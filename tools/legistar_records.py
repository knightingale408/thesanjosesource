#!/usr/bin/env python3
"""Pull San José City Council from Legistar and build record pages.

No API key. The client is ``sanjose``. Raw responses are saved byte for byte
under data/raw/. A later ``build`` reads those files offline.

    python3 tools/legistar_records.py pull --since 2026-11-17 --until 2026-11-17
    python3 tools/legistar_records.py build
    python3 tools/legistar_records.py build --check
    python3 tools/record_lint.py

Pages:

    /meetings/YYYY-MM-DD/
    /items/<file-number>/

``build.py`` picks up the new index.html files the next time it refreshes
sitemap.xml. This script does not edit briefs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from record_lint import lint_html
from record_rules import (
    RECORDED,
    classify_item,
    clean_str,
    flat_text,
    item_question,
    long_date,
    meeting_question,
    record_state,
    state_basis,
)

CLIENT = "sanjose"
API_BASE = f"https://webapi.legistar.com/v1/{CLIENT}"
SITE_BASE = "https://sanjose.legistar.com"
WEB_BASE = "https://thesanjosesource.com"
USER_AGENT = "TheSanJoseSource/1.0 (+https://thesanjosesource.com)"
MEMO_RE = re.compile(r"\b(memorand(?:um|a)|memo)\b", re.I)
FILE_RE = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]{0,40}")

ROOT = Path(__file__).resolve().parent.parent
OWNED_DIRS = ("meetings", "items", "content/meetings", "content/items")


def odata_datetime(value: date) -> str:
    return f"datetime'{value.isoformat()}'"


def events_url(body: str, since: date, until_inclusive: date) -> str:
    """EventDate is a midnight timestamp, so the end bound is the next day."""
    end = until_inclusive + timedelta(days=1)
    escaped = body.replace("'", "''")
    filt = (
        f"EventBodyName eq '{escaped}'"
        f" and EventDate ge {odata_datetime(since)}"
        f" and EventDate lt {odata_datetime(end)}"
    )
    query = urllib.parse.urlencode(
        {"$filter": filt, "$orderby": "EventDate", "$top": "1000"},
        safe="$,()'",
    )
    return f"{API_BASE}/events?{query}"


def fetch_bytes(url: str) -> bytes:
    delay = 2
    last: Exception | None = None
    for attempt in range(4):
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:300]
            if exc.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(delay)
                delay *= 2
                last = exc
                continue
            raise SystemExit(f"Legistar API HTTP {exc.code} for {url}\n{detail!r}") from exc
        except urllib.error.URLError as exc:
            if attempt < 3:
                time.sleep(delay)
                delay *= 2
                last = exc
                continue
            raise SystemExit(f"Legistar API network error for {url}: {exc}") from exc
    raise SystemExit(f"Legistar API failed for {url}: {last}")


def parse_json(data: bytes, what: str) -> object:
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read {what} as JSON: {exc}") from exc


def as_list(payload: object, what: str) -> list:
    if isinstance(payload, dict) and payload.get("@odata.nextLink"):
        raise SystemExit(
            f"{what} returned a next page (@odata.nextLink). Narrow the date window."
        )
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("value"), list):
        return payload["value"]
    raise SystemExit(f"Unexpected {what} payload: {type(payload).__name__}")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def legislation_url_ok(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.netloc.lower() != "sanjose.legistar.com":
        return False
    if not parsed.path.lower().endswith("/legislationdetail.aspx"):
        return False
    qs = urllib.parse.parse_qs(parsed.query)
    has_id = any(key.lower() == "id" and value and value[0] for key, value in qs.items())
    has_guid = any(key.lower() == "guid" and value and value[0] for key, value in qs.items())
    return has_id and has_guid


def resolve_legislation_url(matter_id: int) -> dict:
    """Follow gateway.aspx to the website LegislationDetail URL.

    The API MatterGuid is not the GUID on sanjose.legistar.com.
    """
    gateway = f"{SITE_BASE}/gateway.aspx?M=L&ID={matter_id}"
    req = urllib.request.Request(gateway, headers={"User-Agent": USER_AGENT})
    try:
        _OPENER.open(req, timeout=60)
    except urllib.error.HTTPError as exc:
        location = exc.headers.get("Location") or ""
        if exc.code in (301, 302, 303, 307, 308) and location:
            full = urllib.parse.urljoin(SITE_BASE + "/", location)
            if legislation_url_ok(full):
                return {"url": full, "resolved": True}
    except urllib.error.URLError as exc:
        print(f"warn: gateway lookup failed for matter {matter_id}: {exc}", file=sys.stderr)
    return {"url": "", "resolved": False}


def http_url(value: object) -> str:
    text = clean_str(value)
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return text
    return ""


def public_attachments(payload: object) -> list[dict]:
    """Internet-visible files. Memorandum is a name match, not a rewrite."""
    rows = payload if isinstance(payload, list) else []
    found: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("MatterAttachmentShowOnInternetPage") is False:
            continue
        url = http_url(row.get("MatterAttachmentHyperlink"))
        if not url:
            continue
        name = flat_text(row.get("MatterAttachmentName")) or "Attachment"
        sort = row.get("MatterAttachmentSort")
        att_id = row.get("MatterAttachmentId")
        found.append(
            {
                "id": att_id if isinstance(att_id, int) else 0,
                "kind": "memorandum" if MEMO_RE.search(name) else "document",
                "name": name,
                "sort": sort if isinstance(sort, int) else 0,
                "url": url,
            }
        )
    found.sort(key=lambda row: (row["sort"], row["id"], row["name"]))
    return found


def vote_rows(payload: object) -> list[dict]:
    """Rows from /eventitems/{id}/votes. Empty list means no rows, not a result."""
    rows = payload if isinstance(payload, list) else []
    found: list[tuple[int, int | None, str, str]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        person = flat_text(row.get("VotePersonName"))
        value = flat_text(row.get("VoteValueName"))
        if not person and not value:
            continue
        sort = row.get("VoteSort")
        found.append((index, sort if isinstance(sort, int) else None, person, value))
    if any(sort is not None for _, sort, _, _ in found):
        found.sort(key=lambda row: (row[1] if row[1] is not None else 10**9, row[0]))
    return [{"person": person, "value": value} for _, _, person, value in found]


def _seq(item: dict) -> int:
    seq = item.get("EventItemAgendaSequence")
    return seq if isinstance(seq, int) else 10**9


def attachment_labels(attachments: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for row in attachments:
        counts[row["name"]] = counts.get(row["name"], 0) + 1
    labeled = []
    for row in attachments:
        label = row["name"]
        if counts[row["name"]] > 1 and row["id"]:
            label = f"{row['name']} ({row['id']})"
        labeled.append({**row, "label": label})
    return labeled


def normalize_event(
    event: dict,
    items: list,
    attachments_by_matter: dict[int, list],
    votes_by_item: dict[int, list],
    links: dict[str, dict],
    pulled_at: str,
    source_urls: list[str],
    raw_files: list[str],
    attachment_meta: dict | None = None,
    vote_meta: dict | None = None,
) -> dict:
    """Turn one event plus its raw lists into a meeting dict. No network."""
    as_of = date.fromisoformat(pulled_at[:10])
    meeting_day = date.fromisoformat(clean_str(event.get("EventDate"))[:10])
    agenda_pdf = http_url(event.get("EventAgendaFile"))
    minutes_pdf = http_url(event.get("EventMinutesFile"))
    meeting_url = http_url(event.get("EventInSiteURL"))
    agenda_status = clean_str(event.get("EventAgendaStatusName"))
    minutes_status = clean_str(event.get("EventMinutesStatusName"))
    event_id = int(event["EventId"])

    kept: dict[str, dict] = {}
    kept_order: list[str] = []
    dropped: list[dict] = []
    omitted: list[dict] = []

    for raw_item in sorted(items, key=_seq):
        if not isinstance(raw_item, dict):
            continue
        title = flat_text(raw_item.get("EventItemTitle")) or flat_text(
            raw_item.get("EventItemMatterName")
        )
        file_number = clean_str(raw_item.get("EventItemMatterFile"))
        kind = classify_item(title, file_number)
        event_item_id = raw_item.get("EventItemId")
        matter_id = raw_item.get("EventItemMatterId")
        base = {
            "event_item_id": event_item_id if isinstance(event_item_id, int) else None,
            "file_number": file_number,
            "title": title,
        }
        if kind == "boilerplate":
            dropped.append({**base, "reason": "boilerplate"})
            continue
        if kind == "no_file":
            omitted.append(base)
            continue
        if not FILE_RE.fullmatch(file_number):
            dropped.append({**base, "reason": "file number is not a safe page name"})
            continue

        matter_key = str(matter_id) if isinstance(matter_id, int) else ""
        link = links.get(matter_key) or {}
        votes = vote_rows(votes_by_item.get(event_item_id, []))
        action_name = flat_text(raw_item.get("EventItemActionName"))
        state = record_state(
            meeting_date=meeting_day,
            as_of=as_of,
            action_name=action_name,
            minutes_file=minutes_pdf,
            vote_count=len(votes),
        )
        basis = state_basis(
            meeting_date=meeting_day,
            as_of=as_of,
            agenda_status=agenda_status,
            action_name=action_name,
            minutes_file=minutes_pdf,
            minutes_status=minutes_status,
            vote_count=len(votes),
        )
        agenda_number = flat_text(raw_item.get("EventItemAgendaNumber"))
        record = {
            "action_name": action_name,
            "agenda_number": agenda_number,
            "agenda_numbers": [agenda_number] if agenda_number else [],
            "agenda_pdf": agenda_pdf,
            "api_matter_id": matter_id if isinstance(matter_id, int) else None,
            "attachments": attachment_labels(
                public_attachments(attachments_by_matter.get(matter_id, []))
            ),
            "basis": basis,
            "event_id": event_id,
            "event_item_id": base["event_item_id"],
            "file_number": file_number,
            "legislation_resolved": bool(link.get("resolved")) and legislation_url_ok(
                clean_str(link.get("url"))
            ),
            "legislation_url": clean_str(link.get("url"))
            if link.get("resolved") and legislation_url_ok(clean_str(link.get("url")))
            else "",
            "legistar_status": flat_text(raw_item.get("EventItemMatterStatus")),
            "meeting_date": meeting_day.isoformat(),
            "meeting_url": meeting_url,
            "minutes_pdf": minutes_pdf,
            "minutes_status": minutes_status,
            "pulled_at": pulled_at,
            "section": flat_text(raw_item.get("EventItemMatterType")),
            "state": state,
            "title": title or "(no title)",
            "votes": votes,
        }
        if file_number in kept:
            prior = kept[file_number]
            if agenda_number and agenda_number not in prior["agenda_numbers"]:
                prior["agenda_numbers"].append(agenda_number)
                prior["agenda_number"] = ", ".join(prior["agenda_numbers"])
            if state == RECORDED:
                prior["state"] = state
                prior["basis"] = basis
                prior["action_name"] = action_name or prior["action_name"]
                prior["votes"] = votes or prior["votes"]
            continue
        kept[file_number] = record
        kept_order.append(file_number)

    item_records = []
    for file_number in kept_order:
        record = kept[file_number]
        extra_urls: list[str] = []
        extra_raw: list[str] = []
        matter_key = str(record["api_matter_id"]) if record["api_matter_id"] is not None else ""
        item_key = str(record["event_item_id"]) if record["event_item_id"] is not None else ""
        for meta in (
            (attachment_meta or {}).get(matter_key) or {},
            (vote_meta or {}).get(item_key) or {},
        ):
            if meta.get("url"):
                extra_urls.append(meta["url"])
            if meta.get("path"):
                extra_raw.append(meta["path"])
        record["source_urls"] = _item_source_urls(record, source_urls + extra_urls)
        record["raw_files"] = list(raw_files) + extra_raw
        item_records.append(record)

    return {
        "agenda_pdf": agenda_pdf,
        "agenda_status": agenda_status,
        "as_of": as_of.isoformat(),
        "dropped": dropped,
        "event_id": event_id,
        "event_location": flat_text(event.get("EventLocation")),
        "event_time": flat_text(event.get("EventTime")),
        "items": item_records,
        "meeting_date": meeting_day.isoformat(),
        "meeting_url": meeting_url,
        "minutes_pdf": minutes_pdf,
        "minutes_status": minutes_status,
        "omitted_no_file": omitted,
        "pulled_at": pulled_at,
        "question": meeting_question(meeting_day, as_of),
        "raw_files": list(raw_files),
        "source_urls": _dedupe(
            source_urls + [meeting_url, agenda_pdf, minutes_pdf]
        ),
    }


def _dedupe(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def _item_source_urls(item: dict, shared: list[str]) -> list[str]:
    urls = list(shared)
    urls.append(item["meeting_url"])
    urls.append(item["legislation_url"])
    urls.append(item["agenda_pdf"])
    urls.append(item["minutes_pdf"])
    urls.extend(row["url"] for row in item["attachments"])
    return _dedupe(urls)


def esc(value: str) -> str:
    import html as html_lib

    return html_lib.escape(value, quote=True)


def _dd(value: str, field: str | None) -> str:
    if field:
        return f'<dd data-record-field="{esc(field)}">{esc(value)}</dd>'
    return f"<dd>{esc(value)}</dd>"


def field_row(label: str, value: str, field: str) -> str:
    shown = value if value else "none"
    use_field = field if value else None
    return f"<dt>{esc(label)}</dt>\n{_dd(shown, use_field)}"


def ext_a(url: str, label: str, field: str | None = None) -> str:
    attr = f' data-record-field="{esc(field)}"' if field else ""
    return (
        f'<a href="{esc(url)}"{attr} target="_blank" rel="noopener noreferrer">'
        f"{esc(label)}</a>"
    )


def source_items(item: dict) -> str:
    parts: list[str] = []
    if item["legislation_url"]:
        parts.append(f"<li>{ext_a(item['legislation_url'], 'Legistar item')}</li>")
    else:
        parts.append("<li>Legistar item: website link not resolved</li>")
    if item["agenda_pdf"]:
        parts.append(f"<li>{ext_a(item['agenda_pdf'], 'Agenda PDF')}</li>")
    # Memoranda only. Other public attachments stay in the manifest and the
    # raw JSON. Putting every PDF on the page makes Granicus answer the
    # sitewide link check with false 404s.
    for row in item["attachments"]:
        if row["kind"] != "memorandum":
            continue
        parts.append(f"<li>{ext_a(row['url'], row['label'], 'attachment_name')}</li>")
    if item["minutes_pdf"]:
        parts.append(f"<li>{ext_a(item['minutes_pdf'], 'Minutes PDF')}</li>")
    if item["meeting_url"]:
        parts.append(f"<li>{ext_a(item['meeting_url'], 'Legistar meeting page')}</li>")
    meeting_href = f"../../meetings/{item['meeting_date']}/"
    parts.append(
        f'<li><a href="{esc(meeting_href)}">Meeting page for {esc(long_date(item["meeting_date"]))}</a></li>'
    )
    return "\n".join(parts)


def votes_html(votes: list[dict]) -> str:
    if not votes:
        return "<h2>Votes</h2>\n<p>Vote rows: none in this pull.</p>"
    body = "\n".join(
        "<tr>"
        f"<td>{esc(row['person'])}</td>"
        f"<td>{esc(row['value'])}</td>"
        "</tr>"
        for row in votes
    )
    return f"""<h2>Votes</h2>
