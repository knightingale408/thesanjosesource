#!/usr/bin/env python3
"""Build public-data/projects.json from the canonical data layer.

Runs the data validation first and refuses to emit anything if it fails, so
the generated file can never outrun the evidence. The tracker frontend will
load this file; the committed output must match a fresh build (CI checks
this). Missing values are emitted as null, never zero.

Usage: python3 scripts/build_public_data.py [repo_root]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_data  # noqa: E402
import calculate_deltas  # noqa: E402


def main():
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent)

    # Validate first: no build on invalid data. The pieces are called directly
    # so this script fails fast with its own output.
    report = validate_data.Report()
    projects = validate_data.load_csv(repo / "data" / "projects.csv")
    updates = validate_data.load_csv(repo / "data" / "project-updates.csv")
    sources = validate_data.load_csv(repo / "data" / "sources.csv")
    categories = json.loads((repo / "data" / "categories.json").read_text(encoding="utf-8"))

    for i, row in enumerate(projects, start=2):
        row["_row"] = i
    for i, row in enumerate(updates, start=2):
        row["_row"] = i
    for i, row in enumerate(sources, start=2):
        row["_row"] = i

    ps = json.loads((repo / "schemas" / "project.schema.json").read_text())
    us = json.loads((repo / "schemas" / "update.schema.json").read_text())
    ss = json.loads((repo / "schemas" / "source.schema.json").read_text())
    for row in projects:
        validate_data.check_schema(report, ps, row, f"project '{row.get('project_id', '?')}'")
    for row in updates:
        validate_data.check_schema(report, us, row, f"update '{row.get('update_id', '?')}'")
    for row in sources:
        validate_data.check_schema(report, ss, row, f"source '{row.get('source_id', '?')}'")
    validate_data.check_unique_ids(report, projects, "project_id", "project")
    validate_data.check_unique_ids(report, updates, "update_id", "update")
    validate_data.check_unique_ids(report, sources, "source_id", "source")
    validate_data.check_editorial(report, projects, updates, sources)

    if report.errors:
        for e in report.errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit("Data validation failed; not building public-data/projects.json")

    view = calculate_deltas.current_view(
        projects, updates, sources, categories,
        review_blocked={"pending_review", "needs_more_evidence", "rejected"})

    out = repo / "public-data" / "projects.json"
    out.parent.mkdir(exist_ok=True)
    payload = {"schema_version": 1, "generated_from": "data/ (canonical CSVs)", "projects": view}
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out.relative_to(repo)} ({len(view)} projects, "
          f"{sum(1 for p in view if p['latest'])} with an accepted latest update).")
    for w in report.warnings:
        print(f"WARNING: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
