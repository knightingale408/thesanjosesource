"""Memo quotes are sliced from headings, not rewritten."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "memo_extract", Path(__file__).resolve().parents[1] / "scripts" / "memo_extract.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SAMPLE = """
TO: HONORABLE MAYOR
FROM: Jen Baker

SUBJECT: See Below

RECOMMENDATION

Adopt a resolution retroactively authorizing free use of the
City Hall plazas on Saturday, October 24, 2026.

SUMMARY AND OUTCOME

This is the preamble and is not the quote.

FISCAL IMPACTS

The estimated total cost for the reservation is $6,708.60, of which
$5,470.46 would be waived.

COORDINATION

Budget Office.
"""


def test_slices_recommendation_and_fiscal_and_drops_the_preamble():
    got = mod.slice_memo(SAMPLE)
    assert got["memo_from"] == "Jen Baker"
    assert got["recommendation"].startswith("Adopt a resolution")
    assert "October 24, 2026" in got["recommendation"]
    assert "preamble" not in got["recommendation"]
    assert got["fiscal_heading"] == "FISCAL IMPACTS"
    assert "$6,708.60" in got["fiscal"]
    assert "Budget Office" not in got["fiscal"]
    assert mod.extract_has_resident_fact(got["fiscal"])
    assert not mod.extract_has_resident_fact("")


def test_a_date_that_finishes_the_sentence_stays_in_the_quote():
    text = """
FROM: Toni J. Taber, MMC
City Clerk

RECOMMENDATION

Appoint Richard Santos to a term beginning December 1, 2026 and ending
November 30, 2030.

OUTCOME

The board can meet.
"""
    got = mod.slice_memo(text)
    assert got["memo_from"] == "Toni J. Taber, MMC, City Clerk"
    assert got["recommendation"].endswith("November 30, 2030.")
    assert "The board can meet" not in got["recommendation"]


def test_from_line_on_the_same_line_as_to():
    text = """
TO: HONORABLE CITY COUNCIL FROM: Mayor Matt Mahan
Councilmember Cohen

SUBJECT: SEE BELOW

RECOMMENDATION

Direct the City Manager to pause approvals.

BACKGROUND

No fiscal section here.
"""
    got = mod.slice_memo(text)
    assert got["memo_from"] == "Mayor Matt Mahan, Councilmember Cohen"
    assert got["fiscal"] == ""
    assert not mod.extract_has_resident_fact(got["fiscal"])