<div class="brief-table-wrap" data-record-field="votes">
<table class="brief-table">
<caption>Vote rows returned for this file</caption>
<thead>
<tr><th scope="col">Person</th><th scope="col">Vote</th></tr>
</thead>
<tbody>
{body}
</tbody>
</table>
</div>"""


def page_shell(title: str, description: str, canonical_path: str, main_html: str) -> str:
    canonical = WEB_BASE + canonical_path
    ld = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": title,
            "url": canonical,
            "isPartOf": {
                "@type": "WebSite",
                "name": "The San Jose Source",
                "url": WEB_BASE + "/",
            },
        },
        ensure_ascii=False,
    ).replace("<", "\\u003c")
    prefix = "../.."
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{esc(title)} — The San Jose Source</title>
<meta name="description" content="{esc(description)}" />
<link rel="canonical" href="{esc(canonical)}" />
<link rel="icon" href="{prefix}/favicon.ico" sizes="any" />
<link rel="icon" href="{prefix}/assets/favicon-32.png" type="image/png" sizes="32x32" />
<link rel="icon" href="{prefix}/assets/icon-192.png" type="image/png" sizes="192x192" />
<link rel="apple-touch-icon" href="{prefix}/assets/apple-touch-icon.png" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&amp;family=Syne:wght@600;700;800&amp;display=swap" rel="stylesheet" />
<link rel="stylesheet" href="{prefix}/styles.css" />
<meta property="og:site_name" content="The San Jose Source" />
<meta property="og:title" content="{esc(title)}" />
<meta property="og:description" content="{esc(description)}" />
<meta property="og:url" content="{esc(canonical)}" />
<meta property="og:type" content="website" />
<meta property="og:image" content="{WEB_BASE}/assets/og.jpg" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{esc(title)}" />
<meta name="twitter:description" content="{esc(description)}" />
<meta name="twitter:image" content="{WEB_BASE}/assets/og.jpg" />
<meta name="theme-color" content="#0f4c5c" />
<meta name="referrer" content="strict-origin-when-cross-origin" />
<script type="application/ld+json">
{ld}
</script>
</head>
<body class="page-brief page-record">
<a class="skip" href="#main">Skip to content</a>
<header class="topbar">
<nav class="nav nav--light" aria-label="Primary">
<a class="nav__brand" href="{prefix}/">The San Jose Source</a>
<div class="nav__links">
<a class="nav__link" href="{prefix}/#coverage">Briefs</a>
<a class="nav__link" href="{prefix}/tracker/">Promised vs. Actual</a>
<a class="nav__link" href="{prefix}/about/">About</a>
<a class="nav__link" href="{prefix}/#subscribe">Subscribe</a>
</div>
</nav>
</header>
<main id="main" class="brief">
{main_html}
</main>
<footer class="footer">
<div class="wrap footer__inner">
<p class="footer__brand">The San Jose Source</p>
<p class="footer__by">By J Gonzales · Nonpartisan · Record-linked</p>
<p class="footer__by"><a href="{WEB_BASE}/">www.TheSanJoseSource.com</a></p>
<p class="footer__links">
<a href="mailto:thesanjosesource@gmail.com">thesanjosesource@gmail.com</a>
·
<a href="https://x.com/SanJoseSource" target="_blank" rel="noopener noreferrer">@SanJoseSource</a>
·
<a href="https://thesanjosesource.substack.com" target="_blank" rel="noopener noreferrer">Substack</a>
</p>
</div>
</footer>
<script src="{prefix}/app.js" defer></script>
<noscript><style>.reveal{{opacity:1;transform:none}}</style></noscript>
</body>
</html>
"""


