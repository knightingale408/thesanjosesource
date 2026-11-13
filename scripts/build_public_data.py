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

    # The same checks as `validate_data.py`, including real calendar dates,
    # currency, categories and page order. A subset here used to let
    # 2026-02-30 through the schema pattern.
    report, loaded = validate_data.validate_repo(repo)
    projects = loaded["projects"]
    updates = loaded["updates"]
    sources = loaded["sources"]
    categories = loaded["categories"]

    if report.errors:
        for e in report.errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit("Data validation failed; not building public-data/projects.json")

    view = calculate_deltas.current_view(projects, updates, sources, categories)

    out = repo / "public-data" / "projects.json"
    out.parent.mkdir(exist_ok=True)
    payload = {"schema_version": 1, "generated_from": "data/ (canonical CSVs)", "projects": view}
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out.relative_to(repo)} ({len(view)} projects, "
          f"{sum(1 for p in view if p['accepted_position']['budget'] or p['accepted_position']['completion'] or p['accepted_position']['status'])} with an accepted position).")
    for w in report.warnings:
        print(f"WARNING: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
