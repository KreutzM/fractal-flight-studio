# Test report

Date: 2026-07-24

## Environment

- Linux x86-64 build environment
- Python 3.13.5
- physical runtime backend available here: `cpu-numba`
- no NVIDIA driver or physical CUDA device exposed to the build environment
- CUDA behavior tested with the Numba CUDA simulator
- GUI tested with Tk under Xvfb

## Version 0.7.1 changes under test

- automatic flight termination before pixel coordinates lose useful numerical spacing
- precision-aware limits for perturbation, Float32 and Float64 render paths
- exact clamping to the final valid viewport width and deferred final-frame notification
- automatic robust percentile windowing
- adaptive `asinh` compression and bounded gamma correction
- deterministic image-wide sampling capped at 4096 pixels
- temporal smoothing across related frames and stronger damping for flights
- faster adaptation after large distribution changes
- automatic Newton fallback to linear tone mapping
- optimized CUDA sampling and GPU colorization without full value readback
- automatic GUI tone mapping and CLI tone-mapping selection
- persistent tone state in CLI flight sequences

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

Result: `45 passed`.

Coverage includes:

- viewport navigation and flight interpolation
- included fractal families and palettes
- FP32/FP64 direct rendering
- PNG and CLI rendering
- perturbation auto-selection and reference preparation
- direct-versus-perturbation numerical agreement
- stable reference reuse and bit-identical integer-pixel pan overlap
- CPU rebasing and glitch-repair metadata
- CUDA simulator parity for direct and perturbation paths
- persistent CUDA buffer, palette and reference-orbit reuse
- automatic tone expansion of narrow value bands
- resistance to sparse black/white outliers
- temporal smoothing and scene-key resets
- bounded stratified sampling on large frames
- preservation of Newton root encoding
- CPU/CUDA RGB parity for automatic tone mapping
- optimized CUDA automatic-tone path with small sample transfer
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

### CLI tone-mapping smoke tests

Single image:

```bash
PYTHONPATH=src python -m fractal_flight_studio.cli render \
  --backend cpu --width 160 --height 100 --iterations 120 \
  --tone-mapping auto --output /tmp/ffs-tone.png
```

Three-frame flight with persistent automatic tone state:

```bash
PYTHONPATH=src python -m fractal_flight_studio.cli flight \
  --backend cpu --width 96 --height 64 --iterations 80 \
  --tone-mapping auto --target-x -0.75 --target-y 0.1 \
  --target-width 1.5 --frames 3 --output-dir /tmp/ffs-tone-flight
```

Result: passed; all expected PNG files were created.

### GUI smoke test

```bash
xvfb-run -a env PYTHONPATH=src python scripts/gui_smoke.py
```

Result: passed.

### Wheel build

```bash
python -m pip wheel . --no-deps --no-build-isolation -w dist
```

Result: `fractal_flight_studio-0.7.1-py3-none-any.whl` built successfully.

## Not validated here

- physical RTX 3060 throughput and driver-specific behavior
- native CUDA PTX/SASS generated on Windows
- visual tone stability during a long real-time Windows/CUDA flight
- native macOS packaging

Run on the target RTX 3060 system:

```powershell
.\.venv\Scripts\python.exe scripts\check_pan_stability.py --backend cuda
.\.venv\Scripts\python.exe scripts\benchmark.py --backend all --repeats 5
```
