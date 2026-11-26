# How to build the Legistar record site

Jay's email, Nov 25, 2026. The words below are the spec. Steps 1–5 are in this repo: the folders, the pull, the pages, the November 17, 2026 week, the neutrality lint, and the memo quotes (recommendation and fiscal or cost section, stored as quotes). Steps 6 and 7 are not built yet.

---

Build the record site first. Do not start with the newsletter, and do not start with a model. A weekly email with no pages does not own the file numbers, and a rewriter with no source text is where the bias comes back.

## What this is

The thing that owns the space is not the newsletter. It is a page for every San José City Council file number, written only from the public record, that exists before anyone else's take does. The weekly brief is the front door. The item index is the property.

San José's Legistar client is sanjose. The API is usable for agendas and attachments. It is not usable yet as a vote record. November 2026 City Council meetings come back with final agendas and staff-memo PDFs, but matter status is still Agenda Ready, histories are empty, and minutes are Draft with no file. A system that says "Council approved" off that feed is inventing the outcome. That invention is where politicized language usually starts.

## Two layers

Record layer, automatic. One URL per meeting and one per file (26-1183, not a clever headline). Every consent item gets a stub, not only the interesting ones. Consent is where most of the money moves, and file numbers are searches almost nobody else targets.

Each stub has only:

- Official title, file number, meeting date, section (Consent, Land Use, ordinance, and so on)
- State: agenda only / meeting held, outcome not in the record / recorded
- The operative ask, copied from the memo's recommendation, not the preamble
- Dollar, fee, date, address, or rule, only if the memo states one
- Links: Legistar item, agenda PDF, memo PDF, minutes PDF when it exists, vote rows when the API actually returns them

No "why it matters." If the memo does not state a resident effect, the page says that.

Brief layer, weekly. Six to eight items off the index, same sentences, not a second voice. Email and X are distribution. The site URL is what you own.

## Neutrality is a lint, not a mood

Closed verb list, and only when a field or a minutes sentence supports it: proposed, recommended, approved, denied, continued, referred, adopted, amended.

Hard bans: crisis, slam, bold, historic, controversial, finally, despite, "the community," "stakeholders" unless quoted, and any sentence that ranks a councilmember or characterizes the room.

Three boxes, in this order:

1. What the staff memo recommends, with the department named
2. What the record shows council did, or "not in the public record as of [timestamp]"
3. What changes for a resident, only if a number, date, fee, or rule is in the memo

Public comment is a count, not the story. Video tone is out. Campaign adjectives in a staff preamble get dropped. The recommendation sentence and the fiscal paragraph stay.

Example, file 26-1183, from the Nov 17, 2026 agenda (title only, not a vote):

File 26-1183. The agenda asks for retroactive approval of free use of the City Hall East and West plazas and the Janet Gray Hayes Rotunda for the Tunnel of Terror event. Legistar status: Agenda Ready. No vote is in the public record. Sources: agenda item and the staff memorandum PDF.

That is the whole voice. Anything past it is commentary and does not ship.

## How to build it, in order

1. A folder that is the product. One git repo. Three outputs, nothing else: data/raw/ (JSON from Legistar, untouched); content/meetings/ (one file per meeting date); content/items/ (one file per file number, e.g. 26-1183.md). Each item file is the page. The brief, later, only links to these files. If a sentence is not in an item file, it does not go in the email.

2. One pull script. No API key. Client is sanjose. Run it by hand until a week looks right.

- Events: GET https://webapi.legistar.com/v1/sanjose/events filtered to EventBodyName eq 'City Council' and a date window.
- Items: GET /v1/sanjose/events/{EventId}/eventitems
- Memos: GET /v1/sanjose/matters/{MatterId}/attachments

Drop, in code, anything whose title matches language access, ADA, Levine Act, how to watch, roll call, closed session, approval of minutes, or draft-agenda review. Keep every remaining file number, including boring consent items.

Write the state in the item file from fields, not from prose:

- Meeting still ahead, agenda final: Agenda only
- Meeting date has passed, no action name, no minutes file, no vote rows: Outcome not posted
- Action name, minutes sentence, or vote rows exist: Recorded

The script must be willing to publish "outcome not posted." If it cannot say that, it is not finished.

3. Pages with fixed URLs. A static site is enough. Two templates.

- /meetings/2026-11-17 asks "What was on the San José City Council agenda for November 17, 2026?" and lists every kept item with its state.
- /items/26-1183 asks "What is file 26-1183?" and shows official title, meeting, state, agenda link, memo PDF link, Legistar link.

No essay on these pages. Title, state, links. Publish the set the same day EventAgendaStatusName is Final, before the meeting. Add a sitemap. Put the site on a domain you control. Substack and X only point at these URLs.

4. Stop there and run one real week. Pull November 17, 2026. Confirm boilerplate is gone, file numbers match Legistar, and every page says Agenda only or Outcome not posted rather than "approved." Put that week on the site. This is v1. It should take an afternoon once, then minutes per agenda.

5. Only then, the memo extract. Add a PDF text step. From each staff memo keep two slices: the recommendation and the fiscal or cost section. Store them on the item file as quotes, with the PDF link. Still no rewriter. If a dollar, fee, date, or address is not in that extract, the page does not mention it.

6. The brief is a pick list, not a new draft. Score an item in if it is an ordinance, fee, rate, tax, budget action, contract, housing entitlement, or utility item, or if the extract contains a dollar amount. Take the top six to eight. The email is those item pages, same words, plus one line at the top: how many items are still "outcome not posted," and the as-of time. One post per picked item: file number, one sentence from the page, link. Do not write a third version for X. Human time is reading those six recommendation paragraphs against the PDF. Not the docket.

7. Minutes, later. A second run of the same script, after the meeting, looks for a minutes file, an action name, or vote rows. If none are there, leave the state alone. When they show up, update the same URL. Do not publish a new recap post.

Add a model last, and only as a shortener of the recommendation quote. Reject its output if it uses a verb the state does not allow, or a number that is not in the extract. If the lint is annoying, ship the quote. The quote is already non-politicized enough.

Do not build yet: committees, video summaries, public-comment writeups, or a "why it matters" box. That is the version that takes 20 hours a week.

## Pipeline, short form

Legistar pull (events, items, attachments, votes, histories) -> normalizer (drop boilerplate, stable IDs) -> state machine (agenda / pending / recorded) -> extractor (PDF memo: recommendation, fiscal) -> selector (score, brief slate) -> style-locked rewriter and lint, last -> record store (item pages and meeting pages) -> brief composer -> distribute (site canonical, Substack, X one-liners).
