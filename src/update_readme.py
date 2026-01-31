#!/usr/bin/env python3
"""
Update README Goal Status block from processed runs dataset.

Usage:
  python src/update_readme.py
"""

from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

from goals import build_goal_block

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
RUNS_PARQUET = ROOT / "data" / "processed" / "runs.parquet"

START = "<!-- GOAL_STATUS_START -->"
END = "<!-- GOAL_STATUS_END -->"


def main() -> None:
    if RUNS_PARQUET.exists():
        df = pd.read_parquet(RUNS_PARQUET)
    else:
        df = pd.DataFrame()

    block = build_goal_block(df)

    text = README.read_text(encoding="utf-8")
    pattern = re.compile(rf"{re.escape(START)}.*?{re.escape(END)}", re.DOTALL)

    replacement = f"{START}\n{block}\n{END}"
    new_text, n = pattern.subn(replacement, text, count=1)
    if n != 1:
        raise RuntimeError("Could not find GOAL_STATUS markers in README.md")

    README.write_text(new_text, encoding="utf-8")
    print("README updated.")


if __name__ == "__main__":
    main()
