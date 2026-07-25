# Test report

Date: 2026-07-25

## Environment

- Linux x86-64 build environment
- Python 3.13.5
- physical runtime backend available here: `cpu-numba`
- no NVIDIA driver or physical CUDA device exposed to the build environment
- CUDA behavior tested with the Numba CUDA simulator
- GUI tested with Tk under Xvfb

## Version 0.7.1 changes under test

- FP32-to-FP64 promotion before direct-coordinate quantization
- FP64-to-perturbation transition for Mandelbrot auto mode
- strict precision behavior in explicit direct mode
- reference-bit and FP64-derived minimum viewport width
- automatic flight clamp and stop at the numerical limit
- effective-precision reporting in renderer details and the GUI
- compatibility with automatic tone mapping and reused renderer instances

## Executed checks

### Static compilation

```bash
PYTHONPATH=src python -m compileall -q src tests scripts
```

Result: passed.

### Local compatibility suite

The implementation was first validated against the complete 0.6.0 core suite,
which contains the unchanged navigation, direct-render and perturbation kernels,
plus the new regression tests:

```bash
PYTHONPATH=src python -m pytest -vv
```

Result: `37 passed`.

The merged 0.7.0 branch adds eight tone-mapping tests. The GitHub Actions branch
suite is therefore expected to contain `45` tests and is the authoritative
validation for the complete current-main integration.

Coverage added for this fix includes:

- safe FP32 promotion while remaining in direct mode
- perturbation selection only after the promoted FP64 limit
- no implicit promotion in explicit direct mode
- deeper but finite flight floors for higher reference-bit settings
- final-frame clamping and no further timer scheduling after flight stop
- renderer-instance reuse with adaptive precision

### Pan-stability check

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

### GUI smoke test

```bash
xvfb-run -a env PYTHONPATH=src python scripts/gui_smoke.py
```

Result: passed.

## Not validated here

- physical RTX 3060 performance of the FP32-to-FP64 transition
- native CUDA PTX/SASS generated on Windows
- visual behavior during a long real-time flight on the target system
- native macOS packaging

Run on the target RTX 3060 system:

```powershell
.\.venv\Scripts\python.exe scripts\check_pan_stability.py --backend cuda
.\.venv\Scripts\python.exe scripts\benchmark.py --backend all --repeats 5
```
