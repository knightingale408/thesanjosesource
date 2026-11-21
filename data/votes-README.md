# data/votes.csv — Council vote records

Repo-only file (under `data/`, which `.github/scripts/publish.py` excludes from the public site). There is no public page for this file yet.

## Purpose

One row per City Council money item where the City Clerk’s minutes are published and linked, with a per-member vote when the minutes support it. Used later for “Since our last brief” and related reporting. Do not invent votes, dates, amounts or statuses.

## Columns (tracker-style CSV)

| Field | Meaning |
|---|---|
| `meeting_date` | Council meeting date (`YYYY-MM-DD`). |
| `item_number` | Agenda item number as on the agenda (e.g. `6.1`, `8.1`). |
| `item_title` | Short title of the item. |
| `money_amount` | Plain number, no `$`/commas. Empty = not stated in the minutes/brief. |
| `outcome` | Short result: `approved`, `denied`, `continued`, `dropped`, etc. |
| `mahan` … `foley` | One column per councilmember (last-name slug). Cell values: `yes`, `no`, `abstain`, `absent`, `recused`. Empty only when the minutes do not support a per-member call. |
| `minutes_url` | Full Legistar minutes URL with GUID (`View.ashx?M=M&ID=…&GUID=…&G=…`). Never a Web API link. |
| `brief_url` | Canonical brief URL that covers this item, e.g. `https://thesanjosesource.com/brief/4/`. |

## Councilmember columns (as of Nov. 2026)

Stable last-name slugs, Mayor first, then members in the roll-call order used in recent minutes:

`mahan`, `kamei`, `campos`, `tordillos`, `cohen`, `ortiz`, `mulcahy`, `doan`, `candelas`, `casey`, `foley`

When a seat changes, add a new column; do not rename historical columns. Note the seat change in a commit message.

## When to add a row

- Minutes are posted **and** linked with a full GUID URL.
- The brief (or this file’s source note) records the outcome from those minutes.
- Per-member cells are filled only when the minutes name yes/no/absent/etc. If the minutes say only “carried unanimously” and name absents, yes = present members and absent = named absents, as already done on the brief — do not guess the rest.

If minutes are not posted yet, leave the file without that row (do not invent).

## Current rows

Nov. 17, 2026 items 6.1, 6.2 and 8.1 from Brief #4, citing the draft minutes linked there. Money amounts for 6.1 and 6.2 are the contract figures stated in that brief (`11248000` and `16885000`); 8.1 has no posted cost estimate.
