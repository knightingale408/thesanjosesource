"""State comes from fields, and a past meeting with an empty record says so."""

import importlib.util
from datetime import date
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "record_lib", Path(__file__).resolve().parents[1] / "scripts" / "record_lib.py"
)
lib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lib)

PAST = date(2026, 11, 17)
TODAY = date(2026, 11, 26)
FUTURE = date(2026, 12, 8)


def test_past_meeting_with_no_record_is_outcome_not_posted():
    assert (
        lib.record_state(PAST, TODAY, action_name="", minutes_file="", vote_rows=[])
        == "Outcome not posted"
    )


def test_future_meeting_is_agenda_only():
    assert lib.record_state(FUTURE, TODAY) == "Agenda only"


def test_meeting_day_itself_is_still_agenda_only():
    assert lib.record_state(PAST, PAST) == "Agenda only"


def test_blank_action_name_does_not_count():
    assert lib.record_state(PAST, TODAY, action_name="   ") == "Outcome not posted"


def test_action_name_is_recorded():
    assert lib.record_state(PAST, TODAY, action_name="Adopted") == "Recorded"


def test_minutes_file_is_recorded():
    assert (
        lib.record_state(PAST, TODAY, minutes_file="https://sanjose.legistar.com/View.ashx?M=M")
        == "Recorded"
    )


def test_vote_rows_are_recorded_and_an_empty_list_is_not():
    assert lib.record_state(PAST, TODAY, vote_rows=[]) == "Outcome not posted"
    assert lib.record_state(FUTURE, TODAY, vote_rows=[{"VoteId": 1}]) == "Recorded"


def test_history_action_name_is_recorded_and_prose_is_not_a_field_here():
    assert lib.record_state(PAST, TODAY, history_action_names=["Approved"]) == "Recorded"
    assert lib.history_action_names(
        [
            {"MatterHistoryActionText": "Council approved the item", "MatterHistoryActionName": ""},
            {"MatterHistoryActionName": "  "},
        ]
    ) == []
    assert lib.history_action_names([{"MatterHistoryActionName": "Adopted"}]) == ["Adopted"]


def test_agenda_republish_and_item_set_changes():
    old = {"EventAgendaLastPublishedUTC": "2026-11-14T00:00:00"}
    new = {"EventAgendaLastPublishedUTC": "2026-11-18T21:44:59.767"}
    assert lib.agenda_timestamp_changed(old, new)
    assert not lib.agenda_timestamp_changed(new, dict(new))
    assert not lib.agenda_timestamp_changed(None, new)
    old_sigs = {"26-1183": ("26-1183", "Old title", "2.8", "Consent Agenda", "", "")}
    new_sigs = {"26-1183": ("26-1183", "New title", "2.8", "Consent Agenda", "", "")}
    assert lib.changed_file_numbers(old_sigs, new_sigs) == {"26-1183"}
    added = dict(old_sigs)
    added["26-1220"] = ("26-1220", "Pause", "8.1", "", "", "")
    assert lib.changed_file_numbers(old_sigs, added) == {"26-1220"}


def test_amended_label_uses_the_fixed_line():
    assert lib.amended_label("") == ""
    assert lib.amended_label("2026-11-18") == "Agenda amended November 18, 2026."
