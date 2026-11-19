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
        {"update_id": "u3", "project_id": "p1", "reported_at": "2026-09-01",
         "reported_budget_usd": "200", "reported_completion": "2027-01",
         "review_status": "pending_review"},
    ]
    sources = [{"source_id": "s1"}]
    view = cd.current_view(projects, updates, sources, {"public-safety": {"label": "Public Safety"}})
    assert len(view) == 1
    rec = view[0]
    # Reported position shows the latest row's values, pending badge included.
    assert rec["position"]["budget"]["usd"] == 200.0
    assert rec["position"]["budget"]["review_status"] == "pending_review"
    assert rec["position"]["completion"]["date"] == "2027-01"
    # Deltas come from accepted rows only: u3's unreviewed 200 / 2027-01
    # must not leak into a published number.
    assert rec["accepted_position"]["budget"]["usd"] == 120.0
    assert rec["accepted_position"]["completion"]["date"] == "2025-12"
    assert rec["budget_delta"]["percent"] == 20.0
    assert rec["schedule_delta"]["months"] == 18
    assert len(rec["history"]) == 3


def test_current_view_partial_updates_merge_independently():
    """A budget-only amendment must not wipe out the earlier schedule report."""
    projects = [{"project_id": "p1", "project_name": "P1", "category": "public-safety",
                 "baseline_budget_usd": "", "baseline_budget_label": "",
                 "promised_completion": "2024", "promised_completion_label": "",
                 "review_status": "accepted"}]
    updates = [
        {"update_id": "u1", "project_id": "p1", "reported_at": "2026-01-01",
         "reported_completion": "2026-01", "reported_budget_usd": "",
         "lifecycle_stage": "construction", "status_code": "delayed",
         "source_id": "src-schedule", "review_status": "accepted"},
        {"update_id": "u2", "project_id": "p1", "reported_at": "2026-06-01",
         "reported_budget_usd": "16500000", "reported_completion": "",
         "change_reason": "Council added scope for the training tower.",
         "source_id": "src-budget", "review_status": "accepted"},
    ]
    view = cd.current_view(projects, updates, [], {})
    pos = view[0]["position"]
    assert pos["budget"]["usd"] == 16500000.0   # from u2
    assert pos["completion"]["date"] == "2026-01"  # still from u1
    # Each concept keeps its own source: budget from the amendment,
    # schedule and status from the earlier report. The budget-only
    # amendment carries a change_reason but must not wipe the status.
    assert pos["budget"]["source_id"] == "src-budget"
    assert pos["completion"]["source_id"] == "src-schedule"
    assert pos["status"]["source_id"] == "src-schedule"
    assert pos["status"]["lifecycle_stage"] == "construction"
    assert pos["status"]["status_code"] == "delayed"
    assert pos["budget"]["source_pages"] is None or isinstance(pos["budget"]["source_pages"], str)


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


def test_padded_pending_status_is_not_accepted():
    projects = [{"project_id": "p1", "project_name": "P1", "category": "public-safety",
                 "baseline_budget_usd": "100", "promised_completion": "2024-06",
                 "review_status": "accepted"}]
    updates = [{"update_id": "u1", "project_id": "p1", "reported_at": "2026-01-01",
                "reported_budget_usd": "150", "reported_completion": "2026-01",
                "review_status": "pending_review "}]
    view = cd.current_view(projects, updates, [], {})
    assert view[0]["position"]["budget"]["usd"] == 150.0
    assert view[0]["position"]["budget"]["review_status"] == "pending_review"
    assert view[0]["accepted_position"]["budget"] is None
    assert view[0]["budget_delta"]["delta"] is None


def test_unreviewed_baseline_publishes_no_delta():
    projects = [{"project_id": "p1", "project_name": "P1", "category": "public-safety",
                 "baseline_budget_usd": "100", "promised_completion": "2024-06",
                 "baseline_source_id": "s1", "review_status": "pending_review"}]
    updates = [{"update_id": "u1", "project_id": "p1", "reported_at": "2026-06-01",
                "reported_budget_usd": "150", "reported_completion": "2026-01",
                "source_pages": "19, 117", "source_id": "s1",
                "review_status": "accepted"}]
    sources = [{"source_id": "s1", "document_title": "Memo"}]
    view = cd.current_view(projects, updates, sources, {})
    rec = view[0]
    assert rec["accepted_position"]["budget"]["usd"] == 150.0
    assert rec["accepted_position"]["budget"]["source_pages"] == "19, 117"
    assert rec["baseline"]["source_id"] == "s1"
    assert rec["baseline"]["source"]["document_title"] == "Memo"
    assert rec["budget_delta"]["delta"] is None
    assert rec["schedule_delta"]["months"] is None


