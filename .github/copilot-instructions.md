# GitHub Copilot instructions: The San Jose Source

Read `AGENTS.md` in the repo root before doing anything. It is the rulebook for every agent here.

## Pre-flight (required before any change; Jay, Nov 24, 2026)

Run `python3 tools/preflight.py` and stop if it fails. In short:

1. The repo must be `knightingale408/thesanjosesource`. Never `knightingale408/fiscal-os` (the old repo, "OLDSSJFISCLOSREPO") or `san-jose-sourcearchive`.
2. PRs only. Never merge, approve a deployment, or publish anything Jay has not approved. Jay reviews and merges every PR.
3. Don't touch a `content/brief-N.md` that's queued to publish (changed in another open PR, or waiting in a Publish site run).

If a check fails, stop and tell Jay. Copilot is listed as retired for this repo in `AGENTS.md`; only work here when Jay asks for a specific task.
