#!/usr/bin/env python3
"""Check whether Legistar has posted results for a meeting's items.

Answers "has the City posted what happened yet?" without clicking through
Legistar by hand. For each agenda item it prints the recorded action and
pass/fail flag, or NOT POSTED when the City hasn't entered one yet, plus
whether the meeting's minutes PDF is up.

A blank result only means Legistar has no entry yet. It does not prove the
item wasn't acted on: check the minutes and the meeting video before
saying so in a brief.

Examples:
  python3 tools/check_results.py --date 2026-10-20
  python3 tools/check_results.py --date 2026-10-20 --file 26-1076
  python3 tools/check_results.py --date 2026-10-20 --body "City Council" --all

Working tool only; never published (tools/ is excluded from the site).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

API_BASE = "https://webapi.legistar.com/v1/sanjose"
SITE_BASE = "https://sanjose.legistar.com"
USER_AGENT = "TheSanJoseSource/1.0 (+https://thesanjosesource.com)"


def api_get(path: str, params: dict | None = None) -> object:
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params, safe="$,()'")
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.load(resp)
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise SystemExit(f"Legistar API error for {url}: {exc}") from exc


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--date", required=True, help="Meeting date, YYYY-MM-DD.")
    p.add_argument("--body", default="City Council", help='Meeting body (default: "City Council").')
    p.add_argument("--file", action="append", default=[], help="Only these file numbers, e.g. 26-1076 (repeatable).")
    p.add_argument("--all", action="store_true", help="Include items with no file number (headers, ceremonial items).")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        day = date.fromisoformat(args.date)
    except ValueError:
        raise SystemExit(f"Invalid --date {args.date!r}; use YYYY-MM-DD")

    body = args.body.replace("'", "''")
    events = api_get("/Events", {
        "$filter": f"EventDate eq datetime'{day.isoformat()}' and EventBodyName eq '{body}'",
    })
    if not isinstance(events, list) or not events:
        print(f"No {args.body} meeting found on {day}.")
        return 1

    wanted = {f.strip() for f in args.file}
    for ev in events:
        print(f"{ev.get('EventBodyName')} — {day} {ev.get('EventTime') or ''}".rstrip())
        print(f"Meeting: {ev.get('EventInSiteURL') or SITE_BASE + '/Calendar.aspx'}")
        minutes = ev.get("EventMinutesFile")
        print(f"Minutes PDF: {minutes if minutes else 'NOT POSTED'}")
        print()
        items = api_get(f"/Events/{ev['EventId']}/EventItems")
        if not isinstance(items, list):
            continue
        posted = missing = 0
        for it in items:
            fileno = (it.get("EventItemMatterFile") or "").strip()
            if wanted and fileno not in wanted:
                continue
            if not fileno and not args.all:
                continue
            action = (it.get("EventItemActionName") or "").strip()
            passed = (it.get("EventItemPassedFlagName") or "").strip()
            title = " ".join((it.get("EventItemTitle") or "").split())[:110]
            num = (it.get("EventItemAgendaNumber") or "").strip()
            if action or passed:
                posted += 1
                result = "; ".join(x for x in (action, passed) if x)
            else:
                missing += 1
                result = "NOT POSTED"
            label = " ".join(x for x in (num, fileno) if x)
            print(f"  {label:<18} {result:<34} {title}")
        print()
        print(f"Results posted: {posted} · not posted yet: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
