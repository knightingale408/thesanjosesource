# METHODOLOGY

How The San Jose Source decides what counts as a promise, a change, and a
fact. This file is the policy; `DATA_DICTIONARY.md` defines the fields.

## Core principle

Every displayed number must be traceable to a specific City document, page,
meeting, and extraction or editorial decision. If the source does not state
it, we do not display it as a number: it shows as "Not reported", never as
zero.

## What counts as an "original promise"

The baseline is the first completion target (and budget, when stated) in an
official City record: an adopted budget, a council-approved project approval,
or a status report presented to Council. News coverage, community
expectations and developer statements are context, not baselines.

## How baseline budgets are selected

- The first adopted project-level appropriation or estimate is the baseline.
- When the City never gave a project-level number (only a program
  allocation), the baseline budget is left unreported and the program
  allocation is kept as a label.
- Appropriations, encumbrances, expenditures and total project costs are
  different things. They are stored separately and never combined into one
  number.

## Scope changes

A larger current budget can reflect approved scope expansion, inflation,
financing changes or accounting reclassification - not automatically an
"overrun." The City's stated reason is stored in `change_reason` and kept
separate from the calculated delta. We do not label all increases as
overruns.

## Date normalization

- Dates are stored in ISO 8601 at the precision the source gives:
  `YYYY`, `YYYY-MM` or `YYYY-MM-DD`.
- Year-only and month-only values are treated as estimates. The original
  wording ("Fall 2027", "Q2 FY 2027-28") is always preserved in a label
  field.
- Day-level precision is never invented for approximate dates. Deltas
  between month-precision dates are labelled as estimates.

## When a project is "delayed" or "over budget"

- Delayed: the latest reported completion is later than the baseline
  target.
- Over budget: the latest reported budget is above baseline.
- Both are calculated, never typed in by hand.
- Lifecycle stage and performance status are different things:
  "construction" does not mean "on track."

## Corrections

Material corrections are never silent. See `CORRECTIONS.md`. Small
typographic fixes do not need a correction note; the boundary is: if a
reader could have relied on the old value, it gets a note.

## AI-assisted extraction

Automated extraction proposes; it never publishes. Every extracted value
carries `review_status`. Only `accepted` or `accepted_with_edits` records
reach the production build. A reviewer can also `reject` or send the record
back as `needs_more_evidence`.

## What is never inferred

- A missing or empty field never means zero, "no cost," or "never
  happened."
- An empty Legistar feed field does not mean nothing happened; the minutes
  are checked first.
- We do not compute new totals, delays or percentages unless the source
  gives the inputs exactly.
