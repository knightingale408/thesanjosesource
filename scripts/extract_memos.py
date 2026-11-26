#!/usr/bin/env python3
"""Copy the recommendation and the fiscal section out of each staff memo.

Reads content/items/*.md, downloads the attachment named Memorandum, and
stores the two slices as quotes on that file. It does not rewrite them.

    python3 -m pip install pypdf
    python3 scripts/extract_memos.py

Then run python3 build.py and commit the item files and the rebuilt pages.
"""

from __future__ import annotations

import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from memo_extract import pdf_to_text, slice_memo  # noqa: E402
from record_lib import dump_record, load_record  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
USER_AGENT = "TheSanJoseSource/1.0 (+https://thesanjosesource.com)"
UPDATE = "2026-11-25"
UPDATE_NOTE = (
    "Added the staff memorandum’s recommendation and fiscal or cost section as quotes. "
    "The page previously showed the official title, file number, meeting, section, state, "
    "and official links, and did not quote the memorandum."
)
NO_MEMO_NOTE = (
    "Noted that no staff memorandum is in the public record for this file. "
    "The page previously showed the official title, file number, meeting, section, state, "
    "and official links only."
)


def memorandum_url(record: dict) -> str:
    for row in record.get("attachments") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip().lower()
        if name == "memorandum":
            return str(row.get("url") or "")
    return ""


def download(url: str, dest: Path) -> None:
    last_error: Exception | None = None
    for attempt in range(3):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                dest.write_bytes(resp.read())
                return
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in (404, 429, 500, 502, 503) or attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
    if last_error:
        raise last_error


def apply_one(path: Path) -> str:
    record = load_record(path.read_text(encoding="utf-8"))
    url = memorandum_url(record)
    record["memo_pdf"] = url
    if not url:
        record["memo_from"] = ""
        record["recommendation"] = ""
        record["fiscal_heading"] = ""
        record["fiscal"] = ""
        note = "no memorandum"
    else:
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "memo.pdf"
            download(url, pdf_path)
            sliced = slice_memo(pdf_to_text(pdf_path))
        record.update(sliced)
        note = "quoted" if sliced["recommendation"] else "no recommendation heading"
    if not record.get("update"):
        record["update"] = UPDATE
    record["update_note"] = UPDATE_NOTE if url else NO_MEMO_NOTE
    path.write_text(dump_record(record), encoding="utf-8")
    file_number = record.get("file") or path.stem
    return f"{file_number}: {note}"


def main() -> int:
    folder = ROOT / "content" / "items"
    paths = sorted(folder.glob("*.md"))
    if not paths:
        print("No item files in content/items.")
        return 0
    for path in paths:
        print(apply_one(path))
    print("Next: python3 build.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
