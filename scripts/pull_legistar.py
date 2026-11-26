#!/usr/bin/env python3
"""Pull San José City Council agendas from the public Legistar API.

No API key. Client is sanjose. See scripts/README.md for how to run a date window.

Raw JSON is stored under data/raw/city-council/<date>/ as Legistar returned it.
Kept file numbers become content/items/<file>.md and the meeting becomes
content/meetings/<date>.md. python3 build.py turns those into pages.

A later run compares the new JSON with the stored JSON. If the agenda
publication time or the item set changed, the same URLs stay, and the meeting
page plus any affected item pages gain an "Agenda amended <date>" line.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from record_lib import (  # noqa: E402
    agenda_timestamp_changed,
    boilerplate_match,
    changed_file_numbers,
    clean_text,
    dump_record,
    history_action_names,
    item_signature,
    load_record,
    parse_iso_date,
    record_state,
)

CLIENT = "sanjose"
API_BASE = f"https://webapi.legistar.com/v1/{CLIENT}"
SITE_BASE = "https://sanjose.legistar.com"
USER_AGENT = "TheSanJoseSource/1.0 (+https://thesanjosesource.com)"
PACIFIC = ZoneInfo("America/Los_Angeles")
ROOT = Path(__file__).resolve().parent.parent

GUID_URL_RE = __import__("re").compile(
    r"^https://sanjose\.legistar\.com/LegislationDetail\.aspx\?ID=\d+&GUID=[0-9A-Fa-f-]{36}$"
)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        return None


_NO_REDIRECT = urllib.request.build_opener(_NoRedirect)


def api_get(path: str, params: dict | None = None) -> object:
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params, safe="$,()'")
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise SystemExit(f"Legistar API HTTP {exc.code} for {path}\n{body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Legistar API network error: {exc}") from exc


def iso_date(value: str, flag: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"Invalid {flag}: {value!r} (use YYYY-MM-DD)") from exc


def odata_datetime(value: date) -> str:
    return f"datetime'{value.isoformat()}'"


def fetch_events(body_name: str, since: date, until: date) -> list[dict]:
    """City Council only. Exact match, so Closed Session is a different body."""
    escaped = body_name.replace("'", "''")
    filt = (
        f"EventBodyName eq '{escaped}' and "
        f"EventDate ge {odata_datetime(since)} and "
        f"EventDate le {odata_datetime(until)}"
    )
    data = api_get(
        "/events",
        {"$filter": filt, "$orderby": "EventDate asc"},
    )
    if not isinstance(data, list):
        raise SystemExit(f"Unexpected events payload: {type(data).__name__}")
    return [row for row in data if isinstance(row, dict)]


def fetch_list(path: str) -> list:
    data = api_get(path)
    if data is None:
        return []
    if not isinstance(data, list):
        raise SystemExit(f"Unexpected list payload for {path}: {type(data).__name__}")
    return data


def gateway_url(matter_id: int) -> str:
    return f"{SITE_BASE}/gateway.aspx?M=L&ID={matter_id}"


def resolve_legislation_url(matter_id: int, cache: dict[int, str]) -> str:
    """Website LegislationDetail URL (ID + GUID), not the API MatterId."""
    if matter_id in cache:
        return cache[matter_id]
    req = urllib.request.Request(
        gateway_url(matter_id),
        headers={"User-Agent": USER_AGENT},
    )
    location = ""
    try:
        _NO_REDIRECT.open(req, timeout=60)
    except urllib.error.HTTPError as exc:
        location = exc.headers.get("Location") or ""
        if exc.code in (301, 302, 303, 307, 308) and location:
            full = urllib.parse.urljoin(SITE_BASE + "/", location)
            if GUID_URL_RE.match(full):
                cache[matter_id] = full
                return full
            raise SystemExit(
                f"Matter {matter_id} redirected to a URL that is not a website "
                f"LegislationDetail link with ID and GUID: {full}"
            )
    except urllib.error.URLError as exc:
        raise SystemExit(f"Gateway lookup failed for matter {matter_id}: {exc}") from exc
    raise SystemExit(
        f"Matter {matter_id} did not redirect to a website LegislationDetail URL "
        f"(location {location!r}). Refusing to publish an API id."
    )


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> object | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def event_date(event: dict) -> date:
    raw = str(event.get("EventDate") or "")
    try:
        return parse_iso_date(raw)
    except ValueError as exc:
        raise SystemExit(f"Event {event.get('EventId')} has no EventDate") from exc


def public_attachments(rows: list) -> list[dict[str, str]]:
    """Name and hyperlink, in the City's sort order. No file bytes."""
    usable = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = clean_text(row.get("MatterAttachmentHyperlink"))
        if not url:
            continue
        name = clean_text(row.get("MatterAttachmentName")) or "Attachment"
        sort = row.get("MatterAttachmentSort")
        try:
            sort_key = int(sort)
        except (TypeError, ValueError):
            sort_key = 0
        usable.append((sort_key, name, url))
    usable.sort(key=lambda item: (item[0], item[1]))
    return [{"name": name, "url": url} for _, name, url in usable]


