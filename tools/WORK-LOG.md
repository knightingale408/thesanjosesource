# Work log

Internal session notes for this repo. `tools/` is excluded from the live publish
(`publish.py` `EXCLUDE_PREFIX`), so this file does not go to thesanjosesource.com.

No work log existed anywhere in this repo's git history before this file.
This is the first entry.

## 2026-10-25 — Revert PR #12; why /corrections/ 404s

Asked by Jay / J Gonzales (via Alfred): PR #12 (squash `dbf611cb` on main) copied
out-of-date archive pages over the current site. Publish #17 failed at the build
step, so the public site never took those pages, but main still has them. Close
PR #13 without merging. Revert #12. Do not change `build.py`. Do not re-run
Publish #17. Investigate the `/corrections/` 404. Do not publish. Do not touch
san-jose-sourcearchive.

### PR #13

Closed without merging: https://github.com/knightingale408/thesanjosesource/pull/13

- Title was "1". Base `add-corrections-page`, head `main`.
- Closed at 2026-10-25T08:06:00Z. `mergedAt` is null. State CLOSED.

### Revert

- `dbf611cb8e0dd67bfdc4d3e45788c07626bf1806` is a single-parent squash.
  Its only parent is `f3de0bc2fec0df3c91f7d2b45c4a403e3184ffb6` (merge of PR #11).
- `git revert -m 1 dbf611cb` succeeded on this git (it did not need the
  single-parent fallback). Revert commit: `4ac70a55e1206b2e6b049c790f774ae6f3dd6a9d`
  on branch `cursor/revert-pr-12-archive-sync-f245`.
- `git diff f3de0bc2fec0df3c91f7d2b45c4a403e3184ffb6 4ac70a55` is empty.
  That commit's tree matches pre-#12 main. The only difference on the branch tip,
  after this log was added, is `tools/WORK-LOG.md`.
- `build.py` is unchanged from both `f3de0bc` and `dbf611cb` (PR #12 did not touch it).
- Publish #17 (run 40163264323) was not re-run. It is still failed.
  The build step raised `ValueError: Missing build markers` for
  `<!-- build:coverage-start -->` … `<!-- build:coverage-end -->` because #12
  had replaced `index.html`. The publish step was skipped. Those markers are
  back on the revert. `python3 build.py` on a copy of the reverted tree exited 0
  (wrote both brief pages, updated the homepage, wrote `feed.xml` and
  `sitemap.xml`). That was a local check only. Nothing was published.

### Check links

Lychee v0.24.2, same acceptance rule as `.github/workflows/link-check.yml`
(`--accept 200..=299,403,429`), run on this branch:

- 268 total, 77 unique, 257 OK, 10 excluded, 1 redirect, 1 error.
- The only error: `[404] https://thesanjosesource.com/corrections/` in
  `corrections/index.html` (canonical link, line 11).
- The pull request's Check links run
  (https://github.com/knightingale408/thesanjosesource/actions/runs/40175747443,
  2026-10-25 08:13 UTC) reported the same counts: 268 total, 257 successful,
  1 error, that same URL. The check is red for that known 404 only.

### Why /corrections/ 404s

Publish #16 did upload the page. The file is not on the live host now because
later re-runs of older Publish site workflows replaced the whole here.now
version with manifests that do not include `corrections/index.html`. Finalize
goes live before verification, and a failed verify does not roll the version back.

Checked 2026-10-25 about 08:06 UTC, no publish performed:

- `https://thesanjosesource.com/corrections/`, `/corrections`,
  `/corrections/index.html`, and the same paths with `?v=probe1` all return
  HTTP 404, body `Not found` (9 bytes), `content-type: text/plain`, header
  `x-herenow-origin: worker`. Same body as `https://thesanjosesource.com/does-not-exist/`.
- The slug host does the same:
  `https://smooth-hearth-r7kk.here.now/corrections/` is also that worker 404.
  `https://smooth-hearth-r7kk.here.now/about/` redirects to the custom domain and
  returns the About page.
- This is not a cached 404 of an HTML page. Pages that are in the live manifest
  answer `200` with `cache-control: no-cache`. Missing paths hit the worker.

Publish #16 (run 40145278430, commit `f3de0bc`, 2026-10-25 00:04–00:08 UTC):

- Uploaded `corrections/index.html` (9789 bytes, sha256 prefix `909ecc207e4b`)
  and `feed.xml`. Skipped 19 unchanged files. Finalized version
  `01M5R66NNPDM0DJ8ARPKPFBN7K` (replaced `01M5R4JR5XPXYJMVJ1QEEC5SRD`) and
  printed `VERIFIED` for all 21 files.
- GitHub Pages still serves that exact file:
  `https://knightingale408.github.io/thesanjosesource/corrections/` is HTTP 200,
  9789 bytes, sha256 prefix `909ecc207e4b`. Pages deploys from git. here.now
  deploys from the last finalized manifest.

What replaced that manifest (oldest relevant re-run first):

1. Run 39114162271 attempt 11 (2026-10-25 00:21–00:25 UTC), title
   "Merge pull request #1 from knightingale408/site-updates-oct17", commit
   `82d749f`. That commit has no `corrections/index.html`. The job submitted 15
   files, skipped all 15 as unchanged, and finalize reported version
   `01M5R684RTDF406EH85PAMKA01` (replaced the same id). Verify then failed with
   HTTP 403 on the HTML and asset URLs. The public homepage today is not that
   commit's `index.html` (that file is 13421 bytes, hash prefix `50a229c50882`;
   live `index.html` is 14995 bytes, prefix `adcae21ce1da`, the #16 / pre-#12 page).

2. Run 39745122178 attempt 8 (2026-10-25 03:49–03:52 UTC), commit `b174682`
   ("Automate site generator, dynamic tracker table, and link verification").
   That commit also has no `corrections/index.html`. Its `publish.py` still
   publishes `content/` (the later exclude of `content/` is not in that commit).
   It finalized version `01M5RJVQTY94F2GEGP16JPPVF1`, replacing
   `01M5R684RTDF406EH85PAMKA01`, from a 23-file list with no corrections path.
   Verify failed after finalize.

3. Same run, attempt 9 (2026-10-25 07:29–07:32 UTC). Finalized version
   `01M5RZF2GQC742JCHKGD69QQSG`, replacing `01M5RJVQTY94F2GEGP16JPPVF1`.
   22 files skipped; only `feed.xml` uploaded, because `build.py` stamps
   `lastBuildDate`. Live `https://thesanjosesource.com/feed.xml` is 1355 bytes,
   sha256 prefix `8114fa6bba6b`, and `lastBuildDate` is
   `Sun, 25 Oct 2026 07:30:05 +0000`, matching that upload. Verify failed because
   here.now serves `content/*.md` as an HTML viewer, so the bytes fetched at
   those URLs are not the raw markdown (`content/README.md` live hash prefix
   `9116fe00c59a`, `content/brief-1.md` `0f8d742ddb9c`, `content/brief-2.md`
   `9a478331f0a4`, all `text/html`). Finalize had already happened.

Publish #17 did not do this. Its publish step was skipped after `build.py` failed.

Other live files still match Publish #16's post-build hashes (homepage, About,
tracker, both briefs, `app.js`, `styles.css`, `sitemap.xml`, `robots.txt`).
The corrections path is the one the later manifests left out.

`build.py` `write_sitemap()` never adds `/corrections/`. The sitemap #16
published (449 bytes, prefix `8fcb269ca997`) is still what is live, and it has
no corrections URL. That is separate from the 404: `/corrections/index.html`
itself is absent from the live manifest, not merely missing from the sitemap.

Side effect of those re-runs: `content/` is reachable on the live host right now
(here.now's HTML viewer and a directory listing). Current `publish.py` excludes
`content/`. A later publish from the reverted tree would upload
`corrections/index.html` again and would stop publishing `content/`. Not done
in this session.

Still waiting, not touched: workflow_dispatch run 39138813410 attempt 6, commit
`82d749f` (PR #1 era, no corrections page). The publish job has been waiting
since 2026-10-25T07:53:24Z.
https://github.com/knightingale408/thesanjosesource/actions/runs/39138813410
Approving it would publish that old tree over the live site. It was not
approved, cancelled, or re-run here.

### Not done

- Revert PR left open for Alfred. Not merged.
- `build.py` not edited.
- Publish #17 not re-run.
- No here.now publish.
- san-jose-sourcearchive not touched.
