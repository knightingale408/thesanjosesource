# CORRECTIONS

Policy for correcting the tracker and the briefs. The public record lives at
`corrections/index.html` and in each page's "Corrections and updates" list.

## What is a material correction

A change to a fact, figure, quote, date, source or characterization that a
reader could have relied on. These are never silent:

- Wrong number, date or name.
- A claim the source does not actually support.
- A broken or wrong citation.
- A status change caused by our misreading, not by the City.

Typographic fixes (spelling, formatting, a broken HTML tag) do not need a
correction entry.

## How a correction is recorded

For every material correction, record:

1. Original publication time.
2. Correction time.
3. What changed (quote the original wording).
4. Why it changed.
5. Whether the tracker record also changed.
6. The replacement source, if applicable.

Corrections appear at the top of the affected page and in
`corrections/index.html`, dated. Nothing is removed without a record.

## Tracker-specific rules

- Update rows in `data/project-updates.csv` are append-only: a wrong row is
  superseded by a new row, never edited in place.
- If a correction changes a baseline in `data/projects.csv`, the baseline
  row keeps its `notes` pointing at the correction entry.
- A correction can be published without erasing the original change
  history - that is the point of the append-only design.
