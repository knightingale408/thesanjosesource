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


def test_zero_previous_budget_does_not_crash():
    report = validate_data.Report()
    updates = [
        {"update_id": "u1", "project_id": "p1", "reported_at": "2026-01-01",
         "reported_budget_usd": "0"},
        {"update_id": "u2", "project_id": "p1", "reported_at": "2026-06-01",
         "reported_budget_usd": "100"},
    ]
    validate_data.check_plausibility(report, [], updates)
    assert not report.errors


def test_optional_source_patterns_allow_empty_string():
    import re
    schema = validate_data.load_json(
        Path(__file__).resolve().parent.parent / "schemas" / "source.schema.json"
    )
    for field in ("meeting_date", "page_start", "page_end", "document_sha256"):
        pattern = schema["properties"][field]["pattern"]
        assert re.fullmatch(pattern, ""), field
    assert re.fullmatch(schema["properties"]["meeting_date"]["pattern"], "2026-10-20")
    assert re.fullmatch(schema["properties"]["document_sha256"]["pattern"], "ab" * 32)


def test_retrieved_before_meeting_is_flagged():
    report = validate_data.Report()
    sources = [{
        "source_id": "sj-early",
        "retrieved_at": "2026-10-12",
        "meeting_date": "2026-10-15",
        "document_sha256": "",
        "archived_document_url": "",
    }]
    validate_data.check_sources(report, sources)
    assert any("earlier than meeting_date" in warning for warning in report.warnings)
    assert not report.errors


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


def test_legistar_api_or_guidless_links_fail_in_sources():
    import validate_data as vd
    bad = {
        "webapi": "https://webapi.legistar.com/v1/sanjose/matters/12345",
        "no_guid": "https://sanjose.legistar.com/LegislationDetail.aspx?ID=8236697",
        "view_no_guid": "https://sanjose.legistar.com/View.ashx?M=F&ID=15930312",
    }
    for name, url in bad.items():
        report = vd.Report()
        vd.check_sources(report, [{"source_id": name, "source_document_url": url,
                                   "document_sha256": "x" * 64, "archived_document_url": "",
                                   "retrieved_at": "", "meeting_date": ""}])
        assert any("source_document_url" in e for e in report.errors), name


def test_legistar_website_links_pass_in_sources():
    import validate_data as vd
    good = [
        "https://sanjose.legistar.com/LegislationDetail.aspx?ID=8236697&GUID=2DC39C4A-DF14-40B7-BE6D-8E7C7ED6B66B",
        "https://sanjose.legistar.com/View.ashx?M=F&ID=15930312&GUID=B569EB18-C23A-4BEF-9099-0FDCFDF32EF8",
        "https://legistar.granicus.com/sanjose/attachments/0fd0fee4-57a3-4cdd-8372-fe848df992c6.pdf",
    ]
    for url in good:
        report = vd.Report()
        vd.check_sources(report, [{"source_id": "s", "source_document_url": url,
                                   "document_sha256": "x" * 64, "archived_document_url": "",
                                   "retrieved_at": "", "meeting_date": ""}])
        assert report.errors == [], url


def test_votes_minutes_url_without_guid_fails(tmp_path):
    import validate_data as vd
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "votes.csv").write_text(
        "meeting_date,item_number,minutes_url\n"
        "2026-11-17,6.1,https://sanjose.legistar.com/View.ashx?M=M&ID=1427102\n",
        encoding="utf-8")
    report = vd.Report()
    vd.check_votes(report, tmp_path)
    assert any("minutes_url" in e for e in report.errors)
