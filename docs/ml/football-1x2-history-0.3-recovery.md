# Football 1X2 history 0.3 — exact-parquet recovery

**Recovery status:** `NOT_FOUND`

**Pinned SHA-256 (unchanged):**
`0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5`

This run did not recover a byte-identical copy. Evaluation A remains blocked.

This document is a search report only. No dataset was regenerated. No Sportmonks
rebuild. No Odds API request. No backtest. No retrain. The frozen walk-forward
protocol was not modified. The expected SHA-256 was not changed.

Machine-readable companion: `workers/ml/reports/football-1x2-history-0.3-recovery.json`.

---

## 1. What was sought

The Evaluation A run (`walk-forward-2024-2026-v1`) requires the **exact**
labeled parquet that was hashed on 2026-09-10:

| Field | Value |
|---|---|
| Filename (expected var location) | `workers/ingestion/var/football-1x2-history.parquet` |
| Dataset id | `football-1x2-history-0.3` |
| Rows (from provenance, not from a recovered file) | 7622 (`5729` finished / `1893` `not_finished`) |
| Expected SHA-256 | `0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5` |
| Usable if | SHA-256 matches **exactly** |

A file with a different hash is not usable, even if it has the same schema or
row count.

---

## 2. Final status

| Field | Value |
|---|---|
| `status` | `NOT_FOUND` |
| Exact SHA match | No |
| File copied to expected var location | No |
| Parquet open verification | Not applicable (no matching candidate) |
| Dataset regenerated | No |
| Odds API requests | 0 |
| Backtest executed | No |
| Protocol / expected SHA modified | No |

**Availability from this environment:** the original dataset appears
**permanently unavailable from this Cloud Agent VM**. It was never committed
(`var/` is gitignored), is absent from git objects, worktrees, caches, GitHub
Releases, Actions artifacts, Docker, LFS, `/mnt/data`, and every hashed
parquet-like file on disk. Recovery requires restoring the original file from
the developer machine that produced the 2026-09-10 hash (provenance path:
`/Users/boubacar/Development/predicta-ai/workers/ingestion/var/football-1x2-history.parquet`).

This environment **must not** recreate a substitute parquet.

---

## 3. Locations searched

Every location below was searched. None contained a file whose SHA-256 equals
the pinned digest. Search executed 2026-09-12T18:14:06Z–2026-09-12T18:15:19Z
on this VM (plus a prior pass logged in
`/opt/cursor/artifacts/football_1x2_history_0_3_recovery_search.log`).

### 3.1 Git objects / dangling blobs / unreachable commits

| Check | Result |
|---|---|
| `git rev-list --all --objects` filtered for parquet / football-1x2-history | No parquet paths in any reachable tree |
| `git log --all --full-history` for `**/football-1x2-history*` | Empty |
| `git log --all -- workers/ingestion/var/` | Empty (`var/` never tracked) |
| `git check-ignore` on expected path | Ignored (`var/` in `.gitignore`) |
| `git ls-tree -r` on every local and remote-tracking ref | No `*.parquet` paths |
| `git fsck --unreachable --dangling --lost-found` | No dangling blobs; no lost-found objects |
| Pack blobs ≥10 KiB hashed (`sha256sum` of blob contents) | 212 blobs in `/workspace`; 212 in `/tmp/predicta-ml`; **0** matched |
| Blob names containing `parquet` / `football-1x2` | None |

### 3.2 Local git worktrees

| Worktree | HEAD | Result |
|---|---|---|
| `/workspace` | `cursor/football-1x2-history-0.3-recovery-b277` | No `workers/ingestion/var/*.parquet`; no `workers/ml/var/*` |
| `/tmp/predicta-ml` | detached `1cde8f7` (`origin/agent/data/final-oos-odds-batch`) | Same: `var/` dirs absent; no parquet/joblib artefacts |

`git worktree list` reports only these two. `/tmp/cursor/worktrees` does not
exist.

### 3.3 Local branches and reflogs

| Check | Result |
|---|---|
| All local + remote-tracking branches | Docs/JSON **mention** the SHA; no binary |
| `HEAD` reflog | This agent's protocol / Evaluation A / recovery commits only |
| Stash | Empty |

### 3.4 Cursor worktrees / agent stores

