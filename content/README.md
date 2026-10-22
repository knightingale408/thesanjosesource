# Adding a weekly brief

This folder holds the **source** for each brief on the site. The build step turns each file into a full HTML page, updates the homepage, RSS feed, and sitemap.

## What belongs here

Add one markdown file per brief:

| Rule | Example |
|------|---------|
| File name | `brief-3.md`, `brief-4.md`, … |
| Location | This folder: `content/` |
| Number | Match the brief number you want on the site (`/brief/3/`, etc.) |

Each file has **YAML front matter** at the top (between `---` lines), then the **body** (markdown or HTML).

### Required front matter

- **title** — Headline on the brief page  
- **description** — Used for search engines and link previews  
- **date** — Publication date as `YYYY-MM-DD`

### Common optional fields

- **dek** — Short subtitle under the headline  
- **series** — e.g. `Weekly brief` or `Promised vs. Actual`  
- **homepage_blurb** — One line on the homepage archive  
- **coverage_label** — Date line under the title on the homepage  
- **eyebrow** — Line above the headline (if omitted, the build script fills one in)  
- **date_modified** — When you correct the brief (`YYYY-MM-DD`)  
- **body_format** — `markdown` (default) or `html` if you paste full HTML sections  

### Example (new weekly brief in markdown)

```markdown
---
title: Your headline here
description: Plain-English summary for Google, Substack previews, and social links.
date: 2026-10-22
series: Weekly brief
homepage_blurb: One sentence for the homepage listing.
coverage_label: Weekly brief · Oct 22, 2026 · Brief No. 3
dek: Optional subtitle under the headline.
---

## What matters this week

- **First point** with a [Legistar source](https://sanjose.legistar.com/Calendar.aspx).

## The money

Paragraph text and links here.

## What happens next

Upcoming votes or deadlines.

## J Gonzales's take

Clearly marked opinion, separate from the facts above.
```

Existing briefs `brief-1.md` and `brief-2.md` are good references (Brief #2 uses `body_format: html` for legacy layout).

---

## Two easy ways to add or edit a brief

### A) Save a file in Windows File Explorer

1. Open this repo on your computer (e.g. `Documents\GitHub\thesanjosesource\content`).
2. Create or edit `brief-N.md` in a text editor (Notepad, VS Code, Cursor, etc.).
3. Save the file.
4. Commit and push to `main` when you are ready to publish (GitHub Desktop, Cursor, or command line).

### B) Create or edit on GitHub in the browser

1. Go to [the content folder on GitHub](https://github.com/knightingale408/thesanjosesource/tree/main/content).
2. Click **Add file** → **Create new file** (or open an existing `brief-N.md` and click the pencil to edit).
3. Name the file `brief-N.md`, paste your front matter and body, and commit to `main`.

---

## Verify links before you publish

From the **repo root**, run:

```bash
python check_links.py content/brief-N.md
```

Replace `N` with your brief number. The script lists every URL in that file, warns about broken San José Legistar links that omit a **GUID**, and checks HTTP status (404s and other errors).

You can also check the built page:

```bash
python build.py
python check_links.py brief/N/index.html
```

---

## How publishing works

1. You push changes to the **`main`** branch on GitHub.
2. The **Publish site** workflow runs automatically. It executes `python build.py`, which:
   - Builds `brief/N/index.html` from each `content/brief-N.md`
   - Updates `index.html` (latest brief + archive)
   - Regenerates `feed.xml` and `sitemap.xml`
3. The workflow then deploys **all** site files to the live host ([thesanjosesource.com](https://thesanjosesource.com)).

This repo uses a **production approval** step in GitHub Actions: the deploy waits for an explicit approval before the site goes live. Nothing is partial—every publish is the full site from `main`.

For local preview only, run `python build.py` on your machine; you do not need to publish to see the generated HTML in the repo folder.
