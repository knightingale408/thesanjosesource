#!/usr/bin/env python3
"""Neutrality lint for generated Legistar record pages.

Scans meetings/*/index.html and items/*/index.html.

Outcome verbs (proposed, recommended, approved, denied, continued, referred,
adopted, amended) may appear only inside an element marked
data-record-field, because that text is copied from a Legistar field.

approved, adopted, and denied also fail anywhere on the page, including
inside a source field, when the surrounding data-record-state is not
Recorded.

Hard bans apply to text we wrote (anything outside data-record-field):
crisis, slam, bold, historic, controversial, finally, despite,
"the community", stakeholders, room-color words, and councilmember names.
"""

from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

from record_rules import STATES

OUTCOME_VERBS = re.compile(
    r"\b(proposed|recommended|approved|denied|continued|referred|adopted|amended)\b",
    re.IGNORECASE,
)
RECORDED_ONLY = re.compile(r"\b(approved|adopted|denied)\b", re.IGNORECASE)

HARD_BANS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bcrisis\b", re.IGNORECASE), "crisis"),
    (re.compile(r"\bslam(?:s|med|ming)?\b", re.IGNORECASE), "slam"),
    (re.compile(r"\bbold\b", re.IGNORECASE), "bold"),
    (re.compile(r"\bhistoric\b", re.IGNORECASE), "historic"),
    (re.compile(r"\bcontroversial\b", re.IGNORECASE), "controversial"),
    (re.compile(r"\bfinally\b", re.IGNORECASE), "finally"),
    (re.compile(r"\bdespite\b", re.IGNORECASE), "despite"),
    (re.compile(r"\bthe community\b", re.IGNORECASE), "the community"),
    (re.compile(r"\bstakeholders?\b", re.IGNORECASE), "stakeholders"),
    (
        re.compile(
            r"\b(packed|tense|heated|chaotic|raucous|fiery|outburst|booed|cheered|applause)\b",
            re.IGNORECASE,
        ),
        "room characterization",
    ),
    (
        re.compile(
            r"\b(Mahan|Kamei|Campos|Tordillos|Cohen|Ortiz|Mulcahy|Doan|Candelas|Casey|Foley)\b"
        ),
        "councilmember name",
    ),
]

VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}
SKIP_TAGS = {"script", "style", "noscript"}


class _Segments(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.skip_at: list[int] = []
        self.source_at: list[int] = []
        self.state_at: list[tuple[int, str]] = []
        self.segments: list[dict[str, str | bool]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in VOID_TAGS:
            return
        self.depth += 1
        ad = {key: value or "" for key, value in attrs}
        if tag in SKIP_TAGS:
            self.skip_at.append(self.depth)
        if "data-record-field" in ad:
            self.source_at.append(self.depth)
        if "data-record-state" in ad:
            self.state_at.append((self.depth, ad["data-record-state"].strip()))

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS or self.depth == 0:
            return
        if self.skip_at and self.skip_at[-1] == self.depth:
            self.skip_at.pop()
        if self.source_at and self.source_at[-1] == self.depth:
            self.source_at.pop()
        if self.state_at and self.state_at[-1][0] == self.depth:
            self.state_at.pop()
        self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_at or not data.strip():
            return
        state = self.state_at[-1][1] if self.state_at else ""
        self.segments.append(
            {"text": data, "source": bool(self.source_at), "state": state}
        )


def lint_html(html: str, *, label: str = "page") -> list[str]:
    """Return human-readable failures. An empty list means the page passed."""
    problems: list[str] = []
    if "data-record-state=" not in html:
        problems.append(f"{label}: missing data-record-state")
    parser = _Segments()
    parser.feed(html)
    parser.close()

    states_seen: set[str] = set()
    prose_parts: list[str] = []
    for segment in parser.segments:
        state = str(segment["state"])
        text = str(segment["text"])
        if state:
            states_seen.add(state)
            if state not in STATES:
                problems.append(f"{label}: unknown state {state!r}")
        if not segment["source"]:
            prose_parts.append(text)
        for match in RECORDED_ONLY.finditer(text):
            if state != "Recorded":
                shown = state or "(no state)"
                problems.append(
                    f"{label}: {match.group(0)!r} appears where state is {shown}"
                )

    prose = " ".join(prose_parts)
    for match in OUTCOME_VERBS.finditer(prose):
        problems.append(
            f"{label}: outcome verb {match.group(0)!r} is outside a Legistar field"
        )
    for pattern, name in HARD_BANS:
        match = pattern.search(prose)
        if match:
            problems.append(f"{label}: banned wording {match.group(0)!r} ({name})")
    return problems


def record_pages(repo: Path) -> list[Path]:
    pages = sorted(repo.glob("meetings/*/index.html"))
    pages += sorted(repo.glob("items/*/index.html"))
    return pages


def lint_repo(repo: Path) -> list[str]:
    pages = record_pages(repo)
    if not pages:
        return ["no record pages under meetings/ or items/"]
    problems: list[str] = []
    for path in pages:
        html = path.read_text(encoding="utf-8")
        problems.extend(lint_html(html, label=path.relative_to(repo).as_posix()))
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        help="HTML files to lint. Default: meetings/*/index.html and items/*/index.html.",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root when no paths are given.",
    )
    args = parser.parse_args(argv)
    if args.paths:
        problems: list[str] = []
        for raw in args.paths:
            path = Path(raw)
            problems.extend(lint_html(path.read_text(encoding="utf-8"), label=str(path)))
    else:
        problems = lint_repo(args.repo)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print(f"{len(problems)} neutrality problem(s).", file=sys.stderr)
        return 1
    print("Neutrality lint passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
