#!/usr/bin/env python3
"""Pick six to eight item pages for the weekly brief.

An item is in if the title, section, recommendation, or fiscal quote
matches one of the spec's categories, or if the recommendation or fiscal
quote contains a dollar amount. The brief uses the recommendation's first
sentence, copied, not rewritten.

    python3 scripts/select_brief.py
    python3 scripts/select_brief.py --write content/brief-6.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from record_lib import format_as_of, load_record, parse_iso_date  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://thesanjosesource.com"
PICK_MIN = 6
PICK_MAX = 8

# Spec: ordinance, fee, rate, tax, budget action, contract, housing
# entitlement, or utility item. Patterns stay here so the test can see them.
CATEGORY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ordinance", re.compile(r"\bordinances?\b", re.IGNORECASE)),
    ("fee", re.compile(r"\bfees?\b", re.IGNORECASE)),
    ("rate", re.compile(r"\brates?\b", re.IGNORECASE)),
    ("tax", re.compile(r"\btax(?:es)?\b", re.IGNORECASE)),
    ("budget", re.compile(r"\bbudget\b|\bappropriat\w*", re.IGNORECASE)),
    (
        "contract",
        re.compile(
            r"\bcontracts?\b|\bagreements?\b|\bpurchase orders?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "housing",
        re.compile(r"\bhousing entitlement\b|\bentitlements?\b", re.IGNORECASE),
    ),
    (
        "utility",
        re.compile(
            r"\butilit(?:y|ies)\b|\bwastewater\b|\bsewage\b|\bsewer\b",
            re.IGNORECASE,
        ),
    ),
)
DOLLAR = re.compile(r"\$\s?\d")


_ABBREV = re.compile(
    r"\b(?:Inc|LLC|Corp|Co|No|Mr|Mrs|Ms|Dr|Jr|Sr|St|Cal|Dept|al|Dist|Ct|v|U\.S)\.",
    re.IGNORECASE,
)


def _hide_period(match: re.Match[str]) -> str:
    return match.group(0).replace(".", "\u0000")


def _protect(text: str) -> str:
    """Hide periods that do not end a sentence."""
    text = _ABBREV.sub(_hide_period, text)
    text = re.sub(r"\b([A-Z])\.(?=\s+[A-Z])", _hide_period, text)
    return re.sub(r"(\d)\.(\d)", _hide_period, text)


def first_sentence(text: str) -> str:
    """The recommendation's first complete sentence, with its period.

    A lead-in that ends in a colon is joined to the next line so the
    sentence includes the ask. Periods in Inc., LLC, and decimals stay.
    """
    parts = [part.strip() for part in re.split(r"\n\s*\n", text or "") if part.strip()]
    if not parts:
        flat = " ".join((text or "").split())
    else:
        chosen = [parts[0]]
        if parts[0].endswith(":") and len(parts) > 1:
            chosen.append(parts[1])
        flat = " ".join(chosen)
    if not flat:
        return ""
    protected = _protect(flat)
    match = re.search(r"^.+?\.(?=\s|$)", protected)
    sentence = match.group(0) if match else protected
    return " ".join(sentence.replace("\u0000", ".").split())


def category_hits(text: str) -> list[str]:
    return [name for name, pattern in CATEGORY_PATTERNS if pattern.search(text)]


def has_dollar(text: str) -> bool:
    return bool(DOLLAR.search(text or ""))


def score_record(record: dict) -> dict | None:
    """Return a score row, or None when the item is not on the slate."""
    title = str(record.get("title") or "")
    section = str(record.get("section") or "")
    recommendation = str(record.get("recommendation") or "")
    fiscal = str(record.get("fiscal") or "")
    # Categories come from the title, section, and recommendation.
    # A dollar in the fiscal quote still counts. Fund names in that quote
    # do not, or every memo that cites a tax fund would rank as a tax item.
    described = "\n".join([title, section, recommendation])
    hits = category_hits(described)
    if "utility" in section.lower() and "utility" not in hits:
        hits.append("utility")
    money_text = "\n".join([recommendation, fiscal])
    dollar = has_dollar(money_text)
    if not hits and not dollar:
        return None
    return {
        "file": str(record.get("file") or ""),
        "title": title,
        "section": section,
        "state": str(record.get("state") or ""),
        "sentence": first_sentence(recommendation),
        "hits": hits,
        "dollar": dollar,
        "score": len(hits) + (2 if dollar else 0),
        "agenda_number": str(record.get("agenda_number") or ""),
        "as_of": str(record.get("as_of") or ""),
        "meeting": str(record.get("meeting") or ""),
    }


def load_meeting_items(root: Path, meeting: str | None = None) -> list[dict]:
    folder = root / "content" / "items"
    records = []
    for path in sorted(folder.glob("*.md")):
        record = load_record(path.read_text(encoding="utf-8"))
        if meeting and str(record.get("meeting") or "") != meeting:
            continue
        records.append(record)
    return records


def agenda_key(row: dict) -> tuple:
    raw = row.get("agenda_number") or ""
    parts = re.split(r"(\d+)", raw)
    key: list[object] = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part)
    return (0 if raw else 1, tuple(key), row.get("file") or "")


def rank_picks(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (slate of 6 to 8, every item that qualified)."""
    qualified = []
    for record in records:
        row = score_record(record)
        if row:
            qualified.append(row)
    qualified.sort(key=lambda row: (-row["score"], not row["dollar"], agenda_key(row)))
    if len(qualified) <= PICK_MAX:
        slate = qualified
    else:
        slate = qualified[:PICK_MAX]
    return slate, qualified


