# AGENTS.md: rules for AI coding tools in this repo

Read this before changing anything. It applies to Cursor, GitHub Copilot, Claude Code and any other agent working in `knightingale408/thesanjosesource`.

## What this repo is

The master copy of **thesanjosesource.com**, a free, nonpartisan weekly brief on San José City Council money decisions. Substack and X mirror the website. The owner and only approver is **Jay** (byline **J Gonzales**; never publish the name "Jason").

## The approval gate (never work around it)

1. Nothing goes public without Jay's explicit yes on that specific change.
2. Every change goes on a branch and into a pull request. Never push straight to `main`.
3. Merging to `main` starts the **Publish site** workflow. It waits for Jay to approve the `production` deployment, then publishes all site files to here.now and checks live = repo byte for byte.
4. Don't approve deployments, bypass branch rules, or merge with `--admin` unless Jay asks for that exact PR in the current session.
5. Don't touch the domain, DNS, registrar, here.now settings, Stripe, Substack payments or repo secrets.

## How the site is built

- Source for each brief: `content/brief-N.md` (front matter plus body). Read `content/README.md` before adding one.
- `python3 build.py` builds `brief/N/index.html`, refreshes the homepage list, `feed.xml` and `sitemap.xml`. **Run it after any change to `content/` or `build.py`, and commit the generated files in the same PR**, so the repo matches what goes live.
- Static HTML/CSS/JS. No frameworks, no npm, no build tools beyond `build.py`.
- `.github/scripts/publish.py` defines the deployment file list through `EXCLUDE_EXACT` and `EXCLUDE_PREFIX`, excluding repository-only files and directories. All other tracked files are uploaded to the public site; keep private notes, keys and drafts out of those paths.
- `python3 build.py` rewrites `feed.xml` only when a brief item changed. The committed `lastBuildDate` stays put on a rebuild of the same briefs, so a clean `git diff` after `build.py` means the generated pages match the commit.
- `.github/workflows/build-check.yml` runs that check on every pull request. A `content/` change that does not commit the regenerated `brief/`, `index.html`, `feed.xml` and `sitemap.xml` fails CI.

## Naming and numbering (adopted Nov 7, 2026)

- Public word: **Brief**. Label above the headline: `Brief #N · what it covers · Published date`.
- Numbers follow publish order. Drafts never hold a number. Never renumber a published brief.
- File number = brief number = address: `content/brief-3.md` is Brief #3 at `/brief/3/`. Never change an existing `/brief/N/` address.
- Off-schedule posts are labeled `Update · date` with no number.

## Facts and sources

- Every factual claim links to an official City record, usually San José Legistar or a City budget document.
- Legistar links must use the **website** ID and GUID from the agenda page (`LegislationDetail.aspx?ID=…&GUID=…`). Never build links from the API MatterId; they open "Invalid parameters!".
- Cite page numbers for PDFs. Keep City wording such as "approximately". Don't compute new totals, delays or percentages unless the source gives the inputs exactly.
- An empty field in Legistar's data feed doesn't mean nothing happened. Check the minutes before writing "not posted".
- Don't change a fact, figure, quote or source unless Jay asked for that exact change.

## Changing a published page

- Every change to a published page gets an entry in that page's "Corrections and updates" list **and** on `corrections/index.html`, quoting the original wording and dating the change.
- Corrections go at the top of the affected page. Nothing is removed without a record.

## Link checks

Two checkers, used for different jobs:

- `python3 check_links.py <file>` is the pre-publish check for one brief or page. It is the checker that rejects a public Legistar link built from the Web API. `LegislationDetail.aspx` must include both `ID` and `GUID`, `View.ashx` must include `GUID`, and `webapi.legistar.com` is not a citation. Those are errors, not warnings. `--offline` checks that format only and does not fetch URLs. HTML `&amp;` in query strings is unescaped before the check.
- Lychee (`.github/workflows/link-check.yml`) is the sitewide HTTP check. It runs on every pull request, on Monday mornings, and again against the live sitemap after a publish. It follows the links on the pages. HTTP 403 and 429 count as reachable, because some City hosts block automated clients, and concurrency is capped so Legistar does not answer with false 404s. Lychee does not know the GUID rule; `check_links.py` does.

A change that only edits `link-check.yml`, `build-check.yml`, `agenda-pull.yml` or `check_links.py` does not start **Publish site**. A change to `publish.yml` does, on purpose.

## Before you open a PR

1. `python3 build.py`
2. `python3 check_links.py content/brief-N.md` for any brief you touched (or `brief/N/index.html` after building)
3. One clear commit per change, written in plain English
4. The PR description lists: what changed, Jay's approval (date), and what was checked. Say "No facts changed" only if that's true.
5. A failing **Check links** run must be explained in the PR. A known dead City link is a reason to flag it, never a reason to delete a citation.

## Coordination

- Claim the task in the Drive Doc **WORK LOG - who is doing what** before starting; mark it DONE or STOPPED with the PR link after.
- The GitHub Project board "The San Jose Source" is the single status page. Notion is retired.
- Claude (chat) researches, drafts, fact-checks and verifies the live site. It cannot push to this repo, so it hands approved changes to Cursor as exact instructions.
