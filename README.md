# The San Jose Source

A free, nonpartisan weekly brief on San José City Council money decisions: budgets, fees, costs and what the City said a project would cost and when it would finish. Every factual claim links to the City's official record, mainly agendas and staff reports on [Legistar](https://sanjose.legistar.com) and City budget documents.

- **Website (master copy):** https://thesanjosesource.com
- **Substack (mirror and email list):** https://thesanjosesource.substack.com
- **X:** [@SanJoseSource](https://x.com/SanJoseSource)
- **Contact and corrections:** thesanjosesource@gmail.com
- **Byline:** J Gonzales

## What's in this repo

This repo is the master copy of the website. It is plain static HTML/CSS/JS with no build step.

| Path | What it is |
|---|---|
| `index.html` | Homepage: latest coverage, Promised vs. Actual teaser, subscribe and support links |
| `brief/1/` | Brief #1: Council housing and fee decisions Sept. 15–Oct. 6 and police recruiting overtime (with corrections log) |
| `brief/2/` | Brief #2: Measure T fire stations and police training center, planned vs. actual |
| `tracker/` | Promised vs. Actual tracker: the City's first target dates and what happened |
| `styles.css`, `app.js` | Shared styles and small scroll/nav script |
| `assets/` | Logo, icons, hero and link-preview images |
| `sitemap.xml`, `robots.txt`, `favicon.ico` | Site plumbing |
| `.nojekyll` | Tells GitHub Pages to serve files as-is |

Preview of the current `main` branch: https://knightingale408.github.io/thesanjosesource/

## How the site gets updated

1. Change files here. One clear commit per change.
2. Nothing goes public without Jay's explicit yes.
3. After that yes, **all** site files from this repo are published to the live host (here.now) together, never a partial list.
4. The live site is then checked to be byte-identical to the repo.

The domain stays on here.now until it can be transferred (after Dec 12, 2026); after that it can point at GitHub Pages directly.

## Editorial rules

- **Facts first, opinion labeled.** Each brief has a preview, a recap from the official record, and a clearly marked "My take."
- **Every factual claim links to a City document.** No guesses about motives, no rumors.
- **"Promised" means the City's own published targets,** not contractual commitments. Delays and budget differences are calculated only when City documents give exact dates or amounts; otherwise the cell says *not stated*.
- **Corrections go at the top** of the affected page, and every change to a published page is listed with the original wording.
- **Blank data fields don't prove anything.** Before saying a vote or figure was "not posted," check the meeting's minutes and attachments.

## AI assistance

Research, drafting and source checks are done with AI tools (Claude, Grok and others). A person reviews every claim against the linked source and approves every page before it goes live.
