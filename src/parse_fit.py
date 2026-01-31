#!/usr/bin/env python3
"""
Parse Garmin .FIT files into a single runs dataset.

Run type is determined by folder:
  data/raw/easy      -> easy
  data/raw/long      -> long
  data/raw/threshold -> threshold

Outputs:
  data/processed/runs.parquet
  data/processed/runs.csv
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from fitparse import FitFile


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUT_PARQUET = ROOT / "data" / "processed" / "runs.parquet"
OUT_CSV = ROOT / "data" / "processed" / "runs.csv"

RUN_TYPE_DIRS = {
    "easy": RAW_DIR / "easy",
    "long": RAW_DIR / "long",
    "threshold": RAW_DIR / "threshold",
}


def _safe_get(d: Dict, key: str, default=None):
    v = d.get(key, default)
    return default if v is None else v


def _meters_to_miles(m: float) -> float:
    return float(m) / 1609.344


def _seconds_to_minutes(s: float) -> float:
    return float(s) / 60.0


def _pace_min_per_mile(distance_mi: float, duration_min: float) -> Optional[float]:
    if distance_mi <= 0 or duration_min <= 0:
        return None
    return duration_min / distance_mi


def parse_fit_summary(fit_path: Path) -> Dict:
    """
    Extract a single-session summary from a FIT file.
    We prefer the 'session' message because it contains totals.
    """
    fit = FitFile(str(fit_path))

    sessions = list(fit.get_messages("session"))
    if not sessions:
        raise ValueError(f"No 'session' message found in {fit_path}")

    sess = sessions[0]
    fields = {f.name: f.value for f in sess}

    start_time = _safe_get(fields, "start_time")
    if start_time is None:
        # fallback: file timestamp or None
        start_time = _safe_get(fields, "timestamp")

    total_timer_time = float(_safe_get(fields, "total_timer_time", 0.0) or 0.0)
    total_distance_m = float(_safe_get(fields, "total_distance", 0.0) or 0.0)

    avg_hr = _safe_get(fields, "avg_heart_rate")
    if avg_hr is not None:
        avg_hr = int(avg_hr)

    distance_mi = _meters_to_miles(total_distance_m) if total_distance_m else 0.0
    duration_min = _seconds_to_minutes(total_timer_time) if total_timer_time else 0.0
    avg_pace = _pace_min_per_mile(distance_mi, duration_min)

    return {
        "start_time": start_time,
        "duration_min": duration_min,
        "distance_mi": distance_mi,
        "avg_pace_minmi": avg_pace,
        "avg_hr": avg_hr,
    }


def scan_fit_files() -> List[Dict]:
    rows: List[Dict] = []
    for run_type, d in RUN_TYPE_DIRS.items():
        d.mkdir(parents=True, exist_ok=True)
        for fit_path in sorted(d.glob("*.fit")):
            summary = parse_fit_summary(fit_path)
            start_time = summary["start_time"]

            # derive date
            if start_time is not None:
                date = pd.to_datetime(start_time).date()
            else:
                # fallback: mtime
                date = pd.to_datetime(fit_path.stat().st_mtime, unit="s").date()

            week = pd.Timestamp(date).isocalendar()
            week_str = f"{week.year}-W{int(week.week):02d}"

            rows.append({
                "date": pd.Timestamp(date),
                "week": week_str,
                "run_type": run_type,
                "duration_min": float(summary["duration_min"]),
                "distance_mi": float(summary["distance_mi"]),
                "avg_pace_minmi": (float(summary["avg_pace_minmi"]) if summary["avg_pace_minmi"] is not None else None),
                "avg_hr": summary["avg_hr"],
                "source_file": str(fit_path.relative_to(ROOT)),
            })
    return rows


def main() -> None:
    rows = scan_fit_files()
    df = pd.DataFrame(rows)

    if df.empty:
        print("No .fit files found under data/raw/*")
        return

    df = df.sort_values(["date", "run_type", "source_file"]).reset_index(drop=True)

    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)
    df.to_csv(OUT_CSV, index=False)

    print(f"Wrote {len(df)} runs -> {OUT_PARQUET.relative_to(ROOT)} and {OUT_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
