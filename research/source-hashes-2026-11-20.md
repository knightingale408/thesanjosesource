# Source hashes — November 20, 2026

Working notes. Not published. No `review_status` was changed. No archive copies were saved (Jay: no Wayback saves).

`data/sources.csv` has **9** source records, not 17. Before this change 4 had a SHA-256 and 5 did not. This change adds 3. Two are still open.

## Added

Each file was downloaded twice on Nov. 20, 2026; both downloads gave the same hash.

| Source id | File hashed | Pages | SHA-256 |
| --- | --- | --- | --- |
| `sj-2026-09-29-measure-t-status-report` | Legistar file 26-1045, "Memorandum" attachment: `https://sanjose.legistar.com/View.ashx?M=F&ID=15930312&GUID=B569EB18-C23A-4BEF-9099-0FDCFDF32EF8` | 18 | `3d1418d2dce7b31d90e073de446051922150219a1a5523378251994b0e4eb0c1` |
| `sj-26-1099` | Legistar file 26-1099, "Presentation" attachment (Oct. 13, 2026 joint meeting, Valley Water): `https://sanjose.legistar.com/View.ashx?M=F&ID=16052912&GUID=145D1B8C-5BBE-4FCC-8AC2-5060ECE4F634` | 13 | `46e20da42ef73f41b18943b7d44790fe7d4009f378052ef7bdc5f42d9ad8b661` |
| `sj-26-1100` | Legistar file 26-1100, "Presentation" attachment (Pure Water Silicon Valley, Oct. 13, 2026): `https://sanjose.legistar.com/View.ashx?M=F&ID=16053473&GUID=18A7C022-2911-47E8-A717-0783A1C2A515` | 9 | `9bc44abc62f25b0d22ca668f298c15ea1e467aedbf0b96b59bd19f27962689fd` |

`retrieved_at` on these rows is now 2026-11-20, the download date, following the Nov. 19 practice.

Notes:
- These three rows link to the Legistar record page, not the PDF. The hash is for the attachment listed above, which is the file the tracker cites. For 26-1099 and 26-1100 the presentation is the only City attachment. (26-1099 also has a "Letter from the Public," which was not hashed.)
- The Nov. 19 notes list `ffad7e3d…` (18 pages) for a copy of the 26-1045 memo. Today's download of the attachment linked from the 26-1045 record gives `3d1418d2…`, also 18 pages, the same on two downloads. Not resolved: whether the Nov. 19 copy came from a different URL or the City re-rendered the file.

## Still open (not hashed)

| Source id | Why |
| --- | --- |
| `sj-budget-in-brief` | `https://www.sanjoseca.gov/home/showdocument?id=48832` returns HTTP 403 to automated downloads. Needs a browser download. |
| `sj-26-1076` | The tracker cites Annual Report pp. 19, 117, 178. The 26-1076 Legistar record attaches only a 13-page presentation (`c455ea91…`), which is not the file used. The full Annual Report is on sanjoseca.gov, which blocks automated downloads. Needs a browser download. |

Archive copies: none of the 9 records has one yet. Saving them is a public action and needs Jay's approval.
