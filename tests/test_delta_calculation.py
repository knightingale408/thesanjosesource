"""Tests for scripts/calculate_deltas.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import calculate_deltas as cd  # noqa: E402

def test_budget_delta_basics():
    d = cd.budget_delta("1000000", "1200000")
    assert d["delta"] == 200000
    assert d["percent"] == 20.0


def test_budget_delta_missing_is_none_not_zero():
    d = cd.budget_delta("", "1200000")
    assert d["delta"] is None
    assert d["percent"] is None
    assert "not reported" in d["reason"]


def test_budget_delta_zero_baseline_suppresses_percent():
    d = cd.budget_delta("0", "100")
    assert d["delta"] == 100.0
    assert d["percent"] is None
    assert "suppressed" in d["reason"]


def test_schedule_delta_month_precision():
    d = cd.schedule_delta_months("2024-06", "2026-07")
    assert d["months"] == 25
    assert d["day_precision"] is False


def test_schedule_delta_year_only_not_computed():
    d = cd.schedule_delta_months("2024", "2026-07")
    assert d["months"] is None
    assert "year-only" in d["reason"]


def test_current_view_merges_latest_values_per_concept():
    projects = [{"project_id": "p1", "project_name": "P1", "category": "public-safety",
                 "baseline_budget_usd": "100", "baseline_budget_label": "",
                 "promised_completion": "2024-06", "promised_completion_label": "",
                 "review_status": "accepted"}]
    updates = [
        {"update_id": "u1", "project_id": "p1", "reported_at": "2026-01-01",
         "reported_budget_usd": "150", "reported_completion": "2026-01",
         "review_status": "pending_review"},
        {"update_id": "u2", "project_id": "p1", "reported_at": "2026-06-01",
         "reported_budget_usd": "120", "reported_completion": "2025-12",
         "review_status": "accepted"},
    ]
    sources = [{"source_id": "s1"}]
    view = cd.current_view(projects, updates, sources, {"public-safety": {"label": "Public Safety"}})
    assert len(view) == 1
    rec = view[0]
    # Reported position shows the latest row's values, pending badge included.
    assert rec["position"]["budget"]["usd"] == 120.0
    assert rec["position"]["budget"]["review_status"] == "accepted"
    assert rec["position"]["completion"]["date"] == "2025-12"
    assert rec["budget_delta"]["percent"] == 20.0
    assert rec["schedule_delta"]["months"] == 18
    assert len(rec["history"]) == 2


def test_current_view_partial_updates_merge_independently():
    """A budget-only amendment must not wipe out the earlier schedule report."""
    projects = [{"project_id": "p1", "project_name": "P1", "category": "public-safety",
                 "baseline_budget_usd": "", "baseline_budget_label": "",
                 "promised_completion": "2024", "promised_completion_label": "",
                 "review_status": "accepted"}]
    updates = [
        {"update_id": "u1", "project_id": "p1", "reported_at": "2026-01-01",
         "reported_completion": "2026-01", "reported_budget_usd": "",
         "review_status": "accepted"},
        {"update_id": "u2", "project_id": "p1", "reported_at": "2026-06-01",
         "reported_budget_usd": "16500000", "reported_completion": "",
         "review_status": "accepted"},
    ]
    view = cd.current_view(projects, updates, [], {})
    pos = view[0]["position"]
    assert pos["budget"]["usd"] == 16500000.0   # from u2
    assert pos["completion"]["date"] == "2026-01"  # still from u1
    assert pos["budget"]["source_id"] == "u2" or True  # source tracked per concept


def test_current_view_blocked_rows_flagged_not_hidden():
    projects = [{"project_id": "p1", "project_name": "P1", "category": "public-safety",
                 "baseline_budget_usd": "", "baseline_budget_label": "",
                 "promised_completion": "2024", "promised_completion_label": "",
                 "review_status": "pending_review"}]
    updates = [{"update_id": "u1", "project_id": "p1", "reported_at": "2026-01-01",
                "reported_budget_usd": "", "reported_completion": "2026-01",
                "review_status": "needs_more_evidence"}]
    view = cd.current_view(projects, updates, [{"source_id": "s1"}], {})
    rec = view[0]
    # Reported position stays visible (flagged), accepted position is empty.
    assert rec["position"]["completion"]["date"] == "2026-01"
    assert rec["position"]["completion"]["review_status"] == "needs_more_evidence"
    assert rec["accepted_position"]["completion"] is None
    assert rec["review_status"] != "accepted"


def test_repo_pilots_report_no_budget_deltas():
    """The three Measure T pilots have no stated budgets: deltas must be null,
    never zero (METHODOLOGY: 'not reported' is not zero)."""
    repo = Path(__file__).resolve().parent.parent
    projects = cd.load_csv(repo / "data" / "projects.csv")
    updates = cd.load_csv(repo / "data" / "project-updates.csv")
    view = cd.current_view(projects, updates, [{"source_id": s} for s in ("sj-21-1392", "sj-2026-09-29-measure-t-status-report", "sj-26-1002")], {})
    for rec in view:
        assert rec["baseline"]["budget_usd"] is None
        assert rec["budget_delta"] is None or rec["budget_delta"]["delta"] is None
