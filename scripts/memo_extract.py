#!/usr/bin/env python3
"""Slice a staff memorandum into two quotes.

The recommendation, and the fiscal or cost section. No rewriting.
PDF line breaks are joined. Words are not changed.

PDF reading needs pypdf (`python3 -m pip install pypdf`). The slicer
itself is plain text and does not import pypdf.
"""

from __future__ import annotations

import re
from pathlib import Path

# Longer headings first so "cost summary/implications" wins over "cost summary".
HEADINGS: tuple[str, ...] = (
    "summary and outcome",
    "public outreach/interest",
    "cost summary/implications",
    "evaluation and follow-up",
    "commission recommendation",
    "policy alternatives",
    "fiscal impacts",
    "fiscal impact",
    "cost implications",
    "cost summary",
    "budget reference",
    "public outreach",
    "recommendation",
    "coordination",
    "background",
    "analysis",
    "outcome",
    "ceqa",
)

FISCAL_HEADINGS = {
    "fiscal impacts",
    "fiscal impact",
    "cost summary/implications",
    "cost implications",
    "cost summary",
    "budget reference",
}

_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december"
)
_DATE_LINE = re.compile(rf"(?:{_MONTHS})\s+\d{{1,2}},\s+\d{{4}}\.?$", re.IGNORECASE)
_PAGE_LINE = re.compile(r"page\s+\d+$", re.IGNORECASE)
_FILE_LINE = re.compile(r"file:\s*\d{2}-\d+\s*$", re.IGNORECASE)
_ITEM_LINE = re.compile(r"item:\s*\S+\s*$", re.IGNORECASE)
_LIST_ITEM = re.compile(r"^(?:\([A-Za-z0-9]+\)|\d+\.)\s")


def _norm(line: str) -> str:
    return " ".join(line.split()).strip()


def heading_name(line: str) -> str | None:
    """Return the heading key when the line is only that heading."""
    text = _norm(line).rstrip(":").lower()
    for heading in HEADINGS:
        if text == heading:
            return heading
    return None


def is_document_break(line: str) -> bool:
    """A second memo starts here. Stop the current section before this line."""
    low = _norm(line).lower()
    return low.startswith("to: honorable") or low.startswith("rules committee agenda") or low.startswith("approved:")


def is_running_header(line: str) -> bool:
    text = _norm(line)
    low = text.lower()
    if not text:
        return False
    if low.startswith("honorable mayor"):
        return True
    if low.startswith("subject:"):
        return True
    if low.startswith("council agenda"):
        return True
    if _PAGE_LINE.match(low):
        return True
    if _FILE_LINE.match(low):
        return True
    if _ITEM_LINE.match(low) and len(text) < 24:
        return True
    if _DATE_LINE.match(low):
        return True
    return False


def _paragraphs(lines: list[str]) -> str:
    """Join wrapped PDF lines. A line that ends a sentence closes a paragraph."""
    chunks: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            chunks.append(" ".join(buf))
            buf.clear()

    for raw in lines:
        text = _norm(raw)
        # A lone date is usually the memo header. Keep it when it finishes a sentence.
        date_continues = bool(_DATE_LINE.match(text) and buf and buf[-1][-1:] not in ".?!:")
        if is_running_header(raw) and not date_continues:
            continue
        if not text:
            flush()
            continue
        if buf and _LIST_ITEM.match(text):
            flush()
        if len(buf) == 1 and len(buf[0]) == 1 and buf[0].isalpha() and text[:1].islower():
            buf[0] = buf[0] + text
            if text.endswith((".", "?", "!", ":")):
                flush()
            continue
        if buf and buf[-1].endswith("-") and text[:1].islower():
            buf[-1] = buf[-1][:-1] + text
        else:
            buf.append(text)
        if text.endswith((".", "?", "!", ":")):
            flush()
    flush()
    return "\n\n".join(chunks).strip()


def _sections(text: str) -> list[tuple[str, list[str]]]:
    """Split memo text into (heading, body lines) after the first heading."""
    sections: list[tuple[str, list[str]]] = []
    current: str | None = None
    body: list[str] = []
    for line in text.splitlines():
        found = heading_name(line)
        if found:
            if current is not None:
                sections.append((current, body))
            current = found
            body = []
            continue
        if current is not None:
            if is_document_break(line):
                sections.append((current, body))
                current = None
                body = []
                continue
            body.append(line)
    if current is not None:
        sections.append((current, body))
    return sections


def memo_from(text: str) -> str:
    """The FROM line above the recommendation, when the memo has one."""
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if heading_name(line) == "recommendation":
            break
        if re.search(r"\bFROM:", line, re.IGNORECASE):
            start = index
            break
    if start is None:
        return ""
    first = _norm(lines[start])
    match = re.search(r"\bFROM:\s*(.*)$", first, re.IGNORECASE)
    picked: list[str] = []
    if match and match.group(1).strip():
        picked.append(match.group(1).strip())
    for line in lines[start + 1 :]:
        if heading_name(line):
            break
        norm = _norm(line)
        if not norm:
            if picked:
                break
            continue
        low = norm.lower()
        if (
            low.startswith("subject")
            or low.startswith("date")
            or low.startswith("to:")
            or low.startswith("and city council")
            or low.startswith("council district")
            or low.startswith("approved")
            or is_running_header(line)
        ):
            break
        picked.append(norm)
        if len(picked) >= 8:
            break
    return ", ".join(_norm(part).strip(" ,") for part in picked if part.strip())


def slice_memo(text: str) -> dict[str, str]:
    """Return recommendation and fiscal quotes, plus who signed the memo."""
    sections = _sections(text)
    recommendation = ""
    for name, lines in sections:
        if name == "recommendation":
            recommendation = _paragraphs(lines)
            break

    fiscal_heading = ""
    fiscal_lines: list[str] = []
    taking = False
    for name, lines in sections:
        if name in FISCAL_HEADINGS:
            if not taking:
                fiscal_heading = name.upper()
                taking = True
            fiscal_lines.extend(lines)
            fiscal_lines.append("")
            continue
        if taking:
            break
    return {
        "memo_from": memo_from(text),
        "recommendation": recommendation,
        "fiscal_heading": fiscal_heading,
        "fiscal": _paragraphs(fiscal_lines),
    }


def extract_has_resident_fact(fiscal: str) -> bool:
    """A number, dollar, or fee in the fiscal quote is enough to show it."""
    if not fiscal:
        return False
    if re.search(r"\d", fiscal):
        return True
    return bool(re.search(r"\b(fee|fees)\b", fiscal, re.IGNORECASE))


def pdf_to_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SystemExit(
            "PDF text needs pypdf. Install it with: python3 -m pip install pypdf"
        ) from exc
    reader = PdfReader(str(path))
    parts = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(parts)
