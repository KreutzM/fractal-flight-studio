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

- Before modifying files, confirm that the working tree represents the current target branch. Prefer a normal up-to-date local clone.
- If no current clone is available, restore the latest successful repository-snapshot artifact: verify its SHA-256 manifest, run `git bundle verify`, and clone or fetch from the bundle.
- Never develop against an older snapshot and manually reconstruct the current repository from individual GitHub files.
- Before connector-based GitHub writes, read and follow `docs/AGENT_GIT_WORKFLOW.md`.
- For a related multi-file change through the GitHub API, use one atomic Git-data transaction: create all blobs, create one tree based on the current target tree, create one commit with the current target commit as parent, then create or update the feature-branch ref once.
- Do not use repeated contents-API `update_file` calls for a related multi-file change; each call creates an intermediate commit. Contents-API writes are acceptable for an intentional single-file change.
- Before opening a pull request, compare the feature branch with the target branch and confirm the expected paths, `behind_by == 0`, and no unrelated changes.

## Development workflow

- Work on a feature branch and open a pull request; do not commit directly to `main`.
- Keep commits small, focused, and reviewable.
- Add or update tests for behavioral and numerical changes.
- Update `README.md`, `CHANGELOG.md`, and `TEST_REPORT.md` when user-facing behavior, constraints, or validation changes.
- Avoid committing generated images, benchmark output, virtual environments, build artifacts, or caches.