| Path | Result |
|---|---|
| `/tmp/cursor/worktrees` | Does not exist |
| `/opt/cursor/artifacts` | This run's markdown/json/logs only; no labeled parquet |
| `/cursor/stores` | This run id only |
| `/opt/cursor/logs` | Cloud-agent logs; no parquet |
| Environment snapshot this VM booted from | `bld-20260912-f1589764-8043-4433-9d6b-e5a17fabddbb` — no parquet on disk after boot |
| Other environment builds listed | `bld-20260912-e2d0aadc-99f6-4e79-9b4e-83a70aadf866` (succeeded, not this boot); two `SKIPPED` recurring builds. None exposed a parquet on this VM. |

### 3.5 `/workspace`

| Check | Result |
|---|---|
| Filename glob `*football-1x2-history*` | Markdown/JSON reports and this recovery branch ref only |
| `find` `*.parquet` | pyarrow testdata under `.venv` only (see §4) |
| `workers/ingestion/var/` | Missing |
| `workers/ml/var/` | Missing |

### 3.6 `/tmp`

| Check | Result |
|---|---|
| `find /tmp -iname '*football-1x2-history*'` | Recovery docs in git worktree only (no data parquet) |
| `/tmp/predicta-ml` | See §3.2 |
| `/tmp/pytest-of-ubuntu` | Tiny test cover/labeled parquet copies (hashed; no match) |
| `/tmp/cursor` | `cloud-agent-transcripts`, `start-user` — no parquet |
| `/tmp/parquet-recovery/` | Not present at live search time |

### 3.7 `/mnt/data`

**Does not exist** on this VM (`ls: cannot access '/mnt/data'`). `/mnt` is empty.

### 3.8 User home directories

| Path | Result |
|---|---|
| `/home/ubuntu` | No `football-1x2-history` data files; caches are gh/pip/chrome/go |
| `/root` | No parquet |
| `/Users/boubacar/...` (provenance path) | Not present (macOS developer path; this is Linux Cloud Agent) |

### 3.9 Docker images and volumes

| Check | Result |
|---|---|
| `docker` binary | **Not installed** (`command not found`) |
| `podman` | **Not installed** |
| `/var/lib/docker`, `/var/lib/containerd` | Do not exist |
| Earlier session `docker volume ls` | Empty |
| Postgres | Port `5432` closed; no container |

No Docker volume could be inspected for the parquet.

### 3.10 Local caches / artifact stores

| Path | Result |
|---|---|
| `/workspace/.venv` / `apps/api/.venv` | pyarrow v0.7.1 testdata only |
| `/workspace/workers/ingestion/.venv` | No football parquet |
| `/home/ubuntu/.cache` | pytest/uv/gh/go-build; no labeled dataset |
| HuggingFace / torch caches | Absent |
| `/var/cache`, `/var/tmp` | No matching files |
| npm / go module zips | Unrelated toolchain caches; not the dataset |

### 3.11 Git LFS

Git LFS is installed (`git-lfs/3.7.1`) but **not used** by this repository.
`git lfs ls-files` is empty. `/workspace/.git/lfs/objects` is empty.
`/tmp/predicta-ml/.git/lfs` is not a directory.

### 3.12 CI / workspace artifact cache

| Check | Result |
|---|---|
| GitHub Actions artifacts | `total_count: 0` |
| GitHub Actions workflow runs | `total_count: 0` |
| GitHub Releases | `[]` |
| `workers/ingestion/var` via GitHub Contents API | 404 (path not in the repo) |

### 3.13 GitHub repository (read-only, existing credentials)

| Check | Result |
|---|---|
| Releases | None |
| Actions artifacts | None |
| Trees of `origin/agent/data/final-oos-odds-batch` and `origin/agent/ml/production-oos-backtest-sql` | No parquet paths |
| Code search for the SHA string | Present in **documentation/JSON only** (same digest as expected; not a binary). GitHub code search returned HTTP 429 on a later probe; local `git grep` already covers every fetched ref. |
| Extra credentials | Not invented; not used |

### 3.14 Existing ML / ingestion artifact directories

