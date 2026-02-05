#!/usr/bin/env python3
"""
Goal logic + HR compliance gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Tuple

import pandas as pd

# --- Config you asked for ---
EASY_HR_CAP = 145
LONG_HR_CAP = 155
THRESH_HR_CAP = 165

HR_GATE_WINDOW_DAYS = 14  # rolling window for "any exceeded" rule

RACE_DATE = date(2026, 4, 11)

# Finish goal heuristics (can tune later)
FINISH_LOOKBACK_DAYS = 28
FINISH_MIN_RUNS_PER_WEEK = 2.0  # average over lookback
FINISH_LONG_RUN_MIN_TARGET = 60.0  # early baseline; will ramp later
FINISH_LONG_RUN_STRETCH_TARGET = 75.0  # better indicator


CAP_BY_TYPE = {
    "easy": EASY_HR_CAP,
    "long": LONG_HR_CAP,
    "threshold": THRESH_HR_CAP,
}


@dataclass(frozen=True)
class GoalStatus:
    label: str   # ✅ On track / ⚠️ Possible / ❌ Not on track
    evidence: str


def _status(label: str, evidence: str) -> GoalStatus:
    return GoalStatus(label=label, evidence=evidence)


def compute_hr_compliance(df: pd.DataFrame, today: date | None = None) -> Tuple[bool, Dict]:
    """
    Returns: (pass_gate, details)
    Gate fails if ANY run in the window exceeds its run-type cap.
    """
    if df.empty:
        return True, {"window": f"last {HR_GATE_WINDOW_DAYS} days", "failures": [], "counts": {}}

    if today is None:
        today = pd.Timestamp(df["date"].max()).date()

    window_start = pd.Timestamp(today - timedelta(days=HR_GATE_WINDOW_DAYS - 1))
    w = df[df["date"] >= window_start].copy()

    failures = []
    counts = {}

    for rt, cap in CAP_BY_TYPE.items():
        sub = w[w["run_type"] == rt].copy()
        if sub.empty:
            counts[rt] = {"pass": 0, "fail": 0, "cap": cap}
            continue
        # avg_hr might be null for some activities
        sub = sub.dropna(subset=["avg_hr"])
        fail = sub[sub["avg_hr"] > cap]
        pass_ = sub[sub["avg_hr"] <= cap]
        counts[rt] = {"pass": int(len(pass_)), "fail": int(len(fail)), "cap": cap}
        for _, r in fail.iterrows():
            failures.append({
                "date": pd.Timestamp(r["date"]).date().isoformat(),
                "run_type": rt,
                "avg_hr": int(r["avg_hr"]),
                "cap": cap,
                "source_file": r.get("source_file", ""),
            })

    pass_gate = len(failures) == 0
    details = {
        "window": f"last {HR_GATE_WINDOW_DAYS} days",
        "window_start": pd.Timestamp(window_start).date().isoformat(),
        "window_end": today.isoformat(),
        "counts": counts,
        "failures": failures,
    }
    return pass_gate, details


def finish_goal(df: pd.DataFrame) -> GoalStatus:
    """
    Goal 1: Finish the HM. Based on consistency + long run progression.
    """
    if df.empty:
        return _status("❌ Not on track", "No runs recorded yet.")

    today = pd.Timestamp(df["date"].max()).date()
    start = pd.Timestamp(today - timedelta(days=FINISH_LOOKBACK_DAYS - 1))
    w = df[df["date"] >= start].copy()

    days = (pd.Timestamp(today) - start).days + 1
    weeks = max(days / 7.0, 1e-6)
    runs_per_week = len(w) / weeks

    long_runs = w[w["run_type"] == "long"]
    long_max = float(long_runs["duration_min"].max()) if not long_runs.empty else 0.0

    if runs_per_week >= FINISH_MIN_RUNS_PER_WEEK and long_max >= FINISH_LONG_RUN_MIN_TARGET:
        label = "✅ On track"
    elif runs_per_week >= 1.5:
        label = "⚠️ At risk"
    else:
        label = "❌ Not on track"

    evidence = f"{runs_per_week:.1f} runs/week (last {FINISH_LOOKBACK_DAYS}d); longest long run {long_max:.0f} min."
    return _status(label, evidence)


def time_goal(df: pd.DataFrame, goal_name: str, hr_gate_pass: bool, hr_details: Dict) -> GoalStatus:
    """
    Goal 2/3: Time goals. Hard-failed by HR gate.
    For now, if HR gate passes we mark '⚠️ Possible' until more pace logic is added.
    """
    if df.empty:
        return _status("❌ Not on track", "No runs recorded yet.")

    if not hr_gate_pass:
        # show first failure for clarity
        if hr_details.get("failures"):
            f = hr_details["failures"][0]
            ev = f"HR cap exceeded: {f['run_type']} avg HR {f['avg_hr']} > {f['cap']} on {f['date']}."
        else:
            ev = "HR cap exceeded in the rolling window."
        return _status("❌ Not on track", ev)

    # If HR gate passes, we keep it conservative until pace/efficiency metrics are implemented.
    return _status("⚠️ Possible", "HR compliant recently; add pace/efficiency logic next for a stronger call.")


def compute_race_pace_level(df: pd.DataFrame) -> Tuple[int, float]:
    """
    Compute a 1-5 speedometer level based on recent race pace.
    
    Scale:
    - 1: Won't finish (pace > 15 min/mi)
    - 2: Finish but slow (13.0-15 min/mi)
    - 3: Finish under 2:30 (11.6-13 min/mi, ~2:32)
    - 4: Finish under 2:15 (10.0-11.6 min/mi, ~2:11)
    - 5: Finish under 2:00 (< 10.0 min/mi, i.e., 9:12 pace)
    
    Target 2-hour HM pace: 9:12 min/mi
    Target 2:30 HM pace: 11:36 min/mi
    """
    if df.empty:
        return 1, 0.0
    
    # Use recent easy/threshold runs as pace indicators (exclude long runs which are slower)
    recent = df[df["run_type"].isin(["easy", "threshold"])].copy()
    if recent.empty:
        return 1, 0.0
    
    # Average pace from recent runs
    avg_pace = float(recent["avg_pace_minmi"].mean())
    
    if avg_pace < 10.0:  # Under 2:00 pace
        level = 5
    elif avg_pace < 11.6:  # 2:00 - 2:15 range
        level = 4
    elif avg_pace < 13.0:  # 2:15 - 2:30 range
        level = 3
    elif avg_pace <= 15.0:  # 2:30 - finish range
        level = 2
    else:  # Won't finish
        level = 1
    
    return level, avg_pace


def build_speedometer_graphic(level: int) -> str:
    """
    Build an ASCII speedometer graphic showing race pace confidence level (1-5).
    """
    # Visual representation of a speedometer
    gauges = [
        "🟥🟥🟥🟥🟥 1",  # Level 1: Won't finish
        "🟩🟥🟥🟥🟥 2",  # Level 2: Finish but slow
        "🟩🟩🟥🟥🟥 3",  # Level 3: Under 2:30
        "🟩🟩🟩🟥🟥 4",  # Level 4: Under 2:15
        "🟩🟩🟩🟩🟩 5",  # Level 5: Under 2:00
    ]
    
    # Clamp level to 1-5
    level = max(1, min(5, level))
    
    labels = [
        "Won't finish",
        "Finish slow",
        "Under 2:30",
        "Under 2:15",
        "Under 2:00 🏆",
    ]
    
    return f"{gauges[level - 1]} — {labels[level - 1]}"


def build_goal_block(df: pd.DataFrame) -> str:
    """
    Returns the markdown block to inject into README between GOAL_STATUS markers.
    """
    if df.empty:
        updated = datetime.utcnow().date().isoformat()
        return f"_Last updated: {updated}_\n\nNo runs yet."

    latest_date = pd.Timestamp(df["date"].max()).date()
    weeks_to_race = (RACE_DATE - latest_date).days / 7.0

    hr_pass, hr_details = compute_hr_compliance(df, today=latest_date)
    
    # Calculate race pace level and speedometer
    pace_level, avg_pace = compute_race_pace_level(df)
    speedometer = build_speedometer_graphic(pace_level)

    # HR compliance summary lines
    hr_label = "✅ Pass" if hr_pass else "❌ Fail"
    lines = []
    lines.append(f"**Weeks to race:** {weeks_to_race:.1f}\n")
    lines.append(f"**Race Pace Confidence:** {speedometer}")
    lines.append(f"(Recent avg pace: {avg_pace:.2f} min/mi)")
    lines.append("")
    lines.append(f"**HR compliance ({hr_details['window']}):** {hr_label}")
    for rt in ["easy", "long", "threshold"]:
        c = hr_details["counts"].get(rt, {"pass": 0, "fail": 0, "cap": CAP_BY_TYPE[rt]})
        lines.append(f"- {rt} cap {c['cap']}: {c['pass']}/{c['pass'] + c['fail']} pass")
    if not hr_pass and hr_details.get("failures"):
        f = hr_details["failures"][0]
        lines.append(f"- First failure: **{f['run_type']}** avg HR **{f['avg_hr']}** > {f['cap']} on **{f['date']}**")

    finish = finish_goal(df)
    g_230 = time_goal(df, "sub_2_30", hr_pass, hr_details)
    g_200 = time_goal(df, "sub_2_00", hr_pass, hr_details)

    table = [
        "| Goal | Status | Evidence |",
        "|---|---|---|",
        f"| Finish the half marathon | {finish.label} | {finish.evidence} |",
        f"| Finish under 2:30 | {g_230.label} | {g_230.evidence} |",
        f"| Finish under 2:00 | {g_200.label} | {g_200.evidence} |",
    ]

    updated = latest_date.isoformat()
    header = "\n".join(lines) + "\n\n" + "\n".join(table) + f"\n\n_Last updated: {updated}_"
    return header
