#!/usr/bin/env python3
"""Shared rules for the Legistar record site.

The pull script, the page renderer, and the tests all use this module.
It does not talk to the network. State comes from fields, not from prose.

Edit DROP_TITLE_PATTERNS to change which titles are left off the site.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime

STATE_AGENDA_ONLY = "Agenda only"
STATE_OUTCOME_NOT_POSTED = "Outcome not posted"
STATE_RECORDED = "Recorded"

# One list. A title is boilerplate when any pattern matches (case-insensitive).
# "ADA" is a whole word so it does not catch unrelated words.
# "approval of minutes" also matches the City's longer titles, such as
# "Approval of City Council Minutes" and "Approval of Council Committee Minutes".
# "draft-agenda review" also matches "draft agenda review".
DROP_TITLE_PATTERNS: tuple[str, ...] = (
    "language access",
    r"\bADA\b",
    "Levine Act",
    "how to watch",
    "roll call",
    "closed session",
    r"approval of (?:city council |council committee )?minutes",
    r"draft[-\s]agenda review",
)

_DROP_COMPILED = tuple(re.compile(pattern, re.IGNORECASE) for pattern in DROP_TITLE_PATTERNS)


def clean_text(value: object) -> str:
    """Collapse whitespace. Does not change words."""
    return " ".join(str(value or "").split())


def boilerplate_match(title: object) -> str | None:
    """Return the drop-list pattern that matches this title, or None."""
    text = clean_text(title)
    if not text:
        return None
    for pattern, compiled in zip(DROP_TITLE_PATTERNS, _DROP_COMPILED):
        if compiled.search(text):
            return pattern
    return None


def title_is_boilerplate(title: object) -> bool:
    return boilerplate_match(title) is not None


def _nonempty(value: object) -> str:
    return str(value or "").strip()


def record_state(
    meeting_date: date,
    as_of: date,
    *,
    action_name: str = "",
    minutes_file: str = "",
    vote_rows: list | None = None,
    history_action_names: list[str] | None = None,
) -> str:
    """State from fields only.

    Recorded when an action name, a minutes file, or vote rows exist.
    History contributes only through an action-name field, never through
    a sentence. A past meeting with none of those is Outcome not posted.
    A meeting that is today or still ahead, with none of those, is Agenda only.
    """
    names = [_nonempty(action_name)]
    names.extend(_nonempty(name) for name in (history_action_names or []))
    has_action = any(names)
    has_minutes = bool(_nonempty(minutes_file))
    has_votes = bool(vote_rows)
    if has_action or has_minutes or has_votes:
        return STATE_RECORDED
    if meeting_date < as_of:
        return STATE_OUTCOME_NOT_POSTED
    return STATE_AGENDA_ONLY


def history_action_names(rows: list | None) -> list[str]:
    """Action-name fields from matter histories. Action text is ignored."""
    names: list[str] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        name = _nonempty(row.get("MatterHistoryActionName"))
        if name:
            names.append(name)
    return names


def long_date(value: date) -> str:
    """November 17, 2026."""
    return value.strftime("%B %d, %Y").replace(" 0", " ")


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def format_as_of(value: str) -> str:
    """Render a stored timestamp as a Pacific as-of line."""
    text = value.strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return text
    if parsed.tzinfo is None:
        # Stored values from the pull include an offset. A bare date is a date.
        if len(text) <= 10:
            return long_date(parsed.date())
        return long_date(parsed.date())
    try:
        from zoneinfo import ZoneInfo

        parsed = parsed.astimezone(ZoneInfo("America/Los_Angeles"))
    except Exception:
        pass
    clock = parsed.strftime("%I:%M %p").lstrip("0")
    clock = clock.replace("AM", "a.m.").replace("PM", "p.m.")
    return f"{long_date(parsed.date())}, {clock} Pacific"


def amended_label(value: str) -> str:
    """The fixed re-pull line. Empty when there is no amendment date."""
    text = (value or "").strip()
    if not text:
        return ""
    try:
        shown = long_date(parse_iso_date(text))
    except ValueError:
        shown = text
    return f"Agenda amended {shown}."


def dump_record(fields: dict) -> str:
    """Front matter. Every value is JSON so titles can contain colons."""
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def load_record(text: str) -> dict:
    if not text.startswith("---"):
        raise ValueError("Record file must begin with --- front matter ---")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Unclosed front matter")
    fields: dict = {}
    for line in parts[1].strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, raw = line.split(":", 1)
        fields[key.strip()] = json.loads(raw.strip())
    return fields


def item_signature(item: dict) -> tuple:
    """Fields that mean the agenda line itself changed."""
    return (
        clean_text(item.get("EventItemMatterFile")),
        clean_text(item.get("EventItemTitle")),
        clean_text(item.get("EventItemAgendaNumber")),
        clean_text(item.get("EventItemMatterType")),
        clean_text(item.get("EventItemMatterStatus")),
        clean_text(item.get("EventItemActionName")),
    )


def agenda_timestamp_changed(old_event: dict | None, new_event: dict | None) -> bool:
    if not old_event or not new_event:
        return False
    return (old_event.get("EventAgendaLastPublishedUTC") or "") != (
        new_event.get("EventAgendaLastPublishedUTC") or ""
    )


def changed_file_numbers(old_sigs: dict[str, tuple], new_sigs: dict[str, tuple]) -> set[str]:
    """File numbers added, removed, or changed between two pulls."""
    changed: set[str] = set()
    for file_number in set(old_sigs) | set(new_sigs):
        if old_sigs.get(file_number) != new_sigs.get(file_number):
            changed.add(file_number)
    return changed
