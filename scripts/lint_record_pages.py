#!/usr/bin/env python3
"""Neutrality lint for generated record pages.

Runs on items/ and meetings/ HTML only. Briefs are out of scope.

Outcome verbs that claim a result (approved, denied, continued, referred,
adopted, amended) fail unless the page state is Recorded. "proposed" and
"recommended" are allowed either way. The fixed line "Agenda amended <date>"
is the re-pull marker, so that one phrase does not count as the verb.

Hard bans are case-insensitive whole words or phrases: crisis, slam, bold,
historic, controversial, finally, despite, "the community", and "stakeholders"
unless the word is inside quotation marks. "why it matters" fails too.

Usage:
  python3 scripts/lint_record_pages.py
  python3 scripts/lint_record_pages.py items/26-1183/index.html
"""

from __future__ import annotations

import argparse
import re
import sys
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIRS = ("items", "meetings")
STATE_RECORDED = "Recorded"

# Verbs that need a Recorded state. proposed and recommended are not in this list.
RECORDED_ONLY_VERBS = (
    "approved",
    "denied",
    "continued",
    "referred",
    "adopted",
    "amended",
)

HARD_BAN_WORDS = (
    "crisis",
    "slam",
    "bold",
    "historic",
    "controversial",
    "finally",
    "despite",
)

HARD_BAN_PHRASES = (
    "the community",
    "why it matters",
)

# The re-pull marker is required copy. It is not an outcome claim.
AGENDA_AMENDED_LABEL = re.compile(
    r"Agenda amended\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}",
    re.IGNORECASE,
)

BODY_STATE = re.compile(
    r"<body\b[^>]*\bdata-state\s*=\s*['\"]([^'\"]*)['\"]",
    re.IGNORECASE,
)

SCRIPT_OR_STYLE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
TAG = re.compile(r"<[^>]+>")
BLOCKQUOTE = re.compile(r"<blockquote\b[^>]*>.*?</blockquote>", re.IGNORECASE | re.DOTALL)

# Double quotes and curly quotes. Straight single quotes are left alone so
# apostrophes in "City's" are not treated as quotation marks.
QUOTED_SPAN = re.compile(
    r"“[^”]*”|„[^“]*“|\"[^\"\n]*\"|‘[^’]*’",
)


def page_state(html: str) -> str:
    match = BODY_STATE.search(html)
    if not match:
        return ""
    return match.group(1).strip()


def visible_text(html: str) -> str:
    without_code = SCRIPT_OR_STYLE.sub(" ", html)
    text = TAG.sub(" ", without_code)
    return unescape(text)


def lint_html(html: str) -> list[str]:
    """Return one message per problem. Empty means the page passed.

    A blockquote is the City's memorandum, stored as a quote. The lint
    checks the page's own sentences, not those quotes.
    """
    state = page_state(html)
    text = visible_text(BLOCKQUOTE.sub(" ", html))
    problems: list[str] = []

    for word in HARD_BAN_WORDS:
        if re.search(rf"\b{word}\b", text, re.IGNORECASE):
            problems.append(f"banned word: {word}")

    for phrase in HARD_BAN_PHRASES:
        pattern = r"\b" + r"\s+".join(re.escape(part) for part in phrase.split()) + r"\b"
        if re.search(pattern, text, re.IGNORECASE):
            problems.append(f"banned phrase: {phrase}")

    unquoted = QUOTED_SPAN.sub(" ", text)
    if re.search(r"\bstakeholders\b", unquoted, re.IGNORECASE):
        problems.append("banned word: stakeholders (allowed only inside quotation marks)")

    if state != STATE_RECORDED:
        claimed = AGENDA_AMENDED_LABEL.sub(" ", text)
        for verb in RECORDED_ONLY_VERBS:
            if re.search(rf"\b{verb}\b", claimed, re.IGNORECASE):
                shown = state or "missing"
                problems.append(
                    f"outcome verb {verb!r} needs state {STATE_RECORDED} "
                    f"(page state is {shown})"
                )
    return problems


def iter_record_pages(root: Path) -> list[Path]:
    found: list[Path] = []
    for name in RECORD_DIRS:
        directory = root / name
        if not directory.is_dir():
            continue
        found.extend(sorted(directory.rglob("*.html")))
    return found


def lint_files(paths: list[Path]) -> list[str]:
    messages: list[str] = []
    for path in paths:
        html = path.read_text(encoding="utf-8")
        for problem in lint_html(html):
            messages.append(f"{path.as_posix()}: {problem}")
    return messages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="HTML files to lint. Default: items/ and meetings/ under the repo root.",
    )
    args = parser.parse_args(argv)
    if args.paths:
        paths = args.paths
    else:
        paths = iter_record_pages(ROOT)
    if not paths:
        print("No record pages to lint.")
        return 0
    messages = lint_files(paths)
    if messages:
        print(f"Neutrality lint failed ({len(messages)}):")
        for message in messages:
            print(f"  {message}")
        return 1
    print(f"Neutrality lint passed ({len(paths)} page(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