def test_public_view_keeps_accepted_values_and_drops_the_rest():
    projects = [{"project_id": "p1", "project_name": "P1", "category": "public-safety",
                 "baseline_budget_usd": "100", "baseline_budget_label": "$100",
                 "promised_completion": "2024-06", "promised_completion_label": "June 2024",
                 "review_status": "accepted"}]
    updates = [
        {"update_id": "u-ok", "project_id": "p1", "reported_at": "2026-06-01",
         "reported_budget_usd": "120", "reported_completion": "2025-12",
         "reported_completion_label": "December 2025",
         "lifecycle_stage": "construction", "status_code": "delayed",
         "review_status": "accepted"},
        {"update_id": "u-pending", "project_id": "p1", "reported_at": "2026-09-01",
         "reported_budget_usd": "200", "reported_budget_label": "$200 pending",
         "reported_completion": "2027-01", "reported_completion_label": "January 2027",
         "lifecycle_stage": "construction", "status_code": "delayed",
         "review_status": "pending_review"},
    ]
    view = cd.current_view(projects, updates, [{"source_id": "s1"}], {})
    # The working view still has the pending row for review.
    assert view[0]["position"]["budget"]["usd"] == 200.0
    public = cd.public_view(view)[0]
    assert public["publication"] == "source_checked"
    assert public["baseline"]["completion_label"] == "June 2024"
    assert public["position"]["budget"]["usd"] == 120.0
    assert public["position"]["completion"]["date"] == "2025-12"
    assert [entry["update_id"] for entry in public["history"]] == ["u-ok"]
    blob = __import__("json").dumps(public)
    assert "2027-01" not in blob
    assert "$200 pending" not in blob


def test_public_view_withholds_every_unaccepted_repo_value():
    """Jay's rule: a date or figure that has not been accepted stays off the public tracker."""
    repo = Path(__file__).resolve().parent.parent
    projects = cd.load_csv(repo / "data" / "projects.csv")
    updates = cd.load_csv(repo / "data" / "project-updates.csv")
    sources = cd.load_csv(repo / "data" / "sources.csv")
    categories = __import__("json").loads((repo / "data" / "categories.json").read_text())
    public = cd.public_view(cd.current_view(projects, updates, sources, categories))
    assert len(public) == 6
    leaked = []
    for record in public:
        if record["publication"] != "awaiting_source_check":
            leaked.append(record["project_id"] + " publication")
        baseline = record["baseline"]
        for key in ("budget_usd", "budget_label", "completion", "completion_label"):
            if baseline.get(key) not in (None, ""):
                leaked.append(f"{record['project_id']} baseline {key}={baseline.get(key)!r}")
        for key in ("budget", "completion", "status"):
            if record["position"].get(key):
                leaked.append(f"{record['project_id']} position {key}")
        if record["history"]:
            leaked.append(f"{record['project_id']} history")
        if record["budget_delta"]["delta"] is not None or record["schedule_delta"]["months"] is not None:
            leaked.append(f"{record['project_id']} delta")
    assert leaked == []


def test_committed_public_json_matches_the_withholding_rule():
    repo = Path(__file__).resolve().parent.parent
    payload = __import__("json").loads((repo / "public-data" / "projects.json").read_text())
    assert len(payload["projects"]) == 6
    for record in payload["projects"]:
        assert record["publication"] == "awaiting_source_check"
        assert record["baseline"]["completion"] is None
        assert record["baseline"]["completion_label"] is None
        assert record["baseline"]["budget_label"] is None
        assert record["position"]["budget"] is None
        assert record["position"]["completion"] is None
        assert record["position"]["status"] is None
        assert record["history"] == []


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
