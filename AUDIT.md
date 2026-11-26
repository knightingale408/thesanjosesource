# Audit: Legistar record pages

This file is for an outside reviewer. It is in the git repo and is not uploaded to the public site (`AUDIT.md` is in `EXCLUDE_EXACT` in `.github/scripts/publish.py`). No secrets are required.

The pages are a public-record layer for San José City Council. Each meeting date and each Council file number gets one static page. Wording on the page is the City's own title and field values, plus a fixed state label. Nothing on the page is a rewritten summary.

Jay reviews the pages in the pull request before anything is merged or published. Merging is a separate step, and it is not part of this pipeline.

## What the pipeline does

1. `pull` calls the public Legistar Web API for client `sanjose` (no API key) and saves each response byte for byte under `data/raw/`.
2. The same command writes `data/pulls/<meeting-date>.json`: the pull timestamp, the request URLs, the sha256 of each raw file, and the website LegislationDetail URL resolved through Legistar's gateway.
3. `build` reads only those files. It writes `content/meetings/`, `content/items/`, `meetings/`, `items/`, and `data/manifest.json`.
4. `record_lint.py` fails the HTML if the wording breaks the rules below.
5. `python3 build.py` (the existing site build) discovers every `index.html` and adds `/meetings/` and `/items/` URLs to `sitemap.xml`. It does not rewrite the record pages.

`data/` and `content/` are not part of the public upload. `meetings/` and `items/` are, once a reviewed PR is merged and the production deployment is approved.

## Commands

From the repo root.

Pull one City Council date window (network):

```bash
python3 tools/legistar_records.py pull --since 2026-11-17 --until 2026-11-17
```

`--since` and `--until` are inclusive calendar days. The request is:

`GET https://webapi.legistar.com/v1/sanjose/events?$filter=EventBodyName eq 'City Council' and EventDate ge datetime'YYYY-MM-DD' and EventDate lt datetime'<until + 1 day>'`

Then, for each event:

- `GET /v1/sanjose/events/{EventId}/eventitems`
- `GET /v1/sanjose/matters/{MatterId}/attachments` for every item that has a MatterId
- `GET /v1/sanjose/eventitems/{EventItemId}/votes` for every item that has a MatterId

The votes call is required to tell "no vote rows" from a recorded vote. Matter histories are not requested.

Build and check, offline:

```bash
python3 tools/legistar_records.py build
python3 tools/legistar_records.py build --check
python3 tools/record_lint.py
python3 -m pytest tests/test_record_state.py tests/test_record_lint.py tests/test_record_pages.py -q
python3 build.py
python3 check_links.py --offline meetings/2026-11-17/index.html
python3 check_links.py --offline items/26-1183/index.html
```

`build --check` exits 1 if the HTML, markdown, or manifest differ from what the raw JSON produces. A raw file whose sha256 does not match `data/pulls/` stops the build.

CI runs the tests, the lint, and `build --check` in `.github/workflows/record-check.yml`.

## Where the raw data lives

| Path | What it is |
|---|---|
| `data/raw/sanjose/<window>/events.json` | Untouched events response |
| `data/raw/sanjose/<window>/event-<EventId>-items.json` | Untouched event-items response |
| `data/raw/sanjose/<window>/matter-<MatterId>-attachments.json` | Untouched attachments response |
| `data/raw/sanjose/<window>/eventitem-<EventItemId>-votes.json` | Untouched votes response |
| `data/pulls/<YYYY-MM-DD>.json` | Our index: `pulled_at`, request URLs, sha256, resolved legislation URLs |
| `data/manifest.json` | One object per generated page: path, state, `pulled_at`, `source_urls`, `raw_files`, `state_basis` |
| `content/meetings/<YYYY-MM-DD>.md` | Generated meeting source |
| `content/items/<file>.md` | Generated file source, for example `26-1183.md` |

`pulled_at` is the time of the pull, in UTC. Rebuilds do not stamp a new time.

## How state is derived

Three labels only: `Agenda only`, `Outcome not posted`, `Recorded`.

Evaluated in this order, per kept file:

1. **Recorded** if any of these is present:
   - `EventItemActionName` is a non-empty string, or
   - `EventMinutesFile` is an http(s) URL, or
   - the votes response has at least one row with `VotePersonName` or `VoteValueName`.
2. **Outcome not posted** if none of those are present and the meeting calendar day is before the pull date (`EventDate` date < `pulled_at` date).
3. **Agenda only** otherwise (the meeting day is the pull day or still ahead).

A meeting page whose kept files share one state uses that state in the manifest. Each file row on the meeting page carries its own `data-record-state`.

Fields that do **not** change the state:

| Field | What we do with it |
|---|---|
| `EventItemMatterStatus` | Shown as "Legistar status". `Agenda Ready` stays `Agenda Ready`. It is never turned into approved, adopted, or denied. |
| `EventMinutesStatusName` | Shown as "Minutes status". `Draft` with a null `EventMinutesFile` is not a minutes file. |
| `EventAgendaStatusName` | Shown as "Agenda status". `Final` does not by itself mean the Council acted. It is stored in `state_basis.agenda_final` and is not a state input. A future agenda that is not final is still `Agenda only`. |
| `EventItemActionText` | Left in the raw JSON. Not a state input and not printed. On file 26-1183 this text begins "Adopt a resolution…". That is the agenda sentence, not an action name. |
| `EventItemPassedFlag` / `EventItemPassedFlagName` | Not a state input and not printed. |
| `EventItemTally` | Not a state input and not printed. |
| Matter histories | Not requested. |

`state_basis` in the manifest records the booleans an auditor can recompute: `action_name_present`, `minutes_file_present`, `vote_row_count`, `meeting_date_passed`, `agenda_final`, `minutes_status`.

