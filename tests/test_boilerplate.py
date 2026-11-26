"""The drop list is one constant, and routine consent items stay."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "record_lib", Path(__file__).resolve().parents[1] / "scripts" / "record_lib.py"
)
lib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lib)


def test_drop_list_is_one_constant_covering_the_named_phrases():
    joined = "\n".join(lib.DROP_TITLE_PATTERNS).lower()
    for phrase in (
        "language access",
        "ada",
        "levine act",
        "how to watch",
        "roll call",
        "closed session",
        "approval of",
        "minutes",
        "draft",
        "agenda review",
    ):
        assert phrase in joined


def test_each_named_boilerplate_title_is_dropped():
    samples = [
        "Language Access Instructions / Instrucciones de interpretación",
        "Email the ADA Coordinator at ADA@sanjoseca.gov",
        "THE LEVINE ACT",
        "How to watch the meeting",
        "Call to Order and Roll Call",
        "Closed Session Agenda",
        "Approval of Minutes",
        "Approval of City Council Minutes.",
        "Approval of Council Committee Minutes.",
        "Draft-agenda review",
        "Draft agenda review for City Council",
    ]
    for title in samples:
        assert lib.title_is_boilerplate(title), title


def test_routine_consent_items_are_kept():
    kept = [
        "Retroactive Approval of “Free Use” of the City Hall East and West Plazas.",
        "First Amendment to the Master Consultant Agreement with Cornerstone Earth Group, Inc.",
        "Final Adoption of Ordinances.",
        "Actions Related to the Purchase Order with Tom Lopes Distributing, Inc. for Fuel and Petroleum Products.",
        "Settlement of Lopez et al v. City of San José, et al.",
        "ADAPTIVE reuse study",
        "parade permit",
    ]
    for title in kept:
        assert not lib.title_is_boilerplate(title), title


def test_match_is_case_insensitive_and_ignores_extra_whitespace():
    assert lib.title_is_boilerplate("  language   ACCESS instructions ")
    assert lib.boilerplate_match("Closed Session Report") == "closed session"
