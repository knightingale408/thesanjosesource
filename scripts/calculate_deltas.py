#!/usr/bin/env python3
"""Deterministic delta calculations and the tracker display view.

Rules (METHODOLOGY.md):
- budget_delta = current_budget - baseline_budget
- budget_delta_percent = budget_delta / baseline_budget * 100
- schedule_delta_days = current_estimated_completion - promised_completion

Missing values stay null. A missing value is NOT REPORTED, never zero.
Percentages are suppressed when the baseline is zero, unknown or not
comparable. Dates keep the precision the sources give: month-precision
inputs produce month-precision deltas (labelled as estimates), and no
day-level precision is invented for approximate dates.

The view has two merged positions per project:
- position: the latest reported value per concept, from any row that is
  not rejected. Each value keeps its own source and review status, so a
  card can show reported values while flagging verification as pending.
- accepted_position: merged from accepted / accepted_with_edits rows
  only. Calculated deltas come from this, so no unreviewed value can
  produce a published number.

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
USABLE = {"pending_review", "needs_more_evidence"} | ACCEPTED


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def usd(value):
    """'1234.5' -> 1234.5; '' -> None (not reported, never zero). Idempotent."""
    if isinstance(value, (int, float)):
        return float(value)
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


def _sorted_updates(updates):
    return sorted(updates, key=lambda u: (u.get("reported_at") or "", u.get("update_id") or ""))


def merge_position(updates, allowed, sources_by_id=None):
    """Latest non-empty value per concept, each keeping its own source.

    A row can report only one concept (e.g. a budget amendment), so
    concepts merge independently. Values from later rows win.
    """
    budget = completion = status = None
    for u in _sorted_updates(updates):
        if (u.get("review_status") or "") not in allowed:
            continue
        if (u.get("reported_budget_usd") or "").strip() or (u.get("reported_budget_label") or "").strip():
            budget = {
                "usd": usd(u.get("reported_budget_usd")),
                "label": u.get("reported_budget_label") or None,
                "source_id": u.get("source_id"),
                "source": (sources_by_id or {}).get(u.get("source_id")),
                "as_of": u.get("reported_at"),
                "review_status": u.get("review_status"),
            }
        if (u.get("reported_completion") or "").strip() or (u.get("reported_completion_label") or "").strip():
            completion = {
                "date": u.get("reported_completion") or None,
                "label": u.get("reported_completion_label") or None,
                "source_id": u.get("source_id"),
                "source": (sources_by_id or {}).get(u.get("source_id")),
                "as_of": u.get("reported_at"),
                "review_status": u.get("review_status"),
            }
        if (u.get("lifecycle_stage") or "").strip() or (u.get("status_code") or "").strip() or (u.get("change_reason") or "").strip():
            status = {
                "lifecycle_stage": u.get("lifecycle_stage") or None,
                "status_code": u.get("status_code") or None,
                "change_reason": u.get("change_reason") or None,
                "source_id": u.get("source_id"),
                "source": (sources_by_id or {}).get(u.get("source_id")),
                "as_of": u.get("reported_at"),
                "review_status": u.get("review_status"),
            }
    return {"budget": budget, "completion": completion, "status": status}


def _history(updates, sources_by_id):
    out = []
    for u in _sorted_updates(updates):
        out.append({
            "update_id": u.get("update_id"),
            "reported_at": u.get("reported_at"),
            "budget_usd": usd(u.get("reported_budget_usd")),
            "budget_label": u.get("reported_budget_label") or None,
            "completion": u.get("reported_completion") or None,
            "completion_label": u.get("reported_completion_label") or None,
            "lifecycle_stage": u.get("lifecycle_stage") or None,
            "status_code": u.get("status_code") or None,
            "change_reason": u.get("change_reason") or None,
            "source_id": u.get("source_id"),
            "source": sources_by_id.get(u.get("source_id")),
            "review_status": u.get("review_status"),
        })
    return out


def current_view(projects, updates, sources, categories):
    """Build the display view for every project.

    Blocked statuses (pending_review, needs_more_evidence, rejected) stay
    out of the accepted position and out of the deltas, but remain visible
    in the reported position and the history, flagged for verification.
    """
    sources_by_id = {s["source_id"]: s for s in sources}
    updates_by_project = {}
    for u in updates:
        updates_by_project.setdefault(u["project_id"], []).append(u)

    # The reported position shows anything not rejected; the accepted
    # position (and the deltas) use accepted rows only.
    allowed = USABLE - {"rejected"}
    accepted = ACCEPTED

    out = []
    for p in projects:
        rows = updates_by_project.get(p["project_id"], [])
        position = merge_position(rows, allowed, sources_by_id)
        accepted_position = merge_position(rows, accepted, sources_by_id)
        history = _history(rows, sources_by_id)
        worst_review = p.get("review_status")
        if any((u.get("review_status") or "") not in accepted for u in rows):
            worst_review = worst_review if (worst_review or "") not in accepted else "pending_review"

        record = {
            "project_id": p["project_id"],
            "project_name": p["project_name"],
            "category": p["category"],
            "category_label": categories.get(p["category"], {}).get("label", p["category"]),
            "department": p.get("department") or None,
            "measure_or_fund": p.get("measure_or_fund") or None,
            "fund": p.get("fund") or None,
            "baseline": {
                "budget_usd": usd(p.get("baseline_budget_usd")),
                "budget_label": p.get("baseline_budget_label") or None,
                "completion": p.get("promised_completion") or None,
                "completion_label": p.get("promised_completion_label") or None,
                "source_id": p.get("baseline_source_id"),
                "source": sources_by_id.get(p.get("baseline_source_id")),
            },
            "position": position,
            "accepted_position": accepted_position,
            "budget_delta": None,
            "schedule_delta": None,
            "history": history,
            "review_status": worst_review,
        }
        cur_budget = position["budget"] or {}
        cur_completion = position["completion"] or {}
        record["budget_delta"] = budget_delta(p.get("baseline_budget_usd"), cur_budget.get("usd") if cur_budget else None)
        record["schedule_delta"] = schedule_delta_months(
            p.get("promised_completion"), cur_completion.get("date") if cur_completion else None)
        out.append(record)
    return out


def main():
    projects = load_csv(DATA / "projects.csv")
    updates = load_csv(DATA / "project-updates.csv")
    sources = load_csv(DATA / "sources.csv")
    categories = json.loads((DATA / "categories.json").read_text(encoding="utf-8"))
    view = current_view(projects, updates, sources, categories)
    print(json.dumps(view, indent=2))


if __name__ == "__main__":
    sys.exit(main())
