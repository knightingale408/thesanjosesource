"""Tests for scripts/validate_data.py using small fixtures."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import validate_data  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name):
    return validate_data.load_csv(FIXTURES / name)


def schemas():
    base = Path(__file__).resolve().parent.parent / "schemas"
    return (
        validate_data.load_json(base / "project.schema.json"),
        validate_data.load_json(base / "update.schema.json"),
        validate_data.load_json(base / "source.schema.json"),
    )


def run_full(projects, updates, sources):
    """Run the same checks main() runs and return the report."""
    report = validate_data.Report()
    ps, us, ss = schemas()
    for row in projects:
        row["_row"] = 2
        validate_data.check_schema(report, ps, row, f"project '{row.get('project_id', '?')}'")
        validate_data.check_iso_date(report, row.get("promised_completion"), "x", "promised_completion")
        validate_data.check_usd(report, row.get("baseline_budget_usd"), "x", "baseline_budget_usd")
    for row in updates:
        row["_row"] = 2
        validate_data.check_schema(report, us, row, f"update '{row.get('update_id', '?')}'")
        validate_data.check_iso_date(report, row.get("reported_at"), "x", "reported_at", allow_year=False)
        validate_data.check_iso_date(report, row.get("reported_completion"), "x", "reported_completion")
        validate_data.check_usd(report, row.get("reported_budget_usd"), "x", "reported_budget_usd")
    for row in sources:
        row["_row"] = 2
        validate_data.check_schema(report, ss, row, f"source '{row.get('source_id', '?')}'")
    validate_data.check_unique_ids(report, projects, "project_id", "project")
    validate_data.check_unique_ids(report, updates, "update_id", "update")
    validate_data.check_unique_ids(report, sources, "source_id", "source")
    validate_data.check_editorial(report, projects, updates, sources)
    validate_data.check_plausibility(report, projects, updates)
    validate_data.check_sources(report, sources)
    return report


def test_valid_fixtures_pass():
    report = run_full(load("valid-projects.csv"), load("valid-updates.csv"), load("valid-sources.csv"))
    assert not report.errors, report.errors


def test_invalid_fixtures_fail():
    report = run_full(load("invalid-projects.csv"), load("invalid-updates.csv"), load("valid-sources.csv"))
    messages = "\n".join(report.errors)
    assert "not in enum" in messages            # bad category and status_code
    assert "duplicate project_id" in messages    # repeated id
    assert "does not match" in messages          # $1.2M currency, ISO dates
    assert "unknown project" in messages         # foreign key to ghost-project
    assert "is not ISO 8601" in messages         # 15/01/2026 reported_at
    assert "missing required field" in messages  # baseline_source_id -> sj-missing row


def test_iso_date_precision():
    report = validate_data.Report()
    assert check_ok(report, "2024")          # year precision allowed for baselines
    assert check_ok(report, "2024-06")
    assert check_ok(report, "2024-06-30")
    assert not check_ok(report, "2026-13")   # invalid month
    assert not check_ok(report, "2024-02-30")  # not a real date
    assert not check_ok(report, "mid-2024")


def check_ok(report, value):
    return validate_data.check_iso_date(report, value, "t", "f")


def test_missing_budget_is_not_zero():
    report = validate_data.Report()
    validate_data.check_usd(report, "", "t", "budget")   # not reported: no error
    validate_data.check_usd(report, "0", "t", "budget")  # zero is a valid number
    validate_data.check_usd(report, "$1.2M", "t", "budget")
    assert len(report.errors) == 1


def test_completed_project_needs_completion_date():
    report = validate_data.Report()
    projects = [{"project_id": "p1", "review_status": "accepted"}]
    updates = [{"update_id": "u1", "project_id": "p1", "review_status": "accepted",
                "lifecycle_stage": "complete", "status_code": "complete",
                "reported_completion": "", "source_id": "s1", "reported_at": "2026-01-01"}]
    sources = [{"source_id": "s1"}]
    validate_data.check_editorial(report, projects, updates, sources)
    assert any("without a reported completion" in e for e in report.errors)


def test_plausibility_warnings_not_errors():
    report = validate_data.Report()
    projects = [{"project_id": "p1", "baseline_budget_usd": "100"}]
    updates = [
        {"update_id": "u1", "project_id": "p1", "reported_at": "2026-01-01",
         "reported_budget_usd": "200", "reported_completion": "2026-06",
         "lifecycle_stage": "construction", "status_code": "delayed"},
        {"update_id": "u2", "project_id": "p1", "reported_at": "2026-06-01",
         "reported_budget_usd": "300", "reported_completion": "2026-03",
         "lifecycle_stage": "design", "status_code": "delayed"},
        {"update_id": "u3", "project_id": "p1", "reported_at": "2026-12-01",
         "reported_budget_usd": "100", "reported_completion": "2026-03",
         "lifecycle_stage": "design", "status_code": "delayed"},
    ]
    validate_data.check_plausibility(report, projects, updates)
    assert not report.errors
    text = "\n".join(report.warnings)
    assert "moved earlier" in text          # completion forecast improved
    assert "budget decreased" in text       # budget went down
    assert "moved backward" in text         # construction -> design
    assert "more than 25%" in text          # 200 -> 300 jump


def test_repo_data_validates():
    """The real data/ files in this repo must pass cleanly."""
    repo = Path(__file__).resolve().parent.parent
    report = validate_data.Report()
    projects = validate_data.load_csv(repo / "data" / "projects.csv")
    updates = validate_data.load_csv(repo / "data" / "project-updates.csv")
    sources = validate_data.load_csv(repo / "data" / "sources.csv")
    for rows, field, label in ((projects, "project_id", "project"),
                               (updates, "update_id", "update"),
                               (sources, "source_id", "source")):
        validate_data.check_unique_ids(report, rows, field, label)
    assert not report.errors, report.errors
