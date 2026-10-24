#!/usr/bin/env python3
"""Pull high-impact San José Legistar agenda items into dated Markdown.

Uses the public Legistar Web API (no token required for sanjose).
Focus categories: budget, housing, fees, public safety.

Examples:
  python3 tools/legistar_pull.py
  python3 tools/legistar_pull.py --days 45 --body "City Council" --json
  python3 tools/legistar_pull.py --since 2026-10-26 --until 2026-10-27

Links: the Legistar Web API's MatterId/MatterGuid are NOT the IDs the
sanjose.legistar.com website uses, so links built from them break
("Invalid parameters!"). This script asks Legistar's gateway
(gateway.aspx?M=L&ID=<MatterId>) where each item lives and stores the
full website URL with its ID and GUID, per the house link rule. If that
lookup fails, the item is marked UNRESOLVED and gets the gateway link,
which still opens the right page but must be replaced before publishing.

Output is a working file for drafting. It is never published: tools/ and
research/ are excluded from the site by .github/scripts/publish.py.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

CLIENT = "sanjose"
API_BASE = f"https://webapi.legistar.com/v1/{CLIENT}"
SITE_BASE = "https://sanjose.legistar.com"
USER_AGENT = "TheSanJoseSource/1.0 (+https://thesanjosesource.com)"

# Category -> compiled patterns (title / matter name / type)
CATEGORY_PATTERNS: dict[str, re.Pattern[str]] = {
    "budget": re.compile(
        r"\b("
        r"budget|appropriat(?:e|ion|ions)?|general\s+fund|fiscal(\s+year)?|"
        r"operating\s+budget|capital\s+improv|CIP\b|bond\s+issu|"
        r"year[- ]end\s+budget|mid[- ]year\s+budget|reserve\s+polic|"
        r"financ(?:e|ing)\s+tool|infrastructure\s+financ"
        r")\b",
        re.I,
    ),
    "housing": re.compile(
        r"\b("
        r"hous(?:e|ing)|affordable\s+hous|homeless(?:ness)?|homekey|"
        r"rent(?:al|s)?\b|ADU\b|accessory\s+dwelling|shelter|"
        r"inclusionary|tenant\s+protect|eviction"
        r")\b",
        re.I,
    ),
    "fees": re.compile(
        r"\b("
        r"fees?|fee\s+schedul|tax(?:es|ation)?|levy|levies|"
        r"assessment|surcharge|utility\s+rate|rate\s+increas|"
        r"community\s+facilities\s+district|CFD\b"
        r")\b",
        re.I,
    ),
    "public_safety": re.compile(
        r"\b("
        r"police|fire\s+department|firefighter|public\s+safety|"
        r"emergency\s+servic|911\b|crime|sheriff|EMS\b|"
        r"independent\s+police\s+auditor|police\s+auditor|"
        r"wildfire|flood\s+protect"
        r")\b",
        re.I,
    ),
}

CATEGORY_PATTERNS["spending"] = re.compile(
    r"\b("
    r"loan|grant|contracts?|agreements?|memorandum\s+of\s+(?:agreement|understanding)|"
    r"purchase|procure(?:ment)?|award|amendment|"
    r"labor|bargaining|salar(?:y|ies)|compensation|wages?|"
    r"financing|refinanc\w*|bonds?|"
    r"\d{4,5}\s*-\s*[A-Z]{2,}(?=:)|"  # numbered capital projects, e.g. "10242 - PARK:"
    r"not[- ]to[- ]exceed|\$\s?\d"
    r")\b",
    re.I,
)

CATEGORY_LABELS = {
    "spending": "Contracts & spending",
    "budget": "Budget",
    "housing": "Housing",
    "fees": "Fees",
    "public_safety": "Public safety",
}


@dataclass
class Hit:
    event_id: int
    event_date: str
    event_body: str
    event_url: str
    agenda_file: str | None
    minutes_file: str | None
    matter_id: int
    matter_guid: str
    matter_file: str
    title: str
    matter_type: str
    matter_status: str
    action: str
    passed: str
    categories: list[str] = field(default_factory=list)

    legislation_url: str = ""
    link_resolved: bool = False


def api_get(path: str, params: dict | None = None) -> object:
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params, safe="$,()'")
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise SystemExit(f"Legistar API HTTP {exc.code} for {url}\n{body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Legistar API network error: {exc}") from exc


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--days",
        type=int,
        default=30,
        help="Look back this many days from today (ignored if --since set).",
    )
    p.add_argument(
        "--since",
        type=str,
        default="",
        help="ISO date YYYY-MM-DD lower bound for EventDate.",
    )
    p.add_argument(
        "--until",
        type=str,
        default="",
        help="ISO date YYYY-MM-DD upper bound for EventDate (inclusive).",
    )
    p.add_argument(
        "--body",
        action="append",
        default=[],
        help="Event body name filter (repeatable). Default: City Council.",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("research/pulls"),
        help="Output directory for dated Markdown.",
    )
    p.add_argument(
        "--date",
        type=str,
        default="",
        help="Pull date stamp in filename (default: today UTC).",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Also write a .json sidecar next to the Markdown.",
    )
    return p.parse_args()


def iso_date(value: str, flag: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"Invalid {flag}: {value!r} (use YYYY-MM-DD)") from exc


def classify(text: str) -> list[str]:
    return [name for name, pattern in CATEGORY_PATTERNS.items() if pattern.search(text)]


def odata_datetime(d: date) -> str:
    return f"datetime'{d.isoformat()}'"


def fetch_events(bodies: list[str], since: date, until: date) -> list[dict]:
    clauses = [
        f"EventDate ge {odata_datetime(since)}",
        f"EventDate le {odata_datetime(until)}",
    ]
    if len(bodies) == 1:
        clauses.append(f"EventBodyName eq '{bodies[0].replace(chr(39), chr(39)*2)}'")
    elif bodies:
        body_clause = " or ".join(
            f"EventBodyName eq '{b.replace(chr(39), chr(39)*2)}'" for b in bodies
        )
        clauses.append(f"({body_clause})")

    params = {
        "$filter": " and ".join(clauses),
        "$orderby": "EventDate desc",
        "$top": "100",
    }
    data = api_get("/Events", params)
    if not isinstance(data, list):
        raise SystemExit(f"Unexpected Events payload: {type(data)}")
    return data


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


_NO_REDIRECT = urllib.request.build_opener(_NoRedirect)
GUID_URL_RE = re.compile(
    r"^https://sanjose\.legistar\.com/LegislationDetail\.aspx\?ID=\d+&GUID=[0-9A-Fa-f-]{36}$"
)


def gateway_url(matter_id: int) -> str:
    return f"{SITE_BASE}/gateway.aspx?M=L&ID={matter_id}"


def resolve_legislation_url(matter_id: int, cache: dict[int, tuple[str, bool]]) -> tuple[str, bool]:
    """Return (url, resolved). resolved=True means a full website ID+GUID URL."""
    if matter_id in cache:
        return cache[matter_id]
    gw = gateway_url(matter_id)
    result = (gw, False)
    req = urllib.request.Request(gw, headers={"User-Agent": USER_AGENT})
    try:
        _NO_REDIRECT.open(req, timeout=60)
    except urllib.error.HTTPError as exc:
        location = exc.headers.get("Location") or ""
        if exc.code in (301, 302, 303, 307, 308) and location:
            full = urllib.parse.urljoin(SITE_BASE + "/", location)
            if GUID_URL_RE.match(full):
                result = (full, True)
    except urllib.error.URLError as exc:
        print(f"warn: gateway lookup failed for matter {matter_id}: {exc}", file=sys.stderr)
    cache[matter_id] = result
    return result


def collect_hits(events: list[dict]) -> list[Hit]:
    hits: list[Hit] = []
    seen: set[tuple[int, int]] = set()
    link_cache: dict[int, tuple[str, bool]] = {}

    for event in events:
        event_id = int(event["EventId"])
        detail = api_get(
            f"/Events/{event_id}",
            {
                "EventItems": "1",
                "AgendaNote": "1",
                "MinutesNote": "1",
                "EventItemAttachments": "1",
            },
        )
        if not isinstance(detail, dict):
            continue
        items = detail.get("EventItems") or []
        event_date = str(detail.get("EventDate") or event.get("EventDate") or "")[:10]
        event_url = (
            detail.get("EventInSiteURL")
            or event.get("EventInSiteURL")
            or f"{SITE_BASE}/MeetingDetail.aspx?LEGID={event_id}"
        )
        for item in items:
            matter_id = item.get("EventItemMatterId")
            if not matter_id:
                continue
            title = (item.get("EventItemTitle") or "").strip()
            matter_name = (item.get("EventItemMatterName") or "").strip()
            matter_type = (item.get("EventItemMatterType") or "").strip()
            blob = "\n".join([title, matter_name, matter_type])
            cats = classify(blob)
            if not cats:
                continue
            key = (event_id, int(matter_id))
            if key in seen:
                continue
            seen.add(key)
            url, resolved = resolve_legislation_url(int(matter_id), link_cache)
            hits.append(
                Hit(
                    event_id=event_id,
                    event_date=event_date,
                    event_body=str(detail.get("EventBodyName") or event.get("EventBodyName") or ""),
                    event_url=str(event_url),
                    agenda_file=detail.get("EventAgendaFile") or event.get("EventAgendaFile"),
                    minutes_file=detail.get("EventMinutesFile") or event.get("EventMinutesFile"),
                    matter_id=int(matter_id),
                    matter_guid=str(item.get("EventItemMatterGuid") or ""),
                    matter_file=str(item.get("EventItemMatterFile") or ""),
                    title=title or matter_name or "(untitled)",
                    matter_type=matter_type,
                    matter_status=str(item.get("EventItemMatterStatus") or ""),
                    action=str(item.get("EventItemActionName") or ""),
                    passed=str(item.get("EventItemPassedFlagName") or ""),
                    categories=cats,
                    legislation_url=url,
                    link_resolved=resolved,
                )
            )
    hits.sort(key=lambda h: (h.event_date, h.matter_file, h.title), reverse=True)
    return hits


def render_markdown(
    hits: list[Hit],
    *,
    pull_date: date,
    since: date,
    until: date,
    bodies: list[str],
) -> str:
    lines: list[str] = []
    lines.append(f"# Legistar pull — {pull_date.isoformat()}")
    lines.append("")
    lines.append(
        f"High-impact City of San José agenda items from Legistar "
        f"({', '.join(bodies)}), {since.isoformat()} through {until.isoformat()}."
    )
    lines.append("")
    lines.append("Categories: **Budget**, **Housing**, **Fees**, **Public safety**, **Contracts & spending**.")
    lines.append("")
    lines.append(f"- Calendar: {SITE_BASE}/Calendar.aspx")
    lines.append(f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"- Matches: {len(hits)}")
    unresolved = sum(1 for h in hits if not h.link_resolved)
    if unresolved:
        lines.append(f"- UNRESOLVED links: {unresolved} (fix before any of these go in a brief)")
    lines.append("")

    if not hits:
        lines.append("_No matching items in this window._")
        lines.append("")
        return "\n".join(lines)

    by_date: dict[str, list[Hit]] = {}
    for hit in hits:
        by_date.setdefault(hit.event_date, []).append(hit)

    for event_date in sorted(by_date.keys(), reverse=True):
        day_hits = by_date[event_date]
        body = day_hits[0].event_body
        lines.append(f"## {event_date} — {body}")
        lines.append("")
        lines.append(f"- Meeting: {day_hits[0].event_url}")
        if day_hits[0].agenda_file:
            lines.append(f"- Agenda PDF: {day_hits[0].agenda_file}")
        if day_hits[0].minutes_file:
            lines.append(f"- Minutes PDF: {day_hits[0].minutes_file}")
        lines.append("")
        for hit in day_hits:
            labels = ", ".join(CATEGORY_LABELS[c] for c in hit.categories)
            file_label = hit.matter_file or f"Matter {hit.matter_id}"
            lines.append(f"### {file_label}")
            lines.append("")
            lines.append(hit.title)
            lines.append("")
            lines.append(f"- Categories: {labels}")
            if hit.matter_type:
                lines.append(f"- Type: {hit.matter_type}")
            if hit.matter_status:
                lines.append(f"- Status: {hit.matter_status}")
            if hit.action:
                action_bits = [hit.action]
                if hit.passed:
                    action_bits.append(hit.passed)
                lines.append(f"- Action: {'; '.join(action_bits)}")
            if hit.link_resolved:
                lines.append(f"- Source: {hit.legislation_url}")
            else:
                lines.append(
                    f"- Source (UNRESOLVED, replace with full ID+GUID URL before publishing): "
                    f"{hit.legislation_url}"
                )
            lines.append("")
    return "\n".join(lines)


def hits_to_json(hits: list[Hit]) -> list[dict]:
    out = []
    for h in hits:
        out.append(
            {
                "event_id": h.event_id,
                "event_date": h.event_date,
                "event_body": h.event_body,
                "event_url": h.event_url,
                "agenda_file": h.agenda_file,
                "minutes_file": h.minutes_file,
                "api_matter_id": h.matter_id,
                "api_matter_guid": h.matter_guid,
                "matter_file": h.matter_file,
                "title": h.title,
                "matter_type": h.matter_type,
                "matter_status": h.matter_status,
                "action": h.action,
                "passed": h.passed,
                "categories": h.categories,
                "legislation_url": h.legislation_url,
                "link_resolved": h.link_resolved,
            }
        )
    return out


def main() -> int:
    args = parse_args()
    bodies = args.body or ["City Council"]
    today = datetime.now(timezone.utc).date()
    pull_date = iso_date(args.date, "--date") if args.date else today
    until = iso_date(args.until, "--until") if args.until else today + timedelta(days=21)
    if args.since:
        since = iso_date(args.since, "--since")
    else:
        since = today - timedelta(days=max(args.days, 0))

    print(f"Fetching events for {bodies} from {since} to {until}…", file=sys.stderr)
    events = fetch_events(bodies, since, until)
    print(f"Events: {len(events)}", file=sys.stderr)
    hits = collect_hits(events)
    print(f"High-impact matches: {len(hits)}", file=sys.stderr)
    unresolved = sum(1 for h in hits if not h.link_resolved)
    if unresolved:
        print(f"warn: {unresolved} link(s) unresolved; see the pull file", file=sys.stderr)

    args.out.mkdir(parents=True, exist_ok=True)
    md_path = args.out / f"{pull_date.isoformat()}-legistar-pull.md"
    md = render_markdown(hits, pull_date=pull_date, since=since, until=until, bodies=bodies)
    md_path.write_text(md, encoding="utf-8")
    print(f"Wrote {md_path}", file=sys.stderr)

    if args.json:
        json_path = args.out / f"{pull_date.isoformat()}-legistar-pull.json"
        json_path.write_text(
            json.dumps(hits_to_json(hits), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {json_path}", file=sys.stderr)

    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
