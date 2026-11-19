# Tracker source review — November 19, 2026

Working notes for the six Promised vs. Actual records. This folder is not
published. No `review_status` was changed to `accepted`. Accepting a record
puts its date or figure on the public tracker, and that decision is Jay's.

Files checked on November 19, 2026, by downloading the City's own PDFs and
reading the pages below. Hashes are SHA-256 of those downloads.

## Documents hashed

| Source id | Meeting date on the document | SHA-256 |
| --- | --- | --- |
| `sj-21-1392` | Council agenda June 15, 2021 (memo date June 2, 2021; file 21-1392, item 3.12) | `f4b2a68a72dc3f38b3bb85ce5d48e2d8427e5ed5074c4ff826d73d533e4aa1af` |
| `sj-26-1002` | Council agenda September 29, 2026 (memo date September 8, 2026; file 26-1002, item 3.4) | `a0f32ec99ed0a3d1bbabffd46815c3b24be465258ed4499355aa0de86e6dc227` |
| `sj-2026-10-15-fire-dept-memo` | Committee agenda October 15, 2026 (memo date September 24, 2026; approved October 6, 2026) | `0557751a7f8947fabbb37f1f396170eeef2a133f6970c6b658840e20c0961add` |

The fire-memo row previously had `retrieved_at` 2026-10-12, three days before the
October 15 meeting date stored on the row. The memo's own date line is
September 24, 2026, so October 12 is after the memo was written and before the
committee meeting. `retrieved_at` is now 2026-11-19, the day this copy was
downloaded and hashed. The data checker warns when `retrieved_at` is a full
date earlier than `meeting_date`.

`sj-2026-09-29-measure-t-status-report` is Legistar file 26-1045, titled as
renumbered from item 3.4 (26-1002). Its memorandum attachment is the same
September 8, 2026 status report with a Legistar wrapper, so the bytes differ
from the `sj-26-1002` PDF (`ffad7e3d3a4e21fa491a713dfde6d282bc16d6932d77e36975d8f08a68bc0eba`,
18 pages). The two source rows are the same memo. They were not merged.

## What the pages say

Confirmed in file 21-1392:

- Fire Station 8: "the project expected to be completed mid-2024." Page 4.
- Police Training and Academy Facility: "the project expected to be completed at the end of 2023." The sentence finishes on page 6.

Not found in file 21-1392:

- Fire Station 32 has a site description on page 4 and no "fall 2024" completion target in the file.
- The public-safety allocation on page 3 is $180.9 million. The $650 million bond total is on page 1. The label "$227.1M of $650M" is not in this file. The September 8, 2026 status report, page 3, says: "The Measure T program allocates $227.1 million to complete public safety projects."

September 29, 2026 status report (file 26-1045 memorandum, same text as 26-1002). Page numbers below are that memorandum. The three update rows now cite them. They are still `pending_review`.

- Page 3, Fire Station 8: temporary certification of occupancy July 21, 2026; crew began operations July 22, 2026.
- Page 3, Fire Station 32: beneficial use expected September 2026; activation deferred two years in the 2026-2027 Adopted Budget.
- Page 4, Police Training and Academy Facility: beneficial use anticipated December 2026; activation deferred to 2028-2029.
- Page 4, Fire Station 36: "construction completion anticipated in early 2029."

Fire Department Operations Annual Report (the file stored as the October 15 fire memo), page 21: Fire Station 36 "substantial completion in winter 2028." That memo does not say "early 2029." The tracker update `up-2026-10-15-fs36-schedule` cites only this memo for both "Early 2029" and "winter 2028." The early-2029 date is in the September 8 status report, page 4. The row was not rewritten.

October 20, 2026 file 26-1076 links the Annual Report to the City's budget-documents page and attaches a presentation of 13 pages. That presentation does not contain pages 19, 117, or 178. The update rows that cite those pages were not changed. The full Annual Report file was not opened here.

Coyote Creek file 26-1099, presentation page 9: "Anticipated construction completion date – End of 2028." That is the date in this 2026 update, not a separately identified first promise. The words "on track" are not in that presentation.

Pure Water file 26-1100, presentation page 3: full-scale facility "by 2035" and "Full Scale Facility Project (2028-2035)." Page 6 states two grants, $1,092,000 and $2,203,950. The string 3,295,950 is not in that presentation. The words "on track" are not in it.

## Not checked

Budget in Brief, the Fire Station 36 baseline (`sj-budget-in-brief`, page 11, `https://www.sanjoseca.gov/home/showdocument?id=48832`), returned HTTP 403 to this check. The baseline stays `pending_review`.

November 17, 2026 City Council (Legistar event on 2026-11-17): agenda status Final, minutes status Draft, minutes file empty. The November 17 follow-up still waits on posted minutes.

Archive copies of these sources were not saved. That is a public action and was not done.
