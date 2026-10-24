#!/usr/bin/env python3
"""Publish ALL site files from this repo to here.now, then verify the live site.

Run by .github/workflows/publish.yml after Jay approves. Never publishes a
partial file list. Needs the HERENOW_API_KEY secret; the key never leaves
GitHub's secret store and is never printed.
"""
import hashlib, json, mimetypes, os, subprocess, sys, time, urllib.request, urllib.error

SITE_SLUG = "smooth-hearth-r7kk"
LIVE_BASE = "https://thesanjosesource.com/"
API = "https://here.now/api/v1"
CLIENT = "github-actions/thesanjosesource"
# Repo-only files that are never part of the website.
EXCLUDE_EXACT = {"README.md", ".nojekyll", ".gitattributes", ".gitignore", "CNAME"}
EXCLUDE_PREFIX = (".github/", "content/", "tools/", "research/")

TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8", ".xml": "application/xml; charset=utf-8",
    ".txt": "text/plain; charset=utf-8", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".ico": "image/x-icon", ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8", ".webp": "image/webp",
}

def site_files():
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout
    paths = [p for p in out.decode().split("\0") if p]
    return sorted(p for p in paths if p not in EXCLUDE_EXACT and not p.startswith(EXCLUDE_PREFIX))

def ctype(path):
    ext = os.path.splitext(path)[1].lower()
    return TYPES.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def call(method, url, body=None, key=None, headers=None, raw=None):
    h = {"X-HereNow-Client": CLIENT}
    if key: h["Authorization"] = "Bearer " + key
    if body is not None:
        raw = json.dumps(body).encode(); h["Content-Type"] = "application/json"
    h.update(headers or {})
    req = urllib.request.Request(url, data=raw, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            txt = r.read()
            return json.loads(txt) if txt and r.headers.get_content_type() == "application/json" else txt
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {url.split('?')[0]} failed: HTTP {e.code} {e.read()[:500].decode(errors='replace')}")

def main():
    key = os.environ.get("HERENOW_API_KEY")
    if not key:
        sys.exit("HERENOW_API_KEY secret is not set in this repo (Settings > Environments > production).")
    files = site_files()
    blobs = {p: open(p, "rb").read() for p in files}
    manifest = [{"path": p, "size": len(blobs[p]), "contentType": ctype(p), "hash": sha(blobs[p])} for p in files]
    print(f"Publishing ALL {len(files)} site files at commit {os.environ.get('GITHUB_SHA', '?')[:7]}:")
    for m in manifest: print(f"  {m['path']}  {m['size']} bytes  {m['hash'][:12]}")

    res = call("PUT", f"{API}/publish/{SITE_SLUG}", {"files": manifest}, key)
    up = res["upload"]
    for u in up.get("uploads", []):
        call(u.get("method", "PUT"), u["url"], raw=blobs[u["path"]],
             headers={"Content-Type": (u.get("headers") or {}).get("Content-Type", ctype(u["path"]))})
        print(f"  uploaded {u['path']}")
    print(f"  unchanged (skipped): {len(up.get('skipped', []))}")
    fin = call("POST", up["finalizeUrl"], {"versionId": up["versionId"]}, key)
    print(f"here.now version {fin.get('currentVersionId')} (replaced {fin.get('previousVersionId')}), status {fin.get('publishStatus')}")

    # Verify: every live file must be byte-identical to the repo.
    bust = int(time.time())
    for attempt in range(6):
        bad = []
        for p in files:
            url = LIVE_BASE + ("" if p == "index.html" else p.removesuffix("index.html")) + f"?v={bust}-{attempt}"
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "Mozilla/5.0 (compatible; thesanjosesource-publish)"}), timeout=60) as r:
                    live = r.read()
            except Exception as e:
                bad.append(f"{p}: {e}"); continue
            if sha(live) != sha(blobs[p]): bad.append(f"{p}: live hash {sha(live)[:12]} != repo {sha(blobs[p])[:12]}")
        if not bad:
            print(f"VERIFIED: all {len(files)} live files on {LIVE_BASE} are byte-identical to the repo.")
            return
        print(f"Verify attempt {attempt + 1}: {len(bad)} mismatch(es); waiting for caches...")
        time.sleep(20)
    sys.exit("VERIFY FAILED:\n" + "\n".join(bad))

if __name__ == "__main__":
    main()
