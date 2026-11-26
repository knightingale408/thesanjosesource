#!/usr/bin/env python3
"""Field rules for the Legistar record pages.

State comes only from Legistar fields. The three labels are fixed:

- Agenda only
- Outcome not posted
- Recorded

Matter status (for example "Agenda Ready") and a minutes status of "Draft"
with no minutes file are not outcomes. They never produce "approved".
"""

from __future__ import annotations

import re
from datetime import date

AGENDA_ONLY = "Agenda only"
OUTCOME_NOT_POSTED = "Outcome not posted"
RECORDED = "Recorded"
STATES = (AGENDA_ONLY, OUTCOME_NOT_POSTED, RECORDED)

# Notices the City prints on every agenda. Kept file numbers are everything else.
# "approval of minutes" also matches the longer City titles that insert
# "City Council" or "Council Committee" before "minutes".
# "how to observe" is the San José wording for the watch-the-meeting notice.
DROP_TITLE_RE = re.compile(
    r"(?:"
    r"language\s+access"
    r"|americans?\s+with\s+disabilit"
    r"|american\s+disability\s+act"
    r"|\bada\b"
    r"|levine\s+act"
    r"|how\s+to\s+(?:watch|observe)"
    r"|roll\s+call"
    r"|closed\s+session"
    r"|approval\s+of\s+(?:(?:city\s+council|council\s+committee|council)\s+)?minutes\b"
    r"|draft[-\s]?agenda\s+review"
    r")",
    re.IGNORECASE,
)


def clean_str(value: object) -> str:
    """Return a stripped string. Anything that is not a string is empty."""
    if not isinstance(value, str):
        return ""
    return value.strip()


def flat_text(value: object) -> str:
    """One line of City text, with internal whitespace collapsed."""
    text = clean_str(value).replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", " ", text).strip()


def title_is_boilerplate(title: str) -> bool:
    return bool(DROP_TITLE_RE.search(title or ""))


def agenda_is_final(status: object) -> bool:
    return clean_str(status).casefold() == "final"


def classify_item(title: object, file_number: object) -> str:
    """Return 'boilerplate', 'no_file', or 'keep'."""
    if title_is_boilerplate(flat_text(title)):
        return "boilerplate"
    if not clean_str(file_number):
        return "no_file"
    return "keep"


def record_state(
    *,
    meeting_date: date,
    as_of: date,
    action_name: object,
    minutes_file: object,
    vote_count: int,
) -> str:
    """Derive the page state.

    Recorded when the item has an action name, the meeting has a minutes
    file, or the votes call returned at least one row.

    Otherwise Outcome not posted when the meeting calendar day is before
    the pull date, and Agenda only when that day is still today or ahead.
    Agenda final is not an input: a future non-final agenda is still
    Agenda only, and the agenda status is shown as its own field.
    Minutes status ("Draft") is not an input. A draft with no file does
    not count as minutes.
    """
    if not isinstance(vote_count, int) or isinstance(vote_count, bool):
        raise TypeError("vote_count must be an int")
    if vote_count < 0:
        raise ValueError("vote_count must be >= 0")
    if clean_str(action_name) or clean_str(minutes_file) or vote_count > 0:
        return RECORDED
    if meeting_date < as_of:
        return OUTCOME_NOT_POSTED
    return AGENDA_ONLY


def state_basis(
    *,
    meeting_date: date,
    as_of: date,
    agenda_status: object,
    action_name: object,
    minutes_file: object,
    minutes_status: object,
    vote_count: int,
) -> dict:
    """Machine-readable reason for a state. minutes_status is recorded, not used."""
    state = record_state(
        meeting_date=meeting_date,
        as_of=as_of,
        action_name=action_name,
        minutes_file=minutes_file,
        vote_count=vote_count,
    )
    return {
        "action_name_present": bool(clean_str(action_name)),
        "agenda_final": agenda_is_final(agenda_status),
        "agenda_status": clean_str(agenda_status),
        "as_of": as_of.isoformat(),
        "meeting_date": meeting_date.isoformat(),
        "meeting_date_passed": meeting_date < as_of,
        "minutes_file_present": bool(clean_str(minutes_file)),
        "minutes_status": clean_str(minutes_status),
        "state": state,
        "vote_row_count": vote_count,
    }


def meeting_question(meeting_date: date, as_of: date) -> str:
    verb = "was" if meeting_date < as_of else "is"
    pretty = f"{meeting_date.strftime('%B')} {meeting_date.day}, {meeting_date.year}"
    return f"What {verb} on the San José City Council agenda for {pretty}?"


def item_question(file_number: str) -> str:
    return f"What is file {file_number}?"


def long_date(iso_day: str) -> str:
    value = date.fromisoformat(iso_day)
    return f"{value.strftime('%B')} {value.day}, {value.year}"
