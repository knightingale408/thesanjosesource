#!/usr/bin/env python3
"""Deterministic delta calculations for the tracker.

Rules (METHODOLOGY.md section 2.2):
- budget_delta = current_budget - baseline_budget
- budget_delta_percent = budget_delta / baseline_budget * 100
- schedule_delta_days = current_estimated_completion - promised_completion

Missing values stay null. A missing value is NOT REPORTED, never zero.
Percentages are suppressed when the baseline is zero, unknown or not
comparable. Dates keep the precision the sources give: month-precision
inputs produce month-precision deltas (labelled as estimates), and no
day-level precision is invented for approximate dates.

Usage: python3 scripts/calculate_deltas.py [repo_root]
       (as a module: from calculate_deltas import budget_delta, schedule_delta_months, current_view)
"""
import csv
import json
import sys
from pathlib import Path

REPO = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent)
DATA = REPO / "data"


ACCEPTED = {"accepted", "accepted_with_edits"}


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key, value in list(row.items()):
            if isinstance(value, str):
                row[key] = value.strip()
    return rows


def review_state(row):
    return (row.get("review_status") or "").strip()


def usd(value):
    """'1234.5' -> 1234.5; '' -> None (not reported, never zero)."""
    value = (value or "").strip()
    if not value:
        return None
    return float(value)


def budget_delta(baseline, current):
    baseline, current = usd(baseline), usd(current)
    if baseline is None or current is None:
        return {"delta": None, "percent": None, "reason": "baseline or current budget not reported"}
    delta = current - baseline
    result = {"delta": round(delta, 2), "percent": None, "reason": ""}
    if baseline > 0:
        result["percent"] = round(delta / baseline * 100, 1)
    else:
        result["reason"] = "baseline is zero or negative; percentage suppressed"
    return result


def months(date_str):
    """ISO YYYY / YYYY-MM / YYYY-MM-DD -> months since year 0, or None."""
    if not date_str:
        return None
    parts = date_str.split("-")
    y = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else None
    if m is None:
        return None  # year-only: not precise enough for a delta
    return y * 12 + (m - 1)


def schedule_delta_months(promised, current):
    """Month-precision delta. Returns dict; day_precision is False."""
    p, c = months(promised), months(current)
    if p is None or c is None:
        return {"months": None, "day_precision": False,
                "reason": "one side is year-only or not reported; delta not computed"}
    return {"months": c - p, "day_precision": False,
            "reason": "month-precision inputs; treat as an estimate"}


def latest_accepted_update(updates, review_blocked):
    """The latest update explicitly accepted for production.

    A status is accepted only when it is `accepted` or `accepted_with_edits`.
    Anything else, including a padded `pending_review `, stays out. The
    schema checker trims before its enum test, so this comparison trims too.
    """
    accepted = [
        u for u in updates
        if review_state(u) in ACCEPTED and review_state(u) not in review_blocked
    ]
    if not accepted:
        return None
    return sorted(accepted, key=lambda u: (u.get("reported_at") or "", u.get("update_id", "")))[-1]


def current_view(projects, updates, sources, categories, review_blocked):
    """Build the display view: canonical record + latest accepted update + deltas."""
    sources_by_id = {
        s["source_id"]: {k: v for k, v in s.items() if not str(k).startswith("_")}
        for s in sources
    }
    updates_by_project = {}
    for u in updates:
        updates_by_project.setdefault(u["project_id"], []).append(u)

    out = []
    for p in projects:
        latest = latest_accepted_update(updates_by_project.get(p["project_id"], []), review_blocked)
        record = {
            "project_id": p["project_id"],
            "project_name": p["project_name"],
            "category": p["category"],
            "category_label": categories.get(p["category"], {}).get("label", p["category"]),
            "department": p.get("department") or None,
            "measure_or_fund": p.get("measure_or_fund") or None,
            "baseline": {
                "budget_usd": usd(p.get("baseline_budget_usd")),
                "budget_label": p.get("baseline_budget_label") or None,
                "completion": p.get("promised_completion") or None,
                "completion_label": p.get("promised_completion_label") or None,
                "source_id": p.get("baseline_source_id") or None,
                "source": sources_by_id.get(p.get("baseline_source_id")),
                "review_status": review_state(p) or None,
            },
            "latest": None,
            "budget_delta": None,
            "schedule_delta": None,
            "review_status": p.get("review_status"),
        }
        if latest:
            record["latest"] = {
                "reported_at": latest.get("reported_at"),
                "budget_usd": usd(latest.get("reported_budget_usd")),
                "budget_label": latest.get("reported_budget_label") or None,
                "completion": latest.get("reported_completion") or None,
                "completion_label": latest.get("reported_completion_label") or None,
                "lifecycle_stage": latest.get("lifecycle_stage") or None,
                "status_code": latest.get("status_code") or None,
                "change_reason": latest.get("change_reason") or None,
                "source_id": latest.get("source_id"),
                "source": sources_by_id.get(latest.get("source_id")),
                "source_pages": latest.get("source_pages") or None,
                "review_status": review_state(latest),
            }
            # Deltas cite the baseline. An unreviewed baseline must not
            # produce a published number, even if a later update was accepted.
            if review_state(p) in ACCEPTED:
                record["budget_delta"] = budget_delta(p.get("baseline_budget_usd"), latest.get("reported_budget_usd"))
                record["schedule_delta"] = schedule_delta_months(p.get("promised_completion"), latest.get("reported_completion"))
        out.append(record)
    return out


def main():
    projects = load_csv(DATA / "projects.csv")
    updates = load_csv(DATA / "project-updates.csv")
    sources = load_csv(DATA / "sources.csv")
    categories = json.loads((DATA / "categories.json").read_text(encoding="utf-8"))
    view = current_view(projects, updates, sources, categories,
                        review_blocked={"pending_review", "needs_more_evidence", "rejected"})
    print(json.dumps(view, indent=2))


if __name__ == "__main__":
    sys.exit(main())