def item_description(item: dict) -> str:
    title = item["title"]
    if len(title) > 140:
        title = title[:137].rstrip() + "..."
    return (
        f"File {item['file_number']} on the San José City Council agenda for "
        f"{long_date(item['meeting_date'])}. State: {item['state']}. {title}"
    )


def render_item_html(item: dict) -> str:
    question = item_question(item["file_number"])
    rows = "\n".join(
        [
            field_row("File number", item["file_number"], "file_number"),
            field_row("Meeting date", long_date(item["meeting_date"]), "meeting_date"),
            field_row("Agenda number", item["agenda_number"], "agenda_number"),
            field_row("Section", item["section"], "section"),
            field_row("Legistar status", item["legistar_status"], "legistar_status"),
            field_row("Action name", item["action_name"], "action_name"),
            field_row("Meeting minutes status", item["minutes_status"], "minutes_status"),
            field_row("Minutes PDF", "linked below" if item["minutes_pdf"] else "", "minutes_pdf"),
        ]
    )
    main = f"""<article class="wrap wrap--reading" data-record-state="{esc(item["state"])}">
<p class="eyebrow">City Council file</p>
<h1 class="brief__title">{esc(question)}</h1>
<p class="brief__meta">As of <time datetime="{esc(item["pulled_at"])}">{esc(item["pulled_at"])}</time>.</p>
<p class="brief__lede" data-record-field="title">{esc(item["title"])}</p>
<p>State: <span class="record-state">{esc(item["state"])}</span></p>
<h2>Record</h2>
<dl class="record-dl">
{rows}
</dl>
<h2>Sources</h2>
<ul>
{source_items(item)}
</ul>
{votes_html(item["votes"])}
</article>"""
    return page_shell(question, item_description(item), f"/items/{item['file_number']}/", main)