def attachment_signature(rows: list[dict[str, str]]) -> tuple:
    return tuple((row["name"], row["url"]) for row in rows)


def meeting_dir(meeting: date) -> Path:
    return ROOT / "data" / "raw" / "city-council" / meeting.isoformat()


def safe_file_number(file_number: str) -> str:
    if not file_number or "/" in file_number or "\\" in file_number or file_number.startswith("."):
        raise SystemExit(f"Refusing file number {file_number!r} as a page address")
    return file_number


def classify(items: list[dict]) -> tuple[list[dict], list[tuple[str, str]], list[str]]:
    """Return kept items in agenda order, dropped (file, title) rows, and duplicate file numbers."""
    kept: list[dict] = []
    dropped: list[tuple[str, str]] = []
    duplicates: list[str] = []
    seen: set[str] = set()
    ordered = sorted(
        items,
        key=lambda row: (
            row.get("EventItemAgendaSequence") is None,
            row.get("EventItemAgendaSequence") or 0,
            clean_text(row.get("EventItemMatterFile")),
        ),
    )
    for item in ordered:
        title = clean_text(item.get("EventItemTitle"))
        file_number = clean_text(item.get("EventItemMatterFile"))
        if boilerplate_match(title):
            dropped.append((file_number, title))
            continue
        if not file_number:
            continue
        if file_number in seen:
            duplicates.append(file_number)
            continue
        seen.add(file_number)
        kept.append(item)
    return kept, dropped, duplicates


