# Working tools (never published)

Everything in `tools/` and `research/` is for drafting and checking. The publish
script (`.github/scripts/publish.py`) excludes both folders, so nothing here
reaches thesanjosesource.com, and changes here don't trigger the publish workflow.

| Tool | What it does |
|---|---|
| `legistar_pull.py` | Lists upcoming Council items about budgets, housing, fees, public safety, and contracts/spending. Each item gets its full Legistar website link (ID + GUID). Runs automatically on Fridays (Actions > "Agenda pull"). |
| `check_results.py` | Shows whether Legistar has posted the result of each item from a past meeting, and whether minutes are up. |

```bash
python3 tools/legistar_pull.py --since 2026-10-27 --until 2026-10-27 --json
python3 tools/check_results.py --date 2026-10-20
python3 tools/check_results.py --date 2026-10-20 --file 26-1076
```

## Things to know

- **Legistar's data-feed IDs are not website IDs.** Links built straight from the
  API's MatterId/MatterGuid open "Invalid parameters!". `legistar_pull.py` asks
  Legistar's gateway (`gateway.aspx?M=L&ID=<MatterId>`) for the real page and
  stores that URL. Any item marked UNRESOLVED still needs its link fixed by hand.
- **The keyword filter is a starting point, not an editor.** It catches money items
  and also some routine ones (security contract amendments, concessions). Choosing
  what's consequential is still the brief writer's job.
- **"NOT POSTED" means no entry yet,** not that nothing happened. Check the minutes
  and the meeting video before saying a vote or figure wasn't recorded.
- **`research/tracker-detail.json`** holds the richer Promised vs. Actual records
  (delay reasons, earlier revised dates, budget notes) carried over from the old
  `san-jose-source` repo. Every project is `review.status: "unverified"` until it's
  checked against its linked sources. Only verified facts move to
  `promised-vs-actual.csv` or a brief.
