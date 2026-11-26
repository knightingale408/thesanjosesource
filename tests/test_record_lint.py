"""Neutrality lint. Pages under test are HTML strings, not the live site."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import record_lint


def _page(body: str, state: str = "Outcome not posted") -> str:
    return (
        "<html><body>"
        f'<article data-record-state="{state}">{body}</article>'
        "</body></html>"
    )


def test_clean_outcome_not_posted_page_passes():
    html = _page(
        "<p>State: Outcome not posted.</p>"
        '<p data-record-field="title">Retroactive Approval of free use.</p>'
        '<p data-record-field="legistar_status">Agenda Ready</p>'
    )
    assert record_lint.lint_html(html) == []


def test_approved_fails_when_state_is_not_recorded():
    html = _page('<p data-record-field="title">The contract was approved.</p>')
    problems = record_lint.lint_html(html)
    assert any("approved" in problem and "Outcome not posted" in problem for problem in problems)


def test_approved_in_the_action_field_passes_when_recorded():
    html = _page(
        '<p data-record-field="action_name">Approved</p>',
        state="Recorded",
    )
    assert record_lint.lint_html(html) == []


def test_outcome_verb_in_our_prose_fails_even_when_recorded():
    html = _page("<p>The Council approved the item.</p>", state="Recorded")
    problems = record_lint.lint_html(html)
    assert any("outside a Legistar field" in problem for problem in problems)


def test_hard_bans_and_names_fail_in_prose_only():
    for word in (
        "crisis",
        "slam",
        "bold",
        "historic",
        "controversial",
        "finally",
        "despite",
        "the community",
        "stakeholders",
        "heated",
        "Mahan",
    ):
        problems = record_lint.lint_html(_page(f"<p>Note: {word}.</p>"))
        assert problems, word
    named = _page(
        '<p data-record-field="votes">Mahan Yes</p>',
        state="Recorded",
    )
    assert record_lint.lint_html(named) == []


def test_missing_state_fails():
    html = "<html><body><p>Outcome not posted.</p></body></html>"
    assert any("missing data-record-state" in problem for problem in record_lint.lint_html(html))


def test_approval_and_adoption_are_not_the_past_tense_verbs():
    html = _page(
        '<p data-record-field="title">Retroactive Approval. Final Adoption of Ordinances. First Amendment.</p>'
    )
    assert record_lint.lint_html(html) == []
