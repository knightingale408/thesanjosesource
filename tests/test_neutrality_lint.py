"""Neutrality lint: outcome verbs need a Recorded state, and the hard bans hold."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "lint_record_pages",
    Path(__file__).resolve().parents[1] / "scripts" / "lint_record_pages.py",
)
lint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lint)


def page(body: str, state: str = "Outcome not posted") -> str:
    attr = f' data-state="{state}"' if state else ""
    return (
        "<!DOCTYPE html><html><head><style>.bold { color: red; }</style>"
        f"<script>var stakeholders = 1;</script></head>"
        f"<body{attr}><main><p>{body}</p></main></body></html>"
    )


def test_recorded_only_verbs_fail_until_the_state_is_recorded():
    for verb in ("approved", "denied", "continued", "referred", "adopted", "amended"):
        assert lint.lint_html(page(f"Council {verb} the item."))
        assert lint.lint_html(page(f"Council {verb} the item.", state="Recorded")) == []


def test_proposed_and_recommended_are_allowed_before_a_record_exists():
    assert lint.lint_html(page("Staff recommended the purchase. The agenda proposed a fee.")) == []
    assert lint.lint_html(page("Staff recommended the purchase.", state="Agenda only")) == []


def test_agenda_amended_label_is_allowed_and_other_uses_are_not():
    assert lint.lint_html(page("Agenda amended November 18, 2026.")) == []
    problems = lint.lint_html(page("Agenda amended November 18, 2026. Council amended the fee."))
    assert len(problems) == 1
    assert "amended" in problems[0]


def test_hard_bans_are_whole_words_and_case_insensitive():
    for word in ("crisis", "slam", "bold", "historic", "controversial", "finally", "despite"):
        assert lint.lint_html(page(f"This is a {word.upper()} choice."))
    assert lint.lint_html(page("A historical note about a boldface font and Islam.")) == []
    assert lint.lint_html(page("The recommendation was not discontinued.")) == []


def test_phrases_and_quoted_stakeholders():
    assert lint.lint_html(page("Why it matters to the community."))
    assert any("stakeholders" in item for item in lint.lint_html(page("Talk to stakeholders today.")))
    assert lint.lint_html(page('The memo says "stakeholders" once.')) == []
    assert lint.lint_html(page("The memo says “stakeholders” once.")) == []
    assert lint.lint_html(page('She quoted "the community" in the title.'))


def test_style_and_script_text_is_not_linted():
    assert lint.lint_html(page("File 26-1183. State: Outcome not posted.")) == []


def test_memorandum_quotes_are_not_linted():
    quoted = page('<blockquote class="memo-quote"><p>Council approved it for the community and stakeholders.</p></blockquote>')
    assert lint.lint_html(quoted) == []
    assert lint.lint_html(page("Council approved it."))


def test_missing_state_still_blocks_outcome_verbs():
    html = "<html><body><p>Council approved it.</p></body></html>"
    assert lint.lint_html(html)