def render_meeting_html(meeting: dict) -> str:
    states: dict[str, int] = {}
    for item in meeting["items"]:
        states[item["state"]] = states.get(item["state"], 0) + 1
    rows = []
    for item in meeting["items"]:
        href = f"../../items/{item['file_number']}/"
        rows.append(
            f'<tr data-record-state="{esc(item["state"])}">'
            f'<td data-record-field="file_number"><a href="{esc(href)}">{esc(item["file_number"])}</a></td>'
            f'<td data-record-field="agenda_number">{esc(item["agenda_number"] or "none")}</td>'
            f'<td data-record-field="section">{esc(item["section"] or "none")}</td>'
            f'<td><span class="record-state">{esc(item["state"])}</span></td>'
            f'<td data-record-field="title">{esc(item["title"])}</td>'
            "</tr>"
        )
    table = "\n".join(rows) if rows else "<tr><td colspan=\"5\">No file numbers on this page.</td></tr>"
    meta_rows = "\n".join(
        [
            field_row("Meeting date", long_date(meeting["meeting_date"]), "meeting_date"),
            field_row("Time", meeting["event_time"], "event_time"),
            field_row("Place", meeting["event_location"], "event_location"),
            field_row("Agenda status", meeting["agenda_status"], "agenda_status"),
            field_row("Minutes status", meeting["minutes_status"], "minutes_status"),
        ]
    )
    links = []
    if meeting["meeting_url"]:
        links.append(f"<li>{ext_a(meeting['meeting_url'], 'Legistar meeting page')}</li>")
    if meeting["agenda_pdf"]:
        links.append(f"<li>{ext_a(meeting['agenda_pdf'], 'Agenda PDF')}</li>")
    if meeting["minutes_pdf"]:
        links.append(f"<li>{ext_a(meeting['minutes_pdf'], 'Minutes PDF')}</li>")
    else:
        links.append("<li>Minutes PDF: none in this pull.</li>")
    pretty = long_date(meeting["meeting_date"])
    description = (
        f"San José City Council agenda for {pretty}. "
        f"{len(meeting['items'])} file numbers. "
        + ", ".join(f"{name}: {count}" for name, count in sorted(states.items()))
    )
    main = f"""<article class="wrap wrap--reading wrap--wide">
<p class="eyebrow">City Council agenda</p>
<h1 class="brief__title">{esc(meeting["question"])}</h1>
<p class="brief__meta">As of <time datetime="{esc(meeting["pulled_at"])}">{esc(meeting["pulled_at"])}</time>.</p>
<p>This page lists Council file numbers from this City Council agenda. Language access, ADA, the Levine Act, how to watch or observe, roll call, closed session, approval of minutes, and draft-agenda review are left off. Agenda lines with no file number do not get a page.</p>
<h2>Meeting</h2>
<dl class="record-dl">
{meta_rows}
</dl>
<h2>Sources</h2>
<ul>
{chr(10).join(links)}
</ul>
<h2>Files</h2>
<div class="brief-table-wrap">
<table class="brief-table">
<caption>Council file numbers for {esc(pretty)}</caption>
<thead>
<tr>
<th scope="col">File</th>
<th scope="col">Agenda number</th>
<th scope="col">Section</th>
<th scope="col">State</th>
<th scope="col">Official title</th>
</tr>
</thead>
<tbody>
{table}
</tbody>
</table>
</div>
</article>"""
    return page_shell(meeting["question"], description, f"/meetings/{meeting['meeting_date']}/", main)


