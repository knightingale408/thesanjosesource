"""State machine and boilerplate filter. No network."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import record_rules as rules


def test_outcome_not_posted_when_the_day_passed_and_fields_are_empty():
    state = rules.record_state(
        meeting_date=date(2026, 11, 17),
        as_of=date(2026, 11, 26),
        action_name=None,
        minutes_file=None,
        vote_count=0,
    )
    assert state == "Outcome not posted"


def test_draft_minutes_status_is_not_an_outcome():
    basis = rules.state_basis(
        meeting_date=date(2026, 11, 17),
        as_of=date(2026, 11, 26),
        agenda_status="Final",
        action_name="",
        minutes_file=None,
        minutes_status="Draft",
        vote_count=0,
    )
    assert basis["minutes_status"] == "Draft"
    assert basis["minutes_file_present"] is False
    assert basis["agenda_final"] is True
    assert basis["state"] == "Outcome not posted"


def test_agenda_only_when_the_meeting_is_ahead():
    assert (
        rules.record_state(
            meeting_date=date(2026, 12, 1),
            as_of=date(2026, 11, 26),
            action_name=None,
            minutes_file=None,
            vote_count=0,
        )
        == "Agenda only"
    )


def test_same_day_pull_stays_agenda_only():
    assert (
        rules.record_state(
            meeting_date=date(2026, 11, 17),
            as_of=date(2026, 11, 17),
            action_name=None,
            minutes_file=None,
            vote_count=0,
        )
        == "Agenda only"
    )


def test_future_non_final_agenda_is_still_agenda_only():
    basis = rules.state_basis(
        meeting_date=date(2026, 12, 8),
        as_of=date(2026, 11, 26),
        agenda_status="Draft",
        action_name=None,
        minutes_file=None,
        minutes_status="",
        vote_count=0,
    )
    assert basis["agenda_final"] is False
    assert basis["state"] == "Agenda only"


def test_action_name_minutes_file_or_votes_are_recorded():
    past = dict(meeting_date=date(2026, 11, 17), as_of=date(2026, 11, 26), vote_count=0)
    assert rules.record_state(**past, action_name="Approved", minutes_file=None) == "Recorded"
    assert rules.record_state(**past, action_name=None, minutes_file="https://example.test/m.pdf") == "Recorded"
    assert (
        rules.record_state(
            meeting_date=date(2026, 11, 17),
            as_of=date(2026, 11, 26),
            action_name=None,
            minutes_file=None,
            vote_count=1,
        )
        == "Recorded"
    )


def test_blank_action_name_is_not_recorded():
    assert (
        rules.record_state(
            meeting_date=date(2026, 11, 17),
            as_of=date(2026, 11, 26),
            action_name="   ",
            minutes_file=None,
            vote_count=0,
        )
        == "Outcome not posted"
    )


def test_questions_use_the_meeting_date():
    assert (
        rules.meeting_question(date(2026, 11, 17), date(2026, 11, 26))
        == "What was on the San José City Council agenda for November 17, 2026?"
    )
    assert (
        rules.meeting_question(date(2026, 12, 1), date(2026, 11, 26))
        == "What is on the San José City Council agenda for December 1, 2026?"
    )
    assert rules.item_question("26-1183") == "What is file 26-1183?"


def test_boilerplate_titles_drop_and_other_file_numbers_stay():
    drop = [
        "Language Access Instructions / Instrucciones de interpretación",
        "American Disability Act",
        "To request an alternative format agenda under the Americans with Disabilities Act",
        "THE LEVINE ACT",
        "How to observe the Meeting",
        "How to watch the meeting",
        "Call to Order and Roll Call",
        "Closed Session Agenda",
        "Closed Session, Call to Order in Council Chambers - Cancelled",
        "Approval of City Council Minutes.",
        "Approval of Council Committee Minutes.",
        "Approval of Minutes",
        "Draft Agenda Review",
        "draft-agenda review",
    ]
    keep = [
        "Retroactive Approval of “Free Use” of the City Hall East and West Plazas and the Janet Gray Hayes Rotunda for the Tunnel of Terror Event.",
        "Final Adoption of Ordinances.",
        "First Amendment to the Agreement with N. Harris Computer Corporation.",
        "Pause on Data Center and Large Energy Use Project Approvals and Develop Urgency Ordinances.",
        "Approval of the World AIDS Day Flag Raising.",
    ]
    for title in drop:
        assert rules.classify_item(title, "26-1") == "boilerplate", title
    for title in keep:
        assert rules.classify_item(title, "26-1183") == "keep", title
    assert rules.classify_item("CEREMONIAL ITEMS", None) == "no_file"
    assert rules.classify_item("CEREMONIAL ITEMS", "") == "no_file"