## What gets a page

Kept: an event item with a file number (`EventItemMatterFile`) whose title does not match the drop list.

Dropped as boilerplate: the title matches this expression (case insensitive). The pattern is `DROP_TITLE_RE` in `tools/record_rules.py`.

```text
language access
americans with disabilit / american disability act / the word ADA
levine act
how to watch / how to observe
roll call
closed session
approval of minutes
approval of city council minutes
approval of council committee minutes
approval of council minutes
draft agenda review / draft-agenda review
```

"How to observe" is included because that is the City's wording for the watch-the-meeting notice. The minutes titles are included because the City inserts "City Council" or "Council Committee" between "approval of" and "minutes".

Left off the page, and counted as `omitted_no_file` in the manifest: agenda lines with no file number (section headers, ceremonial lines, procedure notes). They do not get an `/items/` URL. Their titles are listed in the manifest.

Every other file number is kept, including routine consent items. "Final Adoption of Ordinances" is kept. It is not in the drop list.

Section on the item page is `EventItemMatterType` (for example `Consent Agenda`, `Land Use Consent Agenda`). Agenda number is `EventItemAgendaNumber`.

## Links

Public Legistar item links are not built from the API `EventItemMatterId` or `EventItemMatterGuid`. Those open "Invalid parameters!" on the website. `pull` follows `https://sanjose.legistar.com/gateway.aspx?M=L&ID=<MatterId>` and stores the `LegislationDetail.aspx` URL that includes both `ID` and `GUID`.

Agenda PDF is `EventAgendaFile`. Minutes PDF is `EventMinutesFile`, and the link is omitted when that field is empty. Memorandum and other files are `MatterAttachmentHyperlink` where `MatterAttachmentShowOnInternetPage` is not false. A memorandum is an attachment whose `MatterAttachmentName` matches memorandum, memoranda, or memo. The link text is the attachment name.

Vote rows are printed only when the votes call returns rows. Columns are `VotePersonName` and `VoteValueName`. There is no yes/no total.

## Lint rules

`python3 tools/record_lint.py` reads `meetings/*/index.html` and `items/*/index.html`.

Text inside `data-record-field` is copied from a Legistar field. Text outside those elements is ours.

- Our text may not contain the outcome verbs proposed, recommended, approved, denied, continued, referred, adopted, amended.
- `approved`, `adopted`, and `denied` also fail anywhere on the page, including inside a source field, when the surrounding `data-record-state` is not `Recorded`.
- Our text may not contain: crisis, slam, bold, historic, controversial, finally, despite, "the community", stakeholders, room-color words (packed, tense, heated, chaotic, raucous, fiery, outburst, booed, cheered, applause), or a councilmember last name (Mahan, Kamei, Campos, Tordillos, Cohen, Ortiz, Mulcahy, Doan, Candelas, Casey, Foley).
- A page with no `data-record-state` fails.
- `approval`, `adoption`, and `amendment` are not the verbs `approved`, `adopted`, and `amended`.

Script, style, and noscript text is ignored. The check is the visible wording.

## Known limits

- City Council only. Committees, video, public comment, and memo PDF text are out of scope.
- The state describes this pull's fields. It does not say what a minutes PDF or a video might show if those fields are empty.
- `EventItemActionText` can contain "Adopt" while `EventItemActionName` is empty. v1 prints the official title (`EventItemTitle`) and does not print the action text.
- An official title that itself contains approved, adopted, or denied will fail the lint when the state is not Recorded. That failure is intentional.
- Two City Council events on one calendar day are stored, and the build stops rather than collapsing them onto one page.
- Attachments marked `MatterAttachmentShowOnInternetPage: false` stay in the raw JSON and are not linked.
- The website GUID is resolved at pull time. `build` does not call the network. An unresolved gateway lookup leaves the item page without a Legistar item link and records `legislation_resolved: false`.

## Auditor checklist

1. Open `data/manifest.json`. Pick five `kind: item` paths at random.
2. For each, open `legislation_url` in a browser. Compare the file number, the official title, and the Legistar status to the item page. The page title is `EventItemTitle` with whitespace collapsed.
3. Recompute the state from `state_basis` using the order in "How state is derived". For the Nov. 17, 2026 pull, expect `Outcome not posted` while action name, minutes file, and vote rows are empty. Do not expect the word approved.
4. Open the matching raw item in `data/raw/.../event-<EventId>-items.json` and confirm the title and `EventItemMatterStatus`. Confirm the votes file for that `EventItemId` and the event's `EventMinutesFile`.
5. Confirm one raw file's sha256:

   ```bash
   python3 -c "import hashlib,pathlib; p=pathlib.Path('data/raw/sanjose/2026-11-17/events.json'); print(hashlib.sha256(p.read_bytes()).hexdigest())"
   ```

   The digest must match `files.events.sha256` in `data/pulls/2026-11-17.json`.

6. Run:

   ```bash
   python3 tools/record_lint.py
   python3 tools/legistar_records.py build --check
   python3 -m pytest tests/test_record_state.py tests/test_record_lint.py tests/test_record_pages.py -q
   ```

7. Search the generated HTML for outcome verbs sitting on a non-Recorded page. The lint already fails `approved`, `adopted`, and `denied` in that case. A second pass:

   ```bash
   python3 -c "
   import re, pathlib
   bad = re.compile(r'\\b(approved|adopted|denied)\\b', re.I)
   for p in list(pathlib.Path('meetings').rglob('index.html')) + list(pathlib.Path('items').rglob('index.html')):
       text = p.read_text()
       if 'data-record-state=\"Recorded\"' in text:
           continue
       if bad.search(text):
           print(p)
   "
   ```

   No paths should print.
