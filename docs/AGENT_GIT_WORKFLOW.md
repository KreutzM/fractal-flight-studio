# Agent Git workflow

This document defines the fastest safe workflow available when normal Git transport may be unavailable. The mandatory summary is in the repository-root `AGENTS.md`.

## Goals

- Work from the exact current target tree.
- Use normal Git transport whenever it works.
- Reuse verified local trees across sequential PRs instead of downloading a new snapshot unnecessarily.
- Publish connector-based multi-file changes atomically and byte-for-byte identical to the tested local commit.
- Avoid repeated probes, copy/paste payloads, intermediate commits, and oversized documentation churn.

## Decision flow

```text
Verified local tree matches current target tree?
├─ Yes: reuse it, even if commit topology differs after squash/merge.
└─ No: acquire and verify the newest repository snapshot.

Normal authenticated Git push works?
├─ Yes: use local git commit/push, then open the PR through the connector.
└─ No: prepare exact payloads from committed Git objects and use one Git-data transaction.
```

## 1. Probe capabilities once

At the start of a task, perform one bounded capability check:

1. inspect the local repository and current branch;
2. try the normal Git/CLI path once when it is available;
3. verify the GitHub connector once;
4. choose the working path and do not repeatedly retry a known unavailable transport during the same task.

A failed DNS lookup, missing `gh`, or unavailable authenticated remote should immediately select the snapshot/connector path. Repeated probes add latency without increasing safety.

## 2. Establish the current source tree

### Preferred: normal local clone

```powershell
git fetch origin --prune
git switch main
git pull --ff-only
git switch -c agent/<description>
```

Record both commit and tree:

```powershell
git rev-parse HEAD
git rev-parse HEAD^{tree}
```

### Fast reuse for sequential PRs

GitHub squash and merge operations often create a new commit SHA while preserving the exact feature-tree contents. A verified local commit may therefore be reused when:

- its tree SHA equals the current remote target tree SHA;
- the intended target files are present and clean;
- the remote target commit SHA is recorded separately for publication as the new commit parent.

Commit-history identity is not required when tree identity is proven. This avoids downloading and verifying a fresh snapshot after every successful PR.

Do not reuse a local checkout merely because it is recent. If the target tree differs, reacquire or integrate the current target before editing.

### Snapshot fallback

Use the newest successful `Repository snapshot` artifact only when no verified local tree matches the current target. Verify the checksum manifest and bundle:

```powershell
Expand-Archive .\repository-snapshot-<sha>.zip -DestinationPath .\snapshot
Set-Location .\snapshot
Get-Content .\fractal-flight-studio-*.sha256
git init .\verify-bundle
git -C .\verify-bundle bundle verify (Resolve-Path .\fractal-flight-studio-*.bundle)
git clone .\fractal-flight-studio-*.bundle ..\fractal-flight-studio-work
```

Linux:

```bash
unzip repository-snapshot-<sha>.zip -d snapshot
cd snapshot
sha256sum -c fractal-flight-studio-*.sha256
mkdir verify-bundle && git -C verify-bundle init
git -C verify-bundle bundle verify "$PWD"/fractal-flight-studio-*.bundle
git clone fractal-flight-studio-*.bundle ../fractal-flight-studio-work
```

Never reconstruct a current source tree by manually downloading a collection of individual repository files.

## 3. Develop and validate locally

Work normally in Git and commit the complete intended result before preparing connector payloads:

```powershell
git status --short
git diff --check
git diff --stat
git add -- <intended paths>
git commit -m "<focused description>"
```

The worktree must be clean before publication preparation. Run the checks required by `AGENTS.md` and report only checks actually executed.

Keep documentation proportional to the change:

- update `CHANGELOG.md` for user-visible behavior;
- update `README.md` only when the user workflow materially changes;
- update `TEST_REPORT.md` only when validation strategy or durable results change;
- do not replace large historical sections merely to restate the current PR.

## 4. Preferred publication: normal Git push

```powershell
git push -u origin HEAD
```

Then open a draft PR through the GitHub connector. This remains the fastest and least error-prone route.

## 5. Connector fallback: generate exact payloads

Do not copy file text into connector calls manually. Generate payloads from committed Git blob objects:

```powershell
python scripts\prepare_connector_publish.py `
  --base-ref <verified-local-base-ref> `
  --repository KreutzM/fractal-flight-studio `
  --remote-base-commit <current-remote-main-sha> `
  --expected-base-tree <current-remote-main-tree-sha> `
  --branch agent/<description> `
  --output-dir .agent-publish
```

The helper:

- refuses a dirty worktree;
- requires the local base to be an ancestor of the final local commit;
- verifies the expected remote base tree against the local base tree;
- reads bytes with `git cat-file`, preserving line endings, binary data, and encodings;
- emits one Base64 JSON payload per unique blob;
- emits tree, commit, branch, and compare request templates;
- records every expected blob SHA and the expected final tree SHA.

The generated `.agent-publish/README.txt` is the publication checklist.

### Required connector sequence

1. Upload each generated blob payload. Verify every returned SHA immediately.
2. Stop on the first mismatch. Do not retry by copying or re-encoding text.
3. Create one tree using `create-tree.json` and require its returned SHA to equal the manifest's `expected_tree`.
4. Create one commit with the current remote target commit as parent.
5. Create the feature branch only now, after the commit is complete.
6. Compare target and feature branch; require `behind_by == 0` and only expected paths.
7. Open a draft PR.

Because Git blob and tree IDs are content-addressed, matching SHAs prove that GitHub received exactly the locally tested content.

### Why the branch is created last

Creating a branch before the final tree exists exposes an unnecessary incomplete ref and causes repeated branch-creation errors on retries. Preparing blobs, tree, and commit first allows one final branch operation.

### Single-file exception

The contents API is acceptable for a genuinely isolated single-file change. Do not split a logical multi-file change into several contents-API commits.

## 6. Pre-PR verification

Before opening the PR, verify:

- current remote target commit is still the intended parent;
- target tree still matches the verified base tree;
- branch is one focused commit ahead and zero behind;
- changed paths exactly match the manifest;
- additions/deletions are plausible;
- generated payloads, caches, coverage files, build output, and local artifacts are not committed.

If the remote target tree moved, stop and rebuild against the new tree. Do not transplant the final files manually.

## 7. Pull request and merge

Open a draft PR unless the user explicitly requests otherwise. State:

- what changed and why;
- remote parent commit and verified base tree;
- local checks actually executed;
- checks delegated to CI;
- remaining hardware/platform validation.

Merge only after required checks pass and the user authorizes it.

## Prohibited shortcuts

- repeated retries of a transport already known to be unavailable;
- editing an unverified stale tree;
- reconstructing current source from individual downloads;
- publishing multi-file work through repeated contents-API updates;
- copying large file contents manually into blob calls;
- accepting any blob or tree SHA mismatch;
- creating the feature branch before the final commit exists;
- updating `main` directly;
- describing CI as local validation or simulator results as physical GPU validation.
