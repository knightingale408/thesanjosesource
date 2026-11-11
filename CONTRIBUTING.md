# CONTRIBUTING

Read `AGENTS.md` first - it has the approval rules that apply to everyone,
human or tool. Short version:

1. Every change goes on a branch and into a pull request. Never push to
   `main`.
2. Nothing goes public without Jay's explicit yes on that specific change.
3. One clear commit per change, written in plain English.

## Working with the data layer

- `data/` is the canonical record: projects (identity + baseline),
  project-updates (append-only), sources (provenance), categories.
- Schemas in `schemas/` define the fields and enums; `DATA_DICTIONARY.md`
  explains them; `METHODOLOGY.md` is the policy.
- Before opening a PR:
  1. `python3 scripts/validate_data.py` - must pass (warnings need a note
     in the PR).
  2. `python3 scripts/build_public_data.py` - if you changed `data/`, and
     commit the regenerated `public-data/projects.json` in the same PR.
  3. `python3 -m pytest tests/` - must pass.
  4. `python3 build.py` and `python3 check_links.py` per `AGENTS.md`.
- Updates to `data/project-updates.csv` are append-only. A wrong row is
  superseded, never edited.
- Changes to baseline values, project identity, status methodology,
  published briefs, schemas or calculation logic require review - call that
  out in the PR description.
- Never invent a number to fill an empty field. Empty means NOT REPORTED.

## Review checklist for extracted records

- [ ] Every value appears in the cited source (page/section given).
- [ ] Original city wording preserved in label fields.
- [ ] `review_status` set honestly (`accepted`, `accepted_with_edits`,
      `rejected`, `needs_more_evidence`).
- [ ] Plausibility warnings reviewed, not just silenced.
