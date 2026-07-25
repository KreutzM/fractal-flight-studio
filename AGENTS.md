# AGENTS.md

## Scope

These instructions apply to the entire repository.

## Environment

- Primary target: Windows 11 with PowerShell 7.
- Supported Python versions: 3.11, 3.12, and 3.13.
- CPU rendering must remain available without CUDA.
- CUDA work must remain compatible with the optional `numba-cuda[cu12]` setup used by the Windows scripts.

## Setup and validation

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e . pytest
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\check_pan_stability.py --backend cpu
```

On Linux, use `.venv/bin/python` instead. For GUI changes also run:

```bash
xvfb-run -a env PYTHONPATH=src python scripts/gui_smoke.py
```

## Numerical invariants

- Never reduce deep-zoom viewport centers, widths, reference anchors, or reference offsets to absolute Python `float` values before perturbation setup.
- Preserve high-precision text/`mpmath` coordinates through navigation, flight interpolation, and reference selection.
- Related pan and zoom frames should reuse a valid reference orbit; avoid per-frame reference changes that make overlapping pixels unstable.
- Rebasing may change the decomposition `z = Z + dz`, but must not reconstruct the deep parameter `c` as an absolute FP64 value.
- CPU and CUDA paths must agree within the tolerances established by the tests.
- Any perturbation, reference-cache, viewport, or CUDA-kernel change must run the full test suite and `scripts/check_pan_stability.py`.
- Do not claim physical CUDA performance or driver compatibility from CUDA-simulator results alone.

## Repository acquisition and GitHub publishing

- Prefer a normal up-to-date local clone and normal `git push`; probe transport once at the start instead of repeatedly retrying unavailable paths.
- A previously verified clone or snapshot may be reused for the next PR when its tree SHA exactly matches the current target-branch tree, even when the commit SHA differs because GitHub used squash or merge commits.
- Reacquire a snapshot only when no verified local tree matches the current target tree. Verify its SHA-256 manifest and Git bundle before use.
- Never develop against an unverified older tree or reconstruct current source by downloading unrelated individual files.
- Before connector-based GitHub writes, read `docs/AGENT_GIT_WORKFLOW.md` and run `scripts/prepare_connector_publish.py` after the final local commit.
- Publish related multi-file changes atomically: exact committed blobs, one tree, one commit with the current remote target commit as parent, then one branch-ref creation/update.
- Stop at the first blob or tree SHA mismatch. Do not retry by copying, re-encoding, or manually editing file text.
- Create the feature branch only after the verified tree and commit exist, then compare it with the target and require `behind_by == 0` plus only expected paths.
- Repeated contents-API writes are only acceptable for a genuinely isolated single-file change.

## Development workflow

- Work on a feature branch and open a pull request; do not commit directly to `main`.
- Keep commits small, focused, and reviewable.
- Add or update tests for behavioral and numerical changes.
- Update `CHANGELOG.md` for user-visible release behavior. Update `README.md` only when user workflows materially change, and update `TEST_REPORT.md` only when validation strategy or durable results change; avoid rewriting large documents mechanically in every PR.
- Avoid committing generated images, benchmark output, virtual environments, build artifacts, or caches.
