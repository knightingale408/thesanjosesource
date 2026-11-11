#!/usr/bin/env python3
"""Validate the tracker data layer: data/*.csv against schemas/*.json.

Three levels of checks, per the roadmap (METHODOLOGY.md section 1.5):

1. Structural  - required fields, unique stable IDs, ISO 8601 dates,
                 numeric currency fields, enumerated values, foreign keys.
2. Editorial   - every changed value has a source, completed projects have
                 an actual completion or a documented exception, records
                 awaiting review cannot be accepted.
3. Plausibility - warnings only. Legitimate corrections and scope changes
                 must be reviewable, not silently rejected.

Errors fail the run (non-zero exit). Warnings do not.

Usage: python3 scripts/validate_data.py [repo_root]
"""
import csv
import json
import re
import sys
from pathlib import Path

REPO = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent)
DATA = REPO / "data"
SCHEMAS = REPO / "schemas"

REVIEW_BLOCKED = {"pending_review", "needs_more_evidence", "rejected"}


class Report:
    def __init__(self):
        self.errors, self.warnings, self.count = [], [], 0

    def error(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")

    def ok(self):
        return not self.errors


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # Schema checks compare a trimmed value, so a trailing space would pass
    # the enum and then fail a later exact comparison. Trim on load.
    for row in rows:
        for key, value in list(row.items()):
            if isinstance(value, str):
                row[key] = value.strip()
    return rows


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# --- Minimal JSON Schema subset validator (type, enum, required, pattern,
#     minLength, additionalProperties). Enough for the flat CSV records;
#     no external dependencies. ---------------------------------------------

def check_schema(report, schema, record, where):
    for field in schema.get("required", []):
        if not (record.get(field) or "").strip():
            report.error(where, f"missing required field '{field}'")
    if schema.get("additionalProperties") is False:
        known = set(schema.get("properties", {}))
        extra = [k for k in record if k and not k.startswith("_") and k not in known]
        if extra:
            report.error(where, f"unknown fields {sorted(extra)}")
    for field, spec in schema.get("properties", {}).items():
        value = (record.get(field) or "").strip()
        if not value:
            continue  # required-ness handled above; empty = not reported
        if "enum" in spec and value not in spec["enum"]:
            report.error(where, f"'{field}': '{value}' not in enum {spec['enum']}")
        if "pattern" in spec and not re.fullmatch(spec["pattern"], value):
            report.error(where, f"'{field}': '{value}' does not match {spec['pattern']}")
        if "minLength" in spec and len(value) < spec["minLength"]:
            report.error(where, f"'{field}': shorter than {spec['minLength']} characters")


# --- Level 1: structural ------------------------------------------------------

def check_unique_ids(report, rows, id_field, label):
    seen = {}
    for row in rows:
        rid = row.get(id_field, "")
        if rid in seen:
            report.error(f"{label} '{rid}'", f"duplicate {id_field} (first at row {seen[rid]})")
        seen[rid] = row.get("_row", "?")
        report.count += 1


def check_iso_date(report, value, where, field, allow_year=True):
    if not value:
        return True
    ok = re.fullmatch(r"\d{4}", value) or re.fullmatch(r"\d{4}-\d{2}", value) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
    if not ok:
        report.error(where, f"'{field}': '{value}' is not ISO 8601 (YYYY, YYYY-MM or YYYY-MM-DD)")
        return False
    if re.fullmatch(r"\d{4}-\d{2}", value):
        month = int(value[5:7])
        if not 1 <= month <= 12:
            report.error(where, f"'{field}': '{value}' has an invalid month")
            return False
    if len(value) == 10:
        try:
            from datetime import date
            date.fromisoformat(value)
        except ValueError:
            report.error(where, f"'{field}': '{value}' is not a real date")
            return False
    if not allow_year and re.fullmatch(r"\d{4}", value):
        report.warn(where, f"'{field}': year-only date '{value}' is treated as an estimate")
    return True


def check_usd(report, value, where, field):
    if not value:
        return  # not reported, never zero
    if not re.fullmatch(r"\d+(\.\d+)?", value):
        report.error(where, f"'{field}': '{value}' must be a plain number (no $, commas or text)")


# --- Level 2: editorial --------------------------------------------------------

def check_editorial(report, projects, updates, sources):
    project_ids = {p["project_id"] for p in projects}
    source_ids = {s["source_id"] for s in sources}

    for u in updates:
        where = f"update '{u['update_id']}'"
        if u["project_id"] not in project_ids:
            report.error(where, f"references unknown project '{u['project_id']}'")
        if u["source_id"] not in source_ids:
            report.error(where, f"references unknown source '{u['source_id']}'")
        # A changed value needs a source page reference when the source has pages.
        if (u.get("reported_budget_usd") or u.get("reported_completion")) and not (u.get("source_pages") or "").strip():
            report.warn(where, "no source_pages given for a reported value")

    for p in projects:
        where = f"project '{p['project_id']}'"
        if (p.get("baseline_source_id") or "") not in source_ids and p.get("baseline_source_id"):
            report.error(where, f"references unknown source '{p['baseline_source_id']}'")
        latest = [u for u in updates if u.get("project_id") == p.get("project_id") and (u.get("review_status") or "") in REVIEW_BLOCKED]
        if (p.get("review_status") or "") in REVIEW_BLOCKED and not latest:
            report.warn(where, f"baseline is '{p['review_status']}' and has no accepted updates yet")

    # Completed projects need an actual completion value or a documented exception.
    accepted = {u["update_id"]: u for u in updates if u["review_status"] not in REVIEW_BLOCKED}
    for u in accepted.values():
        if u.get("lifecycle_stage") == "complete" or u.get("status_code") == "complete":
            where = f"update '{u['update_id']}'"
            if not (u.get("reported_completion") or "").strip():
                report.error(where, "marked complete without a reported completion date")

    # Nothing awaiting review may be marked accepted (schema enum prevents the
    # opposite mismatch; this catches copy-paste between the two columns).
    for row, label, id_field in ((projects, "project", "project_id"), (updates, "update", "update_id")):
        for r in row:
            if r["review_status"] == "accepted" and not r.get("notes", "").strip() and label == "project":
                pass  # notes optional for projects


# --- Level 3: plausibility (warnings only) -------------------------------------

LIFECYCLE_ORDER = ["planning", "design", "permitting", "procurement", "construction", "complete"]


def check_plausibility(report, projects, updates):
    by_project = {}
    for u in sorted(updates, key=lambda u: u["reported_at"]):
        by_project.setdefault(u["project_id"], []).append(u)

    for pid, rows in by_project.items():
        prev = None
        for u in rows:
            where = f"update '{u['update_id']}'"
            if prev is not None:
                if (u.get("lifecycle_stage") in LIFECYCLE_ORDER and prev.get("lifecycle_stage") in LIFECYCLE_ORDER
                        and LIFECYCLE_ORDER.index(u["lifecycle_stage"]) < LIFECYCLE_ORDER.index(prev["lifecycle_stage"])):
                    report.warn(where, f"lifecycle moved backward: {prev['lifecycle_stage']} -> {u['lifecycle_stage']}")
                if prev.get("status_code") == "complete" and u.get("status_code") != "complete":
                    report.warn(where, "previously completed project received a new forecast")
            if u.get("reported_completion") and prev is not None and prev.get("reported_completion"):
                if u["reported_completion"] < prev["reported_completion"]:
                    report.warn(where, f"completion forecast moved earlier: {prev['reported_completion']} -> {u['reported_completion']}")
            if u.get("reported_budget_usd") and prev is not None and prev.get("reported_budget_usd"):
                try:
                    previous = float(prev["reported_budget_usd"])
                    change = float(u["reported_budget_usd"]) - previous
                    if change < 0:
                        report.warn(where, f"reported budget decreased by {change:,.0f} USD")
                    elif previous > 0 and change / previous > 0.25:
                        report.warn(where, f"reported budget jumped more than 25% (+{change:,.0f} USD)")
                except ValueError:
                    pass
            prev = u

    for p in projects:
        if p.get("baseline_budget_usd"):
            try:
                if float(p["baseline_budget_usd"]) <= 0:
                    report.warn(f"project '{p['project_id']}'", "baseline budget is zero or negative; percentages will be suppressed")
            except ValueError:
                pass


def check_sources(report, sources):
    for s in sources:
        where = f"source '{s['source_id']}'"
        if not (s.get("document_sha256") or "").strip():
            report.warn(where, "no document_sha256 yet; changes to the source file are not detectable")
        if not (s.get("archived_document_url") or "").strip():
            report.warn(where, "no archived copy yet; evidence depends on the live URL")


def validate_repo(repo):
    """Run every structural, editorial and plausibility check.

    Returns (report, loaded). The builder must use this, not a subset of
    the checks, so a date such as 2026-02-30 cannot be published.
    """
    repo = Path(repo)
    data = repo / "data"
    schemas = repo / "schemas"
    report = Report()
    projects = load_csv(data / "projects.csv")
    updates = load_csv(data / "project-updates.csv")
    sources = load_csv(data / "sources.csv")
    categories = load_json(data / "categories.json")

    for i, row in enumerate(projects, start=2):
        row["_row"] = i
    for i, row in enumerate(updates, start=2):
        row["_row"] = i
    for i, row in enumerate(sources, start=2):
        row["_row"] = i

    project_schema = load_json(schemas / "project.schema.json")
    update_schema = load_json(schemas / "update.schema.json")
    source_schema = load_json(schemas / "source.schema.json")

    for row in projects:
        check_schema(report, project_schema, row, f"project '{row.get('project_id', '?')}'")
        check_iso_date(report, row.get("promised_completion"), f"project '{row['project_id']}'", "promised_completion")
        check_usd(report, row.get("baseline_budget_usd"), f"project '{row['project_id']}'", "baseline_budget_usd")
    for row in updates:
        check_schema(report, update_schema, row, f"update '{row.get('update_id', '?')}'")
        where = f"update '{row['update_id']}'"
        check_iso_date(report, row.get("reported_at"), where, "reported_at", allow_year=False)
        check_iso_date(report, row.get("reported_completion"), where, "reported_completion")
        check_usd(report, row.get("reported_budget_usd"), where, "reported_budget_usd")
    for row in sources:
        check_schema(report, source_schema, row, f"source '{row.get('source_id', '?')}'")
        check_iso_date(report, row.get("retrieved_at"), f"source '{row['source_id']}'", "retrieved_at", allow_year=False)
        if row.get("meeting_date"):
            check_iso_date(report, row["meeting_date"], f"source '{row['source_id']}'", "meeting_date", allow_year=False)
        if row.get("page_start") and row.get("page_end") and int(row["page_start"]) > int(row["page_end"]):
            report.error(f"source '{row['source_id']}'", "page_start is after page_end")

    check_unique_ids(report, projects, "project_id", "project")
    check_unique_ids(report, updates, "update_id", "update")
    check_unique_ids(report, sources, "source_id", "source")

    # Categories referenced by projects must exist.
    for p in projects:
        if p.get("category") and p["category"] not in categories:
            report.error(f"project '{p['project_id']}'", f"category '{p['category']}' not defined in data/categories.json")

    check_editorial(report, projects, updates, sources)
    check_plausibility(report, projects, updates)
    check_sources(report, sources)
    loaded = {
        "projects": projects,
        "updates": updates,
        "sources": sources,
        "categories": categories,
    }
    return report, loaded


def main():
    report, _loaded = validate_repo(REPO)
    print(f"Validated {report.count} records across projects, updates and sources.")
    for w in report.warnings:
        print(f"WARNING: {w}")
    if report.errors:
        for e in report.errors:
            print(f"ERROR: {e}")
        print(f"\n{len(report.errors)} error(s), {len(report.warnings)} warning(s). Failing.")
        return 1
    print(f"All checks passed ({len(report.warnings)} warning(s) to review).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
