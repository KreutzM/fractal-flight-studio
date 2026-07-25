# Agent Git workflow

This document defines how automated agents acquire the repository, validate source freshness, and publish coherent changes without creating avoidable intermediate commits. The mandatory summary is in the repository-root `AGENTS.md`.

## Goals

- Always modify the current target-branch content.
- Prefer normal local Git operations when they are available.
- Make related multi-file changes atomic and reviewable.
- Keep GitHub Actions as independent validation, not as a substitute for knowingly testing an outdated tree.
- Report exactly which source state and checks were used.

## Decision flow

```text
Current local clone of the target branch available?
├─ Yes: fetch, fast-forward/rebase as appropriate, then create a feature branch.
└─ No: restore the latest successful repository-snapshot artifact.
        ├─ Verify the artifact checksum manifest.
        ├─ Verify the Git bundle.
        ├─ Clone or fetch from the bundle.
        └─ Confirm the restored commit/tree matches the intended target content.

Can the feature branch be pushed with normal Git?
├─ Yes: commit locally and push the branch.
└─ No: publish through the GitHub Git-data API.
        ├─ Create blobs for every changed file.
        ├─ Create one tree based on the current target tree.
        ├─ Create one commit with the current target commit as parent.
        └─ Create/update the feature-branch ref once.
```

## 1. Establish a current source tree

### Preferred: normal local clone

Before editing, establish the target branch and synchronize it. Typical commands are:

```powershell
git fetch origin --prune
git switch main
git pull --ff-only
git switch -c agent/<description>
```

Do not start from a cached checkout merely because it is available. Check the target commit explicitly with `git rev-parse HEAD` and compare it with the repository's current default-branch head.

### Fallback: repository snapshot and Git bundle

Use the newest successful `Repository snapshot` workflow artifact associated with the required source state. The artifact contains a source ZIP, a complete Git bundle, metadata, and a SHA-256 manifest.

PowerShell example:

```powershell
Expand-Archive .\repository-snapshot-<sha>.zip -DestinationPath .\snapshot
Set-Location .\snapshot
Get-Content .\fractal-flight-studio-*.sha256
# Validate each listed SHA-256 value with Get-FileHash.

git init .\verify-bundle
git -C .\verify-bundle bundle verify (Resolve-Path .\fractal-flight-studio-*.bundle)
git clone .\fractal-flight-studio-*.bundle ..\fractal-flight-studio-work
```

Linux example:

```bash
unzip repository-snapshot-<sha>.zip -d snapshot
cd snapshot
sha256sum -c fractal-flight-studio-*.sha256
mkdir verify-bundle && git -C verify-bundle init
git -C verify-bundle bundle verify "$PWD"/fractal-flight-studio-*.bundle
git clone fractal-flight-studio-*.bundle ../fractal-flight-studio-work
```

A workflow artifact may represent a pull-request merge commit. That is acceptable when its tree is intentionally the source being modified. Record both the commit SHA and tree SHA. If the target branch has advanced, obtain a newer snapshot or rebase the work; do not reconstruct the difference by downloading files individually.

## 2. Develop and validate locally

Make changes in the restored/current working tree. Use normal Git inspection throughout:

```powershell
git status --short
git diff --check
git diff --stat
```

Run the checks required by `AGENTS.md`. For changes that do not affect executable code, at minimum inspect the rendered Markdown structure and run `git diff --check`. Do not claim that the current integrated repository was tested when checks were run only against an older snapshot.

## 3. Preferred publication: normal Git push

When authenticated Git transport is available:

```powershell
git add -- <intended paths>
git commit -m "<focused description>"
git push -u origin HEAD
```

Stage only intended paths. Keep commits focused and reviewable. Open a pull request against the current target branch and let CI independently validate the pushed commit.

## 4. Connector fallback: one Git tree and one commit

When normal push is unavailable but GitHub Git-data operations are available, publish a related multi-file change atomically.

### Required sequence

1. Resolve the current target commit SHA and its tree SHA.
2. Create one blob for the final content of each added or modified file.
3. Create one tree using the target tree as `base_tree_sha`. Include only changed paths.
4. Create one commit using the new tree and the current target commit as `parent_sha`.
5. Create the feature branch at that commit, or update an existing feature-branch ref once.
6. Compare the feature branch with the target branch.
7. Open a draft pull request.

Conceptual payload:

```text
blob(AGENTS.md) ───────┐
blob(docs/...md) ──────┼─> create_tree(base_tree_sha=<target tree>)
other changed blobs ───┘
                                ↓
create_commit(tree_sha=<new tree>, parent_sha=<target commit>)
                                ↓
create/update feature-branch ref once
```

### Why this is required

Repeated contents-API updates create one commit per file and expose incomplete intermediate branch states. A Git-data tree commit is atomic, produces a clean history, reduces API calls, and mirrors a normal local `git commit`.

### Single-file exception

The contents API (`create_file`, `update_file`, or `delete_file`) is acceptable for a truly isolated single-file change. Do not split one logical multi-file change into multiple contents-API commits.

## 5. Pre-PR verification

Before opening the pull request, compare target and feature branch and verify:

- the merge base is the intended target commit;
- the branch is not behind the target (`behind_by == 0`);
- only expected files changed;
- additions/deletions are plausible;
- generated files, caches, artifacts, and unrelated edits are absent;
- the commit count matches the intended history.

If the target branch moved after the commit was prepared, rebuild/rebase against the new target before opening or merging the pull request.

## 6. Pull request and merge

Open a draft pull request unless the user explicitly requests otherwise. The description must state:

- what changed and why;
- the source commit/tree used;
- local checks actually executed;
- checks delegated to CI;
- hardware or platform validation that remains outstanding.

Merge only after required checks pass and the user has authorized the merge. If an API fallback produced several unavoidable commits, prefer squash merge unless preserving those commits has review value.

## Prohibited shortcuts

- Do not edit an outdated clone and manually copy changed files onto the current branch.
- Do not infer a local file path from a connector file reference without downloading or mounting it.
- Do not publish a related multi-file change through repeated contents-API calls.
- Do not update `main` directly.
- Do not open a pull request before comparing it with the current target branch.
- Do not describe CI as local validation or simulator results as physical GPU validation.