| Path | Result |
|---|---|
| `workers/ingestion/var/` | Missing in both worktrees |
| `workers/ml/var/` | Missing in both worktrees |
| `workers/ml/reports/*.joblib` | None |
| `workers/ml/reports/football-elo-v1-candidate/` | JSON/md only |
| Provenance `source_path` | Points at a developer laptop path that is not on this VM |
| `origin/agent/data/final-oos-odds-batch` reports | Record the SHA in JSON; they do not contain the parquet bytes |

### 3.15 Other filesystem roots

`find` for `*football-1x2-history*` under `/opt`, `/cursor`, `/var` (excluding
`/proc` `/sys` `/dev`): **no data parquet**.

Binary scan: files ≥50 KiB with parquet `PAR1` magic, excluding
venv/node_modules/.git/site-packages: **none**.

---

## 4. Candidate files hashed (none matched)

Every `*.parquet` found on local disks was SHA-256 hashed against

`0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5`.

| Path | Bytes | SHA-256 | Match |
|---|---|---|---|
| `/tmp/pytest-of-ubuntu/pytest-2/.../cover.parquet` (8 copies of the OOS fixture) | 40051 | `6c99e01a6611b97b3c908cb9ad59247cc3d7f995f8720b7db8438b4074e6ee6c` | No |
| `/tmp/pytest-of-ubuntu/pytest-4/test_prematch_store_rejects_la0/labeled.parquet` | 3056 | `bb8ca2beb9f790cef567ffa97c66c9d3d87831dc0ea344de2f6f47fcd74148f0` | No |
| `/tmp/pytest-of-ubuntu/pytest-4/test_prematch_store_rejects_po0/prematch.parquet` | 3783 | `29761b9bace189b4b2af67a9f6220e68820b41b8d874dfc1abd75bfea1f8aa5f` | No |
| `/workspace/apps/api/.venv/.../v0.7.1.all-named-index.parquet` | 3948 | `60f1945edc3e4ec38f6e234389e647a1b369de8afb9c7840c491a39880c0caa1` | No |
| `/workspace/apps/api/.venv/.../v0.7.1.column-metadata-handling.parquet` | 2012 | `eec79b660a5f75c3f7ed092c4f71610cbeaf380f6047a1816aae3834256d398c` | No |
| `/workspace/apps/api/.venv/.../v0.7.1.parquet` | 4372 | `be6773848ce905b99192adc68f0c3b2aabab7d214db50b92a52203790566ab2b` | No |
| `/workspace/apps/api/.venv/.../v0.7.1.some-named-index.parquet` | 4008 | `5468128ea8a1091b5d07195471f3f9b3705247b69440aba45be6c68092dffc76` | No |

The OOS fixture is a **tiny synthetic sample** (~40 KiB). The pinned production
parquet is the 7622-row labeled export. None of the hashed files equal the
pinned digest.

Git pack blobs ≥10 KiB: 212 (`/workspace`) + 212 (`/tmp/predicta-ml`, same
object store via worktree) hashed; 0 matches.

No file named with the expected SHA prefix exists on disk.

---

## 5. Why the file is missing here

1. `workers/ingestion/var/` is **gitignored**. The labeled parquet was never
   in git.
2. Provenance records it was written on a **macOS developer machine**
   (`/Users/boubacar/Development/predicta-ai/...`) on **2026-09-10**.
3. This Cloud Agent VM boots from a Linux environment snapshot that includes
   the git checkout, not gitignored `var/` binaries.
4. No CI job uploaded the parquet as a GitHub Actions artifact or Release
   asset. The repository has zero Actions artifacts and zero Releases.

The SHA string appears in docs because later agents **copied the digest from
provenance**. That is not the file.

---

## 6. What was not done (forbidden)

- Dataset regeneration / Sportmonks rebuild
- Odds API download
- Changing the expected SHA
- Substituting another parquet
- Opening a “close enough” file as Evaluation A input
- Running the backtest
- Retraining
- Modifying the frozen walk-forward protocol

---

## 7. How Evaluation A can be unblocked (outside this environment)

Place the **original** file (the one that hashes to the pinned digest) at:

`workers/ingestion/var/football-1x2-history.parquet`

Then re-verify:

```bash
sha256sum workers/ingestion/var/football-1x2-history.parquet
# must be 0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5
```

Until that happens, Evaluation A stays `BLOCKED`. This recovery task stops here.

---

## 8. Paid Odds API

**0** requests. Recovery was search-only.
