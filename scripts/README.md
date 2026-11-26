# Pull a City Council agenda

`pull_legistar.py` reads the public Legistar API for the client `sanjose`. It does not use an API key.

It writes three things:

- `data/raw/city-council/<YYYY-MM-DD>/` — the JSON Legistar returned, unchanged
- `content/meetings/<YYYY-MM-DD>.md` — one file for that meeting
- `content/items/<file>.md` — one file per kept file number, for example `26-1183.md`

Then render the pages:

```bash
python3 build.py
```

## Date window

`--since` and `--until` are both required. Both dates are included. The body filter is an exact match on `City Council`, so a separate `City Council Closed Session` body is not included.

```bash
python3 scripts/pull_legistar.py --since 2026-11-17 --until 2026-11-17
```

A wider window is the same command with different dates:

```bash
python3 scripts/pull_legistar.py --since 2026-11-17 --until 2026-11-24
```

Commit the raw JSON, the content files, and the generated `meetings/`, `items/`, and `sitemap.xml` together.

## What it keeps

Titles that match the list at the top of `scripts/record_lib.py` (`DROP_TITLE_PATTERNS`) do not get a page. Every other file number is kept, including routine consent items. Rows with no file number are not pages.

## State

The state on each page comes from fields, not from the wording of a title:

- Meeting still ahead, or still on the meeting day: Agenda only
- Meeting date has passed, and there is no action name, no minutes file, and no vote rows: Outcome not posted
- An action name, a minutes file, or vote rows: Recorded

Matter histories count only when they include an action-name field. A later run that sees a new agenda publication time, or a changed item set, keeps the same URLs and adds `Agenda amended <date>` on the meeting page and on the item pages that changed.

Vote rows for this client come back from `/eventitems/{id}/votes`. The matter votes route is not used.

## Lint

```bash
python3 scripts/lint_record_pages.py
```

That checks the generated `items/` and `meetings/` pages only.