def prior_amended(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return str(load_record(path.read_text(encoding="utf-8")).get("amended") or "")
    except (ValueError, json.JSONDecodeError):
        return ""


def build_meeting_fields(
    event: dict,
    kept: list[dict],
    *,
    state: str,
    as_of: str,
    amended: str,
) -> dict:
    meeting = event_date(event)
    return {
        "kind": "meeting",
        "date": meeting.isoformat(),
        "body": clean_text(event.get("EventBodyName")),
        "state": state,
        "agenda_status": clean_text(event.get("EventAgendaStatusName")),
        "minutes_status": clean_text(event.get("EventMinutesStatusName")),
        "legistar_url": clean_text(event.get("EventInSiteURL")),
        "agenda_pdf": clean_text(event.get("EventAgendaFile")),
        "minutes_pdf": clean_text(event.get("EventMinutesFile")),
        "as_of": as_of,
        "amended": amended,
        "files": [clean_text(item.get("EventItemMatterFile")) for item in kept],
    }


def build_item_fields(
    event: dict,
    item: dict,
    *,
    state: str,
    legistar_url: str,
    attachments: list[dict[str, str]],
    as_of: str,
    amended: str,
) -> dict:
    return {
        "kind": "item",
        "file": safe_file_number(clean_text(item.get("EventItemMatterFile"))),
        "meeting": event_date(event).isoformat(),
        "section": clean_text(item.get("EventItemMatterType")),
        "state": state,
        "agenda_number": clean_text(item.get("EventItemAgendaNumber")),
        "matter_status": clean_text(item.get("EventItemMatterStatus")),
        "title": clean_text(item.get("EventItemTitle")),
        "legistar_url": legistar_url,
        "agenda_pdf": clean_text(event.get("EventAgendaFile")),
        "minutes_pdf": clean_text(event.get("EventMinutesFile")),
        "as_of": as_of,
        "amended": amended,
        "attachments": attachments,
    }


def raw_is_unchanged(
    folder: Path,
    event: dict,
    items: list,
    matter_payloads: dict[int, dict[str, list]],
    vote_payloads: dict[int, list],
) -> bool:
    if read_json(folder / "event.json") != event:
        return False
    if read_json(folder / "eventitems.json") != items:
        return False
    for matter_id, payload in matter_payloads.items():
        base = folder / "matters" / str(matter_id)
        if read_json(base / "attachments.json") != payload["attachments"]:
            return False
        if read_json(base / "histories.json") != payload["histories"]:
            return False
    for event_item_id, votes in vote_payloads.items():
        if read_json(folder / "eventitems" / str(event_item_id) / "votes.json") != votes:
            return False
    return True


def write_raw(
    folder: Path,
    event: dict,
    items: list,
    matter_payloads: dict[int, dict[str, list]],
    vote_payloads: dict[int, list],
) -> None:
    write_json(folder / "event.json", event)
    write_json(folder / "eventitems.json", items)
    for matter_id, payload in matter_payloads.items():
        base = folder / "matters" / str(matter_id)
        write_json(base / "attachments.json", payload["attachments"])
        write_json(base / "histories.json", payload["histories"])
    for event_item_id, votes in vote_payloads.items():
        write_json(folder / "eventitems" / str(event_item_id) / "votes.json", votes)


def signatures_from_items(items: list[dict]) -> dict[str, tuple]:
    sigs: dict[str, tuple] = {}
    for item in items:
        file_number = clean_text(item.get("EventItemMatterFile"))
        if not file_number or title_dropped(item):
            continue
        sigs[file_number] = item_signature(item)
    return sigs


def title_dropped(item: dict) -> bool:
    return boilerplate_match(item.get("EventItemTitle")) is not None


def pull_event(event: dict, *, as_of_stamp: str, link_cache: dict[int, str]) -> dict:
    event_id = int(event["EventId"])
    meeting = event_date(event)
    print(f"Event {event_id} {meeting.isoformat()} {event.get('EventBodyName')}", file=sys.stderr)
    items = fetch_list(f"/events/{event_id}/eventitems")
    folder = meeting_dir(meeting)
    old_event = read_json(folder / "event.json")
    old_items = read_json(folder / "eventitems.json")
    had_raw = isinstance(old_event, dict) and isinstance(old_items, list)

    matter_ids: list[int] = []
    seen_matters: set[int] = set()
    for item in items:
        matter_id = item.get("EventItemMatterId")
        if not matter_id:
            continue
        matter_id = int(matter_id)
        if matter_id in seen_matters:
            continue
        seen_matters.add(matter_id)
        matter_ids.append(matter_id)

    matter_payloads: dict[int, dict[str, list]] = {}
    for matter_id in matter_ids:
        print(f"  matter {matter_id} attachments and histories", file=sys.stderr)
        matter_payloads[matter_id] = {
            "attachments": fetch_list(f"/matters/{matter_id}/attachments"),
            "histories": fetch_list(f"/matters/{matter_id}/histories"),
        }

    vote_payloads: dict[int, list] = {}
    for item in items:
        if not item.get("EventItemMatterId") or not item.get("EventItemId"):
            continue
        event_item_id = int(item["EventItemId"])
        if event_item_id in vote_payloads:
            continue
        vote_payloads[event_item_id] = fetch_list(f"/eventitems/{event_item_id}/votes")

    kept, dropped, duplicates = classify(items)
    content_ready = (ROOT / "content" / "meetings" / f"{meeting.isoformat()}.md").is_file()
    if content_ready and raw_is_unchanged(folder, event, items, matter_payloads, vote_payloads):
        print(f"  no change in stored JSON for {meeting.isoformat()}", file=sys.stderr)
        return {
            "date": meeting.isoformat(),
            "kept": len(kept),
            "dropped": dropped,
            "states": {},
            "unchanged": True,
            "notes": [],
        }

    as_of_date = datetime.fromisoformat(as_of_stamp).date()
    minutes_file = clean_text(event.get("EventMinutesFile"))
    notes: list[str] = []
    if duplicates:
        notes.append("Duplicate file numbers on this agenda, first row kept: " + ", ".join(duplicates))
    if clean_text(event.get("EventMinutesStatusName")) and not minutes_file:
        notes.append(
            f"Minutes status is {clean_text(event.get('EventMinutesStatusName'))} and EventMinutesFile is empty."
        )
    agenda_file = clean_text(event.get("EventAgendaFile"))
    if "amended" in agenda_file.lower() and not had_raw:
        notes.append(
            "Agenda PDF file name includes 'Amended', and this is the first stored pull, "
            "so the pages do not add an Agenda amended line."
        )

    old_sigs: dict[str, tuple] = {}
    if had_raw:
        old_sigs = signatures_from_items(old_items)  # type: ignore[arg-type]
    new_sigs = signatures_from_items(kept)
    # Attachment changes count too, for kept file numbers.
    old_attachment_sigs: dict[str, tuple] = {}
    new_attachment_sigs: dict[str, tuple] = {}
    for item in kept:
        matter_id = int(item["EventItemMatterId"])
        file_number = clean_text(item.get("EventItemMatterFile"))
        new_attachment_sigs[file_number] = attachment_signature(
            public_attachments(matter_payloads[matter_id]["attachments"])
        )
    if had_raw:
        for item in old_items:  # type: ignore[union-attr]
            if not isinstance(item, dict) or title_dropped(item):
                continue
            file_number = clean_text(item.get("EventItemMatterFile"))
            matter_id = item.get("EventItemMatterId")
            if not file_number or not matter_id:
                continue
            old_rows = read_json(folder / "matters" / str(int(matter_id)) / "attachments.json")
            if isinstance(old_rows, list):
                old_attachment_sigs[file_number] = attachment_signature(public_attachments(old_rows))

    affected = changed_file_numbers(old_sigs, new_sigs) if had_raw else set()
    if had_raw:
        for file_number in set(old_attachment_sigs) | set(new_attachment_sigs):
            if old_attachment_sigs.get(file_number) != new_attachment_sigs.get(file_number):
                affected.add(file_number)

    published = clean_text(event.get("EventAgendaLastPublishedUTC"))
    amended_date = published[:10] if published else as_of_date.isoformat()
    agenda_changed = had_raw and (
        agenda_timestamp_changed(old_event if isinstance(old_event, dict) else None, event)
        or bool(affected)
    )
    meeting_amended = amended_date if agenda_changed else ""

    item_states: dict[str, str] = {}
    any_recorded = False
    prepared: list[tuple[dict, str, list[dict[str, str]], str]] = []
    for item in kept:
        matter_id = int(item["EventItemMatterId"])
        event_item_id = int(item["EventItemId"])
        file_number = safe_file_number(clean_text(item.get("EventItemMatterFile")))
        histories = matter_payloads[matter_id]["histories"]
        votes = vote_payloads.get(event_item_id) or []
        state = record_state(
            meeting,
            as_of_date,
            action_name=clean_text(item.get("EventItemActionName")),
            minutes_file=minutes_file,
            vote_rows=votes if isinstance(votes, list) else [],
            history_action_names=history_action_names(histories),
        )
        if state == "Recorded":
            any_recorded = True
        item_states[file_number] = state
        legistar_url = resolve_legislation_url(matter_id, link_cache)
        attachments = public_attachments(matter_payloads[matter_id]["attachments"])
        if file_number in affected:
            item_amended = amended_date
        else:
            item_amended = prior_amended(ROOT / "content" / "items" / f"{file_number}.md")
        prepared.append((item, state, attachments, item_amended, legistar_url))

    if any_recorded:
        meeting_state = "Recorded"
    else:
        meeting_state = record_state(
            meeting,
            as_of_date,
            action_name="",
            minutes_file=minutes_file,
            vote_rows=[],
        )

    # Removed file numbers keep their URL and gain the amended line.
    removed = set(old_sigs) - set(new_sigs) if had_raw else set()

    write_raw(folder, event, items, matter_payloads, vote_payloads)

    meeting_path = ROOT / "content" / "meetings" / f"{meeting.isoformat()}.md"
    items_dir = ROOT / "content" / "items"
    items_dir.mkdir(parents=True, exist_ok=True)
    meeting_path.parent.mkdir(parents=True, exist_ok=True)
    if not agenda_changed:
        meeting_amended = prior_amended(meeting_path)
    meeting_path.write_text(
        dump_record(
            build_meeting_fields(
                event,
                kept,
                state=meeting_state,
                as_of=as_of_stamp,
                amended=meeting_amended,
            )
        ),
        encoding="utf-8",
    )

    for item, state, attachments, item_amended, legistar_url in prepared:
        file_number = clean_text(item.get("EventItemMatterFile"))
        path = items_dir / f"{file_number}.md"
        if not agenda_changed:
            item_amended = prior_amended(path)
        path.write_text(
            dump_record(
                build_item_fields(
                    event,
                    item,
                    state=state,
                    legistar_url=legistar_url,
                    attachments=attachments,
                    as_of=as_of_stamp,
                    amended=item_amended,
                )
            ),
            encoding="utf-8",
        )

    for file_number in sorted(removed):
        path = items_dir / f"{file_number}.md"
        if not path.is_file():
            continue
        fields = load_record(path.read_text(encoding="utf-8"))
        fields["amended"] = amended_date
        fields["as_of"] = as_of_stamp
        path.write_text(dump_record(fields), encoding="utf-8")
        notes.append(f"{file_number} is no longer on this agenda. The same URL was kept.")

    return {
        "date": meeting.isoformat(),
        "kept": len(kept),
        "dropped": dropped,
        "states": item_states,
        "meeting_state": meeting_state,
        "unchanged": False,
        "notes": notes,
        "agenda_status": clean_text(event.get("EventAgendaStatusName")),
        "minutes_status": clean_text(event.get("EventMinutesStatusName")),
        "agenda_published": published,
    }


def print_summary(summaries: list[dict]) -> None:
    for summary in summaries:
        print(f"Meeting {summary['date']}")
        if summary.get("unchanged"):
            print("  Stored JSON unchanged. Content pages left as they were.")
        else:
            print(f"  Agenda status: {summary.get('agenda_status') or '—'}")
            print(f"  Minutes status: {summary.get('minutes_status') or '—'}")
            print(f"  Agenda last published: {summary.get('agenda_published') or '—'}")
            print(f"  Meeting state: {summary.get('meeting_state')}")
        print(f"  Kept: {summary['kept']}")
        print(f"  Dropped: {len(summary['dropped'])}")
        for file_number, title in summary["dropped"]:
            label = file_number or "(no file number)"
            print(f"    - {label}: {title}")
        states = summary.get("states") or {}
        if states:
            counts: dict[str, int] = {}
            for state in states.values():
                counts[state] = counts.get(state, 0) + 1
            print("  Item states: " + ", ".join(f"{name} {count}" for name, count in sorted(counts.items())))
        for note in summary.get("notes") or []:
            print(f"  Note: {note}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", required=True, help="First EventDate, YYYY-MM-DD, inclusive.")
    parser.add_argument("--until", required=True, help="Last EventDate, YYYY-MM-DD, inclusive.")
    parser.add_argument(
        "--body",
        default="City Council",
        help="Exact EventBodyName. Default: City Council.",
    )
    args = parser.parse_args(argv)
    since = iso_date(args.since, "--since")
    until = iso_date(args.until, "--until")
    if until < since:
        raise SystemExit("--until is before --since")

    as_of_stamp = datetime.now(PACIFIC).replace(microsecond=0).isoformat()
    print(
        f"Fetching {args.body!r} from {since.isoformat()} through {until.isoformat()}",
        file=sys.stderr,
    )
    events = fetch_events(args.body, since, until)
    print(f"Events: {len(events)}", file=sys.stderr)
    if not events:
        print("No events in that window.")
        return 0

    link_cache: dict[int, str] = {}
    summaries = [pull_event(event, as_of_stamp=as_of_stamp, link_cache=link_cache) for event in events]
    print_summary(summaries)
    print("Next: python3 build.py", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