def pending_line(records: list[dict], as_of: str) -> str:
    pending = sum(1 for record in records if record.get("state") != "Recorded")
    shown = format_as_of(as_of) if as_of else ""
    noun = "item is" if pending == 1 else "items are"
    line = f"{pending} {noun} still outcome not posted"
    if shown:
        line += f", as of {shown}"
    return line + "."


def render_brief(records: list[dict], *, meeting: str, published: str) -> str:
    slate, _qualified = rank_picks(records)
    as_of = ""
    for record in records:
        if record.get("as_of"):
            as_of = str(record["as_of"])
            break
    short_when = parse_iso_date(meeting).strftime("%b. %d").replace(" 0", " ") if meeting else ""
    count_line = pending_line(records, as_of)
    title = f"{short_when} City Council files with a contract or a dollar amount in the record"
    lines = [
        "---",
        f"title: {title}",
        "description: A pick list of City Council files from the public record. The sentences are the staff recommendation's first sentence. Outcomes are not posted.",
        f"date: {published}",
        "series: Weekly brief",
        f"homepage_blurb: {count_line}",
        f"eyebrow: {short_when}, outcome not posted",
        f"dek: {count_line}",
        "---",
        "",
        count_line,
        "",
        "Each item below is one sentence from its file page, the staff recommendation. The link goes to that page.",
        "",
    ]
    for row in slate:
        url = f"{SITE}/items/{row['file']}/"
        sentence = row["sentence"] or row["title"]
        lines.append(f"- **[File {row['file']}]({url}).** {sentence}")
        lines.append("")
    lines.append(
        f"The full agenda is on the [meeting page]({SITE}/meetings/{meeting}/)."
    )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meeting", default="2026-11-17")
    parser.add_argument("--write", type=Path, default=None, help="Write the brief markdown here.")
    parser.add_argument("--date", default="2026-11-26", help="Publish date for the brief.")
    args = parser.parse_args(argv)
    records = load_meeting_items(ROOT, args.meeting)
    slate, qualified = rank_picks(records)
    print(pending_line(records, next((str(r.get("as_of") or "") for r in records if r.get("as_of")), "")))
    print(f"Qualified: {len(qualified)}. Slate: {len(slate)}.")
    for row in qualified:
        mark = "PICK" if row in slate else "    "
        money = " $" if row["dollar"] else "  "
        print(
            f"{mark}{money} {row['score']:2} {row['file']} "
            f"[{', '.join(row['hits']) or 'dollar'}] {row['sentence'][:110]}"
        )
    if len(slate) < PICK_MIN:
        print(f"Only {len(slate)} items qualified. The spec asks for {PICK_MIN} to {PICK_MAX}.")
    if args.write:
        text = render_brief(records, meeting=args.meeting, published=args.date)
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(text, encoding="utf-8")
        print(f"Wrote {args.write}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
