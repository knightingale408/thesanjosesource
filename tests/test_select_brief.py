"""The brief slate is a score, and the sentence is copied."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "select_brief", Path(__file__).resolve().parents[1] / "scripts" / "select_brief.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_first_sentence_keeps_inc_and_a_dollar():
    text = (
        "Approve an agreement with Example, Inc. in the amount of $1,250.50 "
        "and authorize the City Manager to sign it. A second sentence stays out."
    )
    assert mod.first_sentence(text) == (
        "Approve an agreement with Example, Inc. in the amount of $1,250.50 "
        "and authorize the City Manager to sign it."
    )


def test_a_colon_lead_in_includes_the_next_line():
    text = "(a) Adopt a resolution authorizing the City Manager to:\n\nExecute the amendment."
    assert mod.first_sentence(text) == (
        "(a) Adopt a resolution authorizing the City Manager to: Execute the amendment."
    )


def test_dollar_or_category_gets_in_and_a_plain_title_stays_out():
    money = {
        "file": "26-1195",
        "title": "Wastewater facility contract",
        "section": "Environmental & Utility Services",
        "recommendation": "Award the contract.",
        "fiscal": "The contract is $11,248,000.",
        "state": "Outcome not posted",
        "agenda_number": "6.1",
    }
    plain = {
        "file": "26-1209",
        "title": "Appointment to a retirement board",
        "section": "Consent Agenda",
        "recommendation": "Appoint a representative to a term ending November 30, 2030.",
        "fiscal": "",
        "state": "Outcome not posted",
        "agenda_number": "2.20",
    }
    assert mod.score_record(money)["dollar"] is True
    assert "utility" in mod.score_record(money)["hits"]
    assert "contract" in mod.score_record(money)["hits"]
    assert mod.score_record(plain) is None


def test_slate_caps_at_eight_and_the_count_line_uses_the_state():
    records = []
    for index in range(10):
        records.append(
            {
                "file": f"26-{1200 + index}",
                "title": f"Agreement {index}",
                "section": "Consent Agenda",
                "recommendation": f"Execute the agreement for ${index + 1},000.",
                "fiscal": "",
                "state": "Outcome not posted",
                "agenda_number": f"2.{index + 1}",
                "as_of": "2026-11-25T21:21:25-08:00",
                "meeting": "2026-11-17",
            }
        )
    slate, qualified = mod.rank_picks(records)
    assert len(qualified) == 10
    assert len(slate) == 8
    line = mod.pending_line(records, "2026-11-25T21:21:25-08:00")
    assert line.startswith("10 items are still outcome not posted, as of November 25, 2026, 9:21 p.m. Pacific.")
