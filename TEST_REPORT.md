# Test report

Date: 2026-07-25

## Environment

- Linux x86-64 build environment
- Python 3.13.5
- physical runtime backend available here: `cpu-numba`
- no NVIDIA driver or physical CUDA device exposed to the build environment
- CUDA behavior tested with the Numba CUDA simulator
- GUI tested with Tk under Xvfb

## Version 0.7.2 changes under test

- renderer-level FP32/FP64 pixel-grid uniqueness and ULP-margin measurement
- automatic perturbation-reference re-anchoring before relative coordinates collapse
- a shared CPU/CUDA perturbation boundary raised when even a fresh grid is exhausted
- bounded RGB analysis for uniform colour fields, missing edge structure, repeated
  rows/columns and repeated two-dimensional pixel blocks
- rejection of an unsafe flight candidate before display
- restoration of the last good viewport and RGB frame after coordinate- or
  image-quality failure
- retention of the reference-bit/FP64 hard stop as a secondary safety limit

## Existing coverage retained

- FP32-to-FP64 promotion before direct-coordinate quantization
- FP64-to-perturbation transition for Mandelbrot auto mode
- strict precision behavior in explicit direct mode
- automatic robust tone mapping with temporal smoothing
- persistent renderer, palette, tone-state and reference-orbit reuse
- CPU/CUDA numerical and RGB parity checks

## Executed checks

### Static compilation

```bash
PYTHONPATH=src python -m py_compile \
  src/fractal_flight_studio/deep_zoom.py \
  src/fractal_flight_studio/flight_app.py \
  src/fractal_flight_studio/flight_quality.py \
  src/fractal_flight_studio/renderers/auto.py \
  tests/test_deep_zoom.py tests/test_flight_quality.py \
  tests/test_precision_transitions.py
```

Result: passed locally.

### Flight-grid, visual-quality and precision regressions

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_deep_zoom.py tests/test_flight_quality.py \
  tests/test_precision_transitions.py
```

Result: `22 passed` locally.

Coverage includes:

- detection of neighbouring coordinates that round to the same FP64 value
- automatic replacement of a stale deep-zoom reference before block formation
- direct auto-render grid metadata after FP32-to-FP64 promotion
- detection of uniform colour fields and repeated two-dimensional pixel blocks
- rejection of a visually exhausted candidate before the base GUI displays it
- visual gating of the numerically clamped final frame even after flight state clears
- last-good-frame restoration when an unsafe candidate reaches the GUI
- existing automatic precision promotion and hard numerical flight floor

### End-to-end default-flight simulation

A sequential CPU flight used the application defaults (`float32`, `auto`, 400
iterations, zoom factor `1.035`) and the canonical target
`-0.743643887037151 + 0.13182590420533i`. Each real rendered RGB frame was
classified before acceptance at 144×96 pixels.

Result: frame 411 remained accepted at viewport width `2.53270308551e-6`;
frame 412 was rejected at `2.44705612126e-6` because repeated rows and columns
formed a two-dimensional block raster. The rejected frame was not selected as
the last good frame.

### CPU pan stability

```bash
PYTHONPATH=src python scripts/check_pan_stability.py --backend cpu
```

Result:

```text
reference reused: True
maximum overlapping value difference: 0
inside/outside mismatches: 0
result: STABLE
```

### CUDA simulator paths

```bash
PYTHONPATH=src python -m pytest -q tests/test_renderer_frame_path.py \
  -k 'not cuda_auto_tone_mapping_stays_on_optimized_gpu_path'
```

Result: `4 passed, 1 deselected` locally. Direct and perturbation CUDA paths, reference reuse, RGB parity and rebasing metadata passed with the shared grid boundary enabled.

The complete automatic-tone CUDA simulator case is intentionally left to
GitHub Actions in this environment because that single simulator workload
exceeded the local execution timeout before the change as well.

### Service, CLI and tone mapping

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_service_and_cli.py tests/test_tonemapping.py
```

Result: `9 passed` locally.

### Full integration suite

The pull-request GitHub Actions matrix is authoritative for the complete suite
on Linux and Windows with Python 3.11, 3.12 and 3.13. The branch contains 53
tests before any CI-only additions.

### GUI smoke test

```bash
xvfb-run -a env PYTHONPATH=src python scripts/gui_smoke.py
```

Result: passed locally.

### Wheel build

```bash
python -m pip wheel . --no-deps --no-build-isolation -w dist
```

Result: `fractal_flight_studio-0.7.2-py3-none-any.whl` built locally. GitHub
Actions remains authoritative for the integrated cross-platform artifact.

## Not validated locally

- physical RTX 3060 behavior and performance
- native CUDA PTX/SASS generated on Windows
- visual smoothness and the exact stop point of a long real-time target flight
  on the physical target display; the automated checks validate the classifier
  and restoration logic, not subjective aesthetics
- native macOS packaging

Run on the target RTX 3060 system:

```powershell
.\.venv\Scripts\python.exe scripts\check_pan_stability.py --backend cuda
.\.venv\Scripts\python.exe scripts\benchmark.py --backend all --repeats 5
```
