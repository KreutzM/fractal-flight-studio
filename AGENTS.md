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

## Development workflow

- Work on a feature branch and open a pull request; do not commit directly to `main`.
- Keep commits small, focused, and reviewable.
- Add or update tests for behavioral and numerical changes.
- Update `README.md`, `CHANGELOG.md`, and `TEST_REPORT.md` when user-facing behavior, constraints, or validation changes.
- Avoid committing generated images, benchmark output, virtual environments, build artifacts, or caches.
