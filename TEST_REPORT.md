# Test report

Date: 2026-07-22

## Environment

- Linux x86-64 build environment
- Python 3.13.5
- physical runtime backend available here: `cpu-numba`
- no NVIDIA driver or physical CUDA device exposed to the build environment
- CUDA behavior tested with the Numba CUDA simulator
- GUI tested with Tk under Xvfb

## Version 0.6.0 changes under test

- persistent reference orbit across related pan/zoom frames
- high-precision viewport-to-reference offsets
- true perturbation rebasing without absolute FP64 deep coordinates
- cancellation-based glitch repair by rebasing to `Z_0 = 0`
- longest-lived reference selection from viewport candidates
- explicit rebase limit for escaped reference orbits
- reused CUDA reference orbit retained on the device

## Executed checks

### Static compilation

```bash
python -m py_compile src/fractal_flight_studio/*.py \
  src/fractal_flight_studio/renderers/*.py tests/*.py
```

Result: passed.

### Automated test suite

```bash
PYTHONPATH=src pytest -q
```

Result: `31 passed`.

Coverage includes:

- viewport navigation and flight interpolation
- included fractal families and palettes
- FP32/FP64 direct rendering
- PNG and CLI rendering
- perturbation auto-selection and reference preparation
- direct-versus-perturbation numerical agreement
- stable reference reuse after a pan
- bit-identical overlap after an integer-pixel pan
- CPU rebasing and glitch-repair metadata
- CUDA simulator parity for direct and perturbation frame paths
- CUDA simulator parity for rebase/glitch behavior
- persistent CUDA buffer, palette and reference-orbit reuse
- Windows launcher and CUDA diagnostics

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

### High-precision spot validation

Selected perturbation pixels were compared with direct `mpmath` Mandelbrot
orbits. Inside/outside classifications matched; normalized smooth-value errors
were in the low `1e-9` range for the sampled escaping points.

### GUI smoke test

```bash
xvfb-run -a env PYTHONPATH=src python scripts/gui_smoke.py
```

Result: passed.


### Wheel build

```bash
python -m pip wheel . --no-deps --no-build-isolation -w dist
```

Result: `fractal_flight_studio-0.6.0-py3-none-any.whl` built successfully.

## Not validated here

- physical RTX 3060 throughput and driver-specific behavior
- native CUDA PTX/SASS generated on Windows
- Windows Tk display timing during a long deep-zoom flight
- native macOS packaging

Run on the target RTX 3060 system:

```powershell
.\.venv\Scripts\python.exe scripts\check_pan_stability.py --backend cuda
.\.venv\Scripts\python.exe scripts\benchmark.py --backend all --repeats 5
```