def yaml_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_item_md(item: dict) -> str:
    lines = [
        "<!-- Generated from data/raw by tools/legistar_records.py. Do not edit by hand. -->",
        "---",
        f"file_number: {yaml_str(item['file_number'])}",
        f"meeting_date: {yaml_str(item['meeting_date'])}",
        f"agenda_number: {yaml_str(item['agenda_number'])}",
        f"section: {yaml_str(item['section'])}",
        f"state: {yaml_str(item['state'])}",
        f"legistar_status: {yaml_str(item['legistar_status'])}",
        f"action_name: {yaml_str(item['action_name'])}",
        f"pulled_at: {yaml_str(item['pulled_at'])}",
        f"legislation_url: {yaml_str(item['legislation_url'])}",
        f"agenda_pdf: {yaml_str(item['agenda_pdf'])}",
        f"minutes_pdf: {yaml_str(item['minutes_pdf'])}",
        f"title: {yaml_str(item['title'])}",
        "---",
        "",
        item["title"],
        "",
        f"State: {item['state']}",
        "",
    ]
    if item["legislation_url"]:
        lines.append(f"- [Legistar item]({item['legislation_url']})")
    if item["agenda_pdf"]:
        lines.append(f"- [Agenda PDF]({item['agenda_pdf']})")
    for row in item["attachments"]:
        if row["kind"] != "memorandum":
            continue
        lines.append(f"- [{row['label']}]({row['url']})")
    if item["minutes_pdf"]:
        lines.append(f"- [Minutes PDF]({item['minutes_pdf']})")
    lines.append("")
    return "\n".join(lines)


