#!/usr/bin/env python3
"""
Pre-publish link checker for a single source file (markdown or HTML).

Usage:
  python check_links.py content/brief-2.md
  python check_links.py brief/2/index.html

Extracts URLs from markdown [text](url) and HTML href attributes, flags
San José Legistar links that omit a GUID, and verifies HTTP status codes.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen

USER_AGENT = "Mozilla/5.0 (compatible; thesanjosesource-link-check/1.0)"
DEFAULT_TIMEOUT = 30
SKIP_SCHEMES = {"mailto", "tel", "javascript", "data", "blob"}

MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
HTML_HREF = re.compile(
    r"""href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""",
    re.IGNORECASE,
)


@dataclass
class LinkResult:
    url: str
    ok: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    status: str = "—"

    @property
    def has_warning(self) -> bool:
        return bool(self.warnings)

    @property
    def has_error(self) -> bool:
        return bool(self.errors)


def extract_urls(text: str) -> list[str]:
    found: list[str] = []
    for match in MARKDOWN_LINK.finditer(text):
        found.append(strip_url_wrapper(match.group(1)))
    for match in HTML_HREF.finditer(text):
        href = match.group(1) or match.group(2) or match.group(3) or ""
        found.append(strip_url_wrapper(href))
    # Preserve first-seen order, dedupe
    seen: set[str] = set()
    unique: list[str] = []
    for url in found:
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(url)
    return unique


def strip_url_wrapper(raw: str) -> str:
    url = raw.strip()
    if url.startswith("<") and url.endswith(">"):
        url = url[1:-1].strip()
    return unquote(url)


def should_skip_http(url: str) -> bool:
    if url.startswith("#"):
        return True
    parsed = urlparse(url)
    if not parsed.scheme:
        return True
    if parsed.scheme.lower() in SKIP_SCHEMES:
        return True
    return False


def legistar_guid_warning(url: str) -> str | None:
    lower = url.lower()
    if "legistar" not in lower and "legislationdetail.aspx" not in lower:
        return None
    if "legislationdetail.aspx" not in lower:
        return None
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    has_id = any(k.lower() == "id" for k in qs)
    has_guid = any(k.lower() == "guid" for k in qs)
    if has_id and not has_guid:
        return (
            'Legistar "Invalid parameters!" risk: LegislationDetail.aspx has ID '
            "but no GUID. Use the full Legistar URL from the City record."
        )
    return None


def http_check(url: str, timeout: int) -> tuple[str, list[str], list[str]]:
    """Returns (status_label, warnings, errors)."""
    warnings: list[str] = []
    errors: list[str] = []
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
        },
        method="GET",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            if code is None:
                code = resp.status
            if 200 <= code <= 299:
                return f"{code} OK", warnings, errors
            if code in (403, 429):
                warnings.append(f"HTTP {code} (often a bot block; verify in a browser)")
                return f"{code}", warnings, errors
            errors.append(f"HTTP {code}")
            return f"{code}", warnings, errors
    except HTTPError as exc:
        code = exc.code
        if code in (403, 429):
            warnings.append(f"HTTP {code} (often a bot block; verify in a browser)")
            return f"{code}", warnings, errors
        if code == 404:
            errors.append("HTTP 404 Not Found")
        else:
            errors.append(f"HTTP {code}")
        return f"{code}", warnings, errors
    except URLError as exc:
        errors.append(f"Request failed: {exc.reason}")
        return "failed", warnings, errors
    except TimeoutError:
        errors.append(f"Timed out after {timeout}s")
        return "timeout", warnings, errors


def check_url(url: str, timeout: int) -> LinkResult:
    result = LinkResult(url=url)
    legistar = legistar_guid_warning(url)
    if legistar:
        result.warnings.append(legistar)

    if should_skip_http(url):
        result.status = "skipped"
        result.ok = not result.has_error
        if not url.startswith("#") and not urlparse(url).scheme:
            result.warnings.append("Relative or non-http URL (not fetched)")
        return result

    status, http_warnings, http_errors = http_check(url, timeout)
    result.status = status
    result.warnings.extend(http_warnings)
    result.errors.extend(http_errors)
    result.ok = not result.has_error
    return result


def print_detail(results: list[LinkResult]) -> None:
    for item in results:
        if item.status == "skipped" and not item.warnings and not item.errors:
            continue
        flag = "OK"
        if item.has_error:
            flag = "ERROR"
        elif item.has_warning:
            flag = "WARN"
        print(f"\n[{flag}] {item.url}")
        print(f"      Status: {item.status}")
        for msg in item.warnings:
            print(f"      Warning: {msg}")
        for msg in item.errors:
            print(f"      Error: {msg}")


def print_summary(results: list[LinkResult]) -> None:
    checked = [r for r in results if r.status != "skipped"]
    passed = [r for r in checked if r.ok and not r.has_warning]
    warn = [r for r in results if r.has_warning and not r.has_error]
    err = [r for r in results if r.has_error]
    warnings_or_errors = len(warn) + len(err)

    rows = [
        ("Total URLs found", len(results)),
        ("HTTP checked", len(checked)),
        ("Passed (200 OK, no warnings)", len(passed)),
        ("Warnings / errors", warnings_or_errors),
    ]
    width = max(len(label) for label, _ in rows)
    print("\n" + "=" * (width + 18))
    print(f"{'Metric'.ljust(width)} | Count")
    print("-" * (width + 18))
    for label, count in rows:
        print(f"{label.ljust(width)} | {count}")
    print("=" * (width + 18))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pre-publish link checker for one file.")
    parser.add_argument(
        "path",
        type=Path,
        help="File to scan (e.g. content/brief-2.md or brief/2/index.html)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"HTTP timeout in seconds (default {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Only print the summary table",
    )
    args = parser.parse_args(argv)

    path: Path = args.path
    if not path.is_file():
        print(f"Error: not a file: {path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    urls = extract_urls(text)
    if not urls:
        print(f"No URLs found in {path}")
        print_summary([])
        return 0

    print(f"Checking {len(urls)} URL(s) in {path} …")
    results: list[LinkResult] = []
    for url in urls:
        results.append(check_url(url, args.timeout))
        time.sleep(0.15)

    if not args.quiet:
        print_detail(results)
    print_summary(results)

    if any(r.has_error for r in results):
        return 1
    if any(r.has_warning for r in results):
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
