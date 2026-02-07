# Half Marathon Tracker – April 11, 2026

This repo tracks my training toward a half marathon on **April 11, 2026**, based on Garmin **.FIT** files.

## 🎯 Goal Status (auto-updated)

> Run `python src/update_readme.py` to refresh this section.

<!-- GOAL_STATUS_START -->
**Weeks to race:** 9.0

**Race Pace Confidence:** 🟩🟥🟥🟥🟥 2 — Finish slow
(Recent avg pace: 14.79 min/mi)

**HR compliance (last 14 days):** ❌ Fail
- easy cap 145: 2/3 pass
- long cap 155: 1/1 pass
- threshold cap 165: 0/0 pass
- First failure: **easy** avg HR **146** > 145 on **2026-01-28**

| Goal | Status | Evidence |
|---|---|---|
| Finish the half marathon | ❌ Not on track | 1.0 runs/week (last 28d); longest long run 60 min. |
| Finish under 2:30 | ❌ Not on track | HR cap exceeded: easy avg HR 146 > 145 on 2026-01-28. |
| Finish under 2:00 | ❌ Not on track | HR cap exceeded: easy avg HR 146 > 145 on 2026-01-28. |

_Last updated: 2026-02-07_
<!-- GOAL_STATUS_END -->

## Quickstart

### 1) Create a virtualenv + install deps
```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

### 2) Add a run (manual)
Export a `.fit` file from Garmin and drop it into one of:

- `data/raw/easy/`
- `data/raw/long/`
- `data/raw/threshold/`

Recommended filename: `YYYY-MM-DD.fit` (but any name works).

### 3) Parse + update README
```bash
python src/parse_fit.py
python src/update_readme.py
```

### 4) Commit
```bash
git add .
git commit -m "run: add YYYY-MM-DD + update status"
git push
```

## Data model

The canonical dataset is written to:
- `data/processed/runs.parquet`
- `data/processed/runs.csv`

Columns:
- `date`, `week`, `run_type`, `duration_min`, `distance_mi`, `avg_pace_minmi`, `avg_hr`, `source_file`

## Notes

- HR caps are hard gates for the time goals:
  - easy: avg HR ≤ 145
  - long: avg HR ≤ 155
  - threshold: avg HR ≤ 165