def render_meeting_md(meeting: dict) -> str:
    lines = [
        "<!-- Generated from data/raw by tools/legistar_records.py. Do not edit by hand. -->",
        "---",
        f"meeting_date: {yaml_str(meeting['meeting_date'])}",
        f"pulled_at: {yaml_str(meeting['pulled_at'])}",
        f"agenda_status: {yaml_str(meeting['agenda_status'])}",
        f"minutes_status: {yaml_str(meeting['minutes_status'])}",
        f"title: {yaml_str(meeting['question'])}",
        "---",
        "",
        meeting["question"],
        "",
        f"As of {meeting['pulled_at']}.",
        "",
    ]
    if meeting["meeting_url"]:
        lines.append(f"- [Legistar meeting page]({meeting['meeting_url']})")
    if meeting["agenda_pdf"]:
        lines.append(f"- [Agenda PDF]({meeting['agenda_pdf']})")
    if meeting["minutes_pdf"]:
        lines.append(f"- [Minutes PDF]({meeting['minutes_pdf']})")
    lines.append("")
    for item in meeting["items"]:
        lines.append(
            f"- {item['file_number']}: {item['state']}. {item['title']}"
        )
    lines.append("")
    return "\n".join(lines)


def render_manifest(meetings: list[dict], pull_files: list[str]) -> str:
    pages = []
    meeting_summaries = []
    for meeting in meetings:
        states: dict[str, int] = {}
        for item in meeting["items"]:
            states[item["state"]] = states.get(item["state"], 0) + 1
        shared_state = next(iter(states)) if len(states) == 1 else None
        pages.append(
            {
                "kind": "meeting",
                "meeting_date": meeting["meeting_date"],
                "path": f"/meetings/{meeting['meeting_date']}/",
                "pulled_at": meeting["pulled_at"],
                "raw_files": meeting["raw_files"],
                "source_urls": meeting["source_urls"],
                "state": shared_state,
                "item_states": states,
            }
        )
        for item in meeting["items"]:
            pages.append(
                {
                    "action_name": item["action_name"],
                    "api_matter_id": item["api_matter_id"],
                    "event_id": item["event_id"],
                    "event_item_id": item["event_item_id"],
                    "file_number": item["file_number"],
                    "kind": "item",
                    "legistar_status": item["legistar_status"],
                    "legislation_resolved": item["legislation_resolved"],
                    "legislation_url": item["legislation_url"],
                    "meeting_date": item["meeting_date"],
                    "path": f"/items/{item['file_number']}/",
                    "pulled_at": item["pulled_at"],
                    "raw_files": item["raw_files"],
                    "source_urls": item["source_urls"],
                    "state": item["state"],
                    "state_basis": item["basis"],
                }
            )
        meeting_summaries.append(
            {
                "dropped": meeting["dropped"],
                "dropped_boilerplate": len(meeting["dropped"]),
                "kept": len(meeting["items"]),
                "meeting_date": meeting["meeting_date"],
                "omitted_no_file": len(meeting["omitted_no_file"]),
                "omitted_no_file_titles": [row["title"] for row in meeting["omitted_no_file"]],
                "states": states,
            }
        )
    pages.sort(key=lambda row: row["path"])
    payload = {
        "client": CLIENT,
        "meetings": meeting_summaries,
        "pages": pages,
        "pull_files": pull_files,
        "note": "Page text is generated from data/raw. pulled_at is the pull time, not the build time.",
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render_outputs(meetings: list[dict], pull_files: list[str]) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for meeting in meetings:
        day = meeting["meeting_date"]
        outputs[f"meetings/{day}/index.html"] = render_meeting_html(meeting)
        outputs[f"content/meetings/{day}.md"] = render_meeting_md(meeting)
        for item in meeting["items"]:
            file_number = item["file_number"]
            outputs[f"items/{file_number}/index.html"] = render_item_html(item)
            outputs[f"content/items/{file_number}.md"] = render_item_md(item)
    outputs["data/manifest.json"] = render_manifest(meetings, pull_files)
    for rel, text in list(outputs.items()):
        if not text.endswith("\n"):
            outputs[rel] = text + "\n"
    return outputs


def lint_outputs(outputs: dict[str, str]) -> list[str]:
    problems: list[str] = []
    for rel, text in sorted(outputs.items()):
        if rel.endswith(".html"):
            problems.extend(lint_html(text, label=rel))
    return problems


def owned_files(repo: Path) -> list[str]:
    found: list[str] = []
    for root in OWNED_DIRS:
        base = repo / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file():
                found.append(path.relative_to(repo).as_posix())
    manifest = repo / "data" / "manifest.json"
    if manifest.is_file():
        found.append("data/manifest.json")
    return found


def apply_outputs(repo: Path, outputs: dict[str, str], check: bool) -> int:
    problems = lint_outputs(outputs)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print("Refusing to write pages that fail the neutrality lint.", file=sys.stderr)
        return 1
    diffs: list[str] = []
    expected = set(outputs)
    for rel in owned_files(repo):
        if rel not in expected:
            diffs.append(f"extra {rel}")
            if not check:
                (repo / rel).unlink()
    for rel, text in sorted(outputs.items()):
        path = repo / rel
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current != text:
            diffs.append(rel)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8", newline="\n")
    if check and diffs:
        print("Record pages do not match data/raw. Run: python3 tools/legistar_records.py build", file=sys.stderr)
        for rel in diffs:
            print(f"  {rel}", file=sys.stderr)
        return 1
    return 0


def _read_hashed(repo: Path, record: dict) -> bytes:
    path = repo / record["path"]
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != record["sha256"]:
        raise SystemExit(
            f"Raw file was edited after the pull: {record['path']}\n"
            f"expected {record['sha256']}\nactual   {digest}"
        )
    return data


def meetings_from_pull(repo: Path, pull: dict) -> list[dict]:
    files = pull["files"]
    events_payload = parse_json(_read_hashed(repo, files["events"]), "events")
    events = as_list(events_payload, "events")
    by_id = {int(event["EventId"]): event for event in events if isinstance(event, dict)}
    meetings = []
    raw_shared = [files["events"]["path"]]
    for event_id_s, spec in sorted(pull["event_ids"].items(), key=lambda pair: int(pair[0])):
        event_id = int(event_id_s)
        event = by_id.get(event_id)
        if event is None:
            raise SystemExit(f"Event {event_id} is in the pull index and missing from events JSON")
        items_rec = spec["event_items"]
        items = as_list(parse_json(_read_hashed(repo, items_rec), "event items"), "event items")
        attachments: dict[int, list] = {}
        votes: dict[int, list] = {}
        raw_files = raw_shared + [items_rec["path"]]
        for matter_s, rec in sorted(spec.get("attachments", {}).items(), key=lambda pair: int(pair[0])):
            attachments[int(matter_s)] = as_list(
                parse_json(_read_hashed(repo, rec), "attachments"),
                "attachments",
            )
        for item_s, rec in sorted(spec.get("votes", {}).items(), key=lambda pair: int(pair[0])):
            votes[int(item_s)] = as_list(parse_json(_read_hashed(repo, rec), "votes"), "votes")
        source_urls = [files["events"]["url"], items_rec["url"]]
        meetings.append(
            normalize_event(
                event,
                items,
                attachments,
                votes,
                pull.get("legislation_urls", {}),
                pull["pulled_at"],
                _dedupe(source_urls),
                raw_files,
                attachment_meta=spec.get("attachments", {}),
                vote_meta=spec.get("votes", {}),
            )
        )
    return meetings


def load_meetings(repo: Path) -> tuple[list[dict], list[str]]:
    pull_dir = repo / "data" / "pulls"
    if not pull_dir.is_dir():
        return [], []
    meetings: list[dict] = []
    pull_files: list[str] = []
    seen_days: dict[str, str] = {}
    for path in sorted(pull_dir.glob("*.json")):
        pull = json.loads(path.read_text(encoding="utf-8"))
        rel = path.relative_to(repo).as_posix()
        pull_files.append(rel)
        for meeting in meetings_from_pull(repo, pull):
            day = meeting["meeting_date"]
            if day in seen_days:
                raise SystemExit(
                    f"Meeting {day} is in both {seen_days[day]} and {rel}. Keep one pull."
                )
            seen_days[day] = rel
            meetings.append(meeting)
    meetings.sort(key=lambda row: row["meeting_date"])
    return meetings, pull_files


def summarize(meetings: list[dict]) -> str:
    lines = []
    for meeting in meetings:
        states: dict[str, int] = {}
        for item in meeting["items"]:
            states[item["state"]] = states.get(item["state"], 0) + 1
        lines.append(
            f"{meeting['meeting_date']}: kept {len(meeting['items'])}, "
            f"dropped boilerplate {len(meeting['dropped'])}, "
            f"omitted no file number {len(meeting['omitted_no_file'])}, "
            f"states {states}"
        )
    return "\n".join(lines)


def build_repo(repo: Path, check: bool = False) -> int:
    meetings, pull_files = load_meetings(repo)
    if not meetings:
        extras = [rel for rel in owned_files(repo)]
        if extras:
            print("Record pages exist but data/pulls has no meetings.", file=sys.stderr)
            return 1
        print("No Legistar pulls to build.")
        return 0
    outputs = render_outputs(meetings, pull_files)
    status = apply_outputs(repo, outputs, check)
    print(summarize(meetings))
    if status == 0 and not check:
        print(f"Wrote {len(outputs)} record files.")
    if status == 0 and check:
        print("Record pages match data/raw.")
    return status


def _write_raw(repo: Path, rel: str, url: str, data: bytes) -> dict:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"path": rel, "sha256": hashlib.sha256(data).hexdigest(), "url": url}


