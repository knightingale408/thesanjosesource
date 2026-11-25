#!/usr/bin/env python3
"""Pre-flight check for every agent (Claude, Cursor, Copilot, Perplexity, Grok, Gemini).

Run this before changing anything in this repo, and again before opening a PR:

    python3 tools/preflight.py                 # checks your branch's changes vs origin/main
    python3 tools/preflight.py --files content/brief-6.md   # checks specific files you plan to touch

It stops (exit 1) when:
  1. The repo is not knightingale408/thesanjosesource (for example fiscal-os,
     "OLDSSJFISCLOSREPO", or the archived san-jose-sourcearchive).
  2. You are on main. Work on a branch; open a PR; never merge.
  3. You are touching a brief that is queued to publish: a content/brief-N.md file
     changed by another open pull request, or by the commit that a "Publish site"
     run is waiting to publish.

It only reads. It never pushes, merges, approves or publishes. Standard library only.
In GitHub Actions (pull_request) it runs with --ci and checks the PR's own files.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

REPO = "knightingale408/thesanjosesource"
WRONG_REPOS = ("fiscal-os", "san-jose-sourcearchive", "san-jose-source.git")
BRIEF_RE = re.compile(r"^content/brief-\d+\.md$")
API = "https://api.github.com/repos/" + REPO


def repo_ok(remote_or_slug):
    """True only for knightingale408/thesanjosesource (any URL form)."""
    s = (remote_or_slug or "").strip().lower()
    if any(w in s for w in WRONG_REPOS):
        return False
    s = re.sub(r"\.git$", "", s).rstrip("/")
    return s.endswith(REPO)


def brief_files(paths):
    return sorted({p for p in paths if BRIEF_RE.match(p)})


def queued_overlap(my_files, queued):
    """queued: {path: reason}. Returns [(path, reason)] for briefs I touch that are queued."""
    return [(p, queued[p]) for p in brief_files(my_files) if p in queued]


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def api(path):
    req = urllib.request.Request(API + path, headers={"Accept": "application/vnd.github+json",
                                                      "User-Agent": "tsjs-preflight"})
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        req.add_header("Authorization", "Bearer " + tok)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def pr_files(number):
    files, page = [], 1
    while True:
        batch = api(f"/pulls/{number}/files?per_page=100&page={page}")
        files += [f["filename"] for f in batch]
        if len(batch) < 100:
            return files
        page += 1


def queued_briefs(skip_pr=None):
    """Briefs that another open PR changes, or that a waiting Publish run would publish."""
    queued = {}
    for pr in api("/pulls?state=open&per_page=100"):
        if skip_pr and pr["number"] == skip_pr:
            continue
        for p in brief_files(pr_files(pr["number"])):
            queued[p] = f"open PR #{pr['number']} ({pr['title']})"
    main_sha = api("/branches/main")["commit"]["sha"]
    for run in api("/actions/runs?status=waiting&per_page=20").get("workflow_runs", []):
        # Publish site only proceeds for the current main HEAD; older waiting runs are stale.
        if run.get("name") == "Publish site" and run.get("head_sha") == main_sha:
            for f in api(f"/commits/{main_sha}").get("files", []):
                if BRIEF_RE.match(f["filename"]):
                    queued[f["filename"]] = f"Publish site run #{run['run_number']} is waiting for Jay's approval"
    return queued


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--files", nargs="*", help="files you plan to change (default: your changes vs origin/main)")
    ap.add_argument("--ci", action="store_true", help="GitHub Actions pull_request mode")
    a = ap.parse_args()
    problems, notes = [], []

    # 1. Right repo
    where = os.environ.get("GITHUB_REPOSITORY") if a.ci else git("remote", "get-url", "origin")
    if not repo_ok(where):
        problems.append(f"Wrong repo: '{where or 'no origin remote'}'. Only {REPO} is in use. "
                        "Never fiscal-os (OLDSSJFISCLOSREPO) or san-jose-sourcearchive. Stop and tell Jay.")

    # 2. Not on main
    pr_number = None
    if a.ci:
        event = os.environ.get("GITHUB_EVENT_PATH")
        if event and os.path.exists(event):
            pr_number = (json.load(open(event)).get("pull_request") or {}).get("number")
    else:
        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        if branch in ("main", "master"):
            problems.append("You are on main. Create a branch, then open a PR. Agents never push to main or merge.")

    # Files this work touches
    if a.files is not None and a.files:
        mine = a.files
    elif a.ci and pr_number:
        mine = pr_files(pr_number)
    else:
        mine = set(filter(None, git("diff", "--name-only", "origin/main...HEAD").splitlines()))
        mine |= set(filter(None, git("diff", "--name-only", "HEAD").splitlines()))
        mine = sorted(mine)

    # 3. Not a brief that's queued to publish
    try:
        hits = queued_overlap(mine, queued_briefs(skip_pr=pr_number))
        for path, reason in hits:
            problems.append(f"{path} is queued to publish ({reason}). Don't change it; tell Jay instead.")
    except Exception as e:  # network or rate limit: say so, don't pretend it passed
        msg = f"Could not check queued briefs ({e.__class__.__name__}: {e})."
        if a.ci:
            problems.append(msg)
        else:
            notes.append(msg + " Check open PRs and waiting Publish site runs by hand before touching content/brief-*.md.")

    print(f"Pre-flight for {REPO}")
    print(f"  files checked: {len(mine)}")
    for n in notes:
        print("  NOTE:", n)
    if problems:
        for p in problems:
            print("  STOP:", p)
        print("Pre-flight FAILED. Do not continue. Log it in the WORK LOG and tell Jay.")
        return 1
    print("  OK: right repo, not on main, no queued brief touched.")
    print("  Reminder: PRs only. No agent merges, approves a deployment, or publishes; Jay does.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