def pull(repo: Path, since: date, until: date, body: str) -> int:
    if until < since:
        raise SystemExit("--until is before --since")
    pulled_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    folder = since.isoformat() if since == until else f"{since.isoformat()}_{until.isoformat()}"
    raw_root = f"data/raw/{CLIENT}/{folder}"
    url = events_url(body, since, until)
    print(f"GET {url}", file=sys.stderr)
    events_bytes = fetch_bytes(url)
    events = as_list(parse_json(events_bytes, "events"), "events")
    if not events:
        raise SystemExit(f"No {body} events from {since.isoformat()} through {until.isoformat()}.")

    by_day: dict[str, list[dict]] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        if clean_str(event.get("EventBodyName")) != body:
            continue
        day = clean_str(event.get("EventDate"))[:10]
        by_day.setdefault(day, []).append(event)
    if not by_day:
        raise SystemExit(f"No {body} events in the response.")

    events_rec = _write_raw(repo, f"{raw_root}/events.json", url, events_bytes)
    for day, day_events in sorted(by_day.items()):
        event_ids: dict[str, dict] = {}
        legislation: dict[str, dict] = {}
        for event in day_events:
            event_id = int(event["EventId"])
            items_url = f"{API_BASE}/events/{event_id}/eventitems"
            print(f"GET {items_url}", file=sys.stderr)
            items_bytes = fetch_bytes(items_url)
            items = as_list(parse_json(items_bytes, "event items"), "event items")
            items_rec = _write_raw(
                repo,
                f"{raw_root}/event-{event_id}-items.json",
                items_url,
                items_bytes,
            )
            attachments: dict[str, dict] = {}
            votes: dict[str, dict] = {}
            matter_ids: set[int] = set()
            for item in items:
                if not isinstance(item, dict):
                    continue
                matter_id = item.get("EventItemMatterId")
                event_item_id = item.get("EventItemId")
                if isinstance(matter_id, int) and matter_id > 0:
                    matter_ids.add(matter_id)
                if isinstance(event_item_id, int) and isinstance(matter_id, int) and matter_id > 0:
                    vote_url = f"{API_BASE}/eventitems/{event_item_id}/votes"
                    print(f"GET {vote_url}", file=sys.stderr)
                    vote_bytes = fetch_bytes(vote_url)
                    votes[str(event_item_id)] = _write_raw(
                        repo,
                        f"{raw_root}/eventitem-{event_item_id}-votes.json",
                        vote_url,
                        vote_bytes,
                    )
            for matter_id in sorted(matter_ids):
                att_url = f"{API_BASE}/matters/{matter_id}/attachments"
                print(f"GET {att_url}", file=sys.stderr)
                att_bytes = fetch_bytes(att_url)
                attachments[str(matter_id)] = _write_raw(
                    repo,
                    f"{raw_root}/matter-{matter_id}-attachments.json",
                    att_url,
                    att_bytes,
                )
                print(f"gateway matter {matter_id}", file=sys.stderr)
                legislation[str(matter_id)] = resolve_legislation_url(matter_id)
                if not legislation[str(matter_id)]["resolved"]:
                    print(f"warn: unresolved legislation URL for matter {matter_id}", file=sys.stderr)
            event_ids[str(event_id)] = {
                "attachments": attachments,
                "event_items": items_rec,
                "votes": votes,
            }
        index = {
            "body": body,
            "client": CLIENT,
            "event_ids": event_ids,
            "files": {"events": events_rec},
            "legislation_urls": legislation,
            "meeting_date": day,
            "pulled_at": pulled_at,
            "since": since.isoformat(),
            "until": until.isoformat(),
        }
        index_path = repo / "data" / "pulls" / f"{day}.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        unresolved = sum(1 for row in legislation.values() if not row.get("resolved"))
        print(
            f"Wrote {index_path.relative_to(repo)} "
            f"({len(event_ids)} event(s), unresolved links {unresolved})",
            file=sys.stderr,
        )
    print("Next: python3 tools/legistar_records.py build")
    return 0


def _parse_day(value: str, flag: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"Invalid {flag}: {value!r} (use YYYY-MM-DD)") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="cmd", required=True)

    pull_p = sub.add_parser("pull", help="Download one date window into data/raw.")
    pull_p.add_argument("--since", required=True, help="YYYY-MM-DD, inclusive.")
    pull_p.add_argument("--until", required=True, help="YYYY-MM-DD, inclusive.")
    pull_p.add_argument("--body", default="City Council")

    build_p = sub.add_parser("build", help="Write pages from data/raw. No network.")
    build_p.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if generated files differ from data/raw. Writes nothing.",
    )
    args = parser.parse_args(argv)
    if args.cmd == "pull":
        return pull(
            args.repo,
            _parse_day(args.since, "--since"),
            _parse_day(args.until, "--until"),
            args.body,
        )
    return build_repo(args.repo, check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
