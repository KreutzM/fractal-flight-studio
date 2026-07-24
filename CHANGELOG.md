# Changelog

## 0.7.1 — 2026-07-24

### Flight safety

- Interactive flights now stop automatically at the last numerically useful viewport width.
- Mandelbrot perturbation limits use reference precision and the FP64 delta range; direct paths use the selected Float32/Float64 coordinate spacing.
- Automatic Mandelbrot rendering switches from direct Float32 calculation to perturbation before neighbouring pixels collapse.
- The final valid frame is rendered exactly at the limit and the GUI reports why the flight stopped.

## 0.7.0 — 2026-07-24

### Automatic tone mapping

- Added automatic contrast handling as the default presentation mode.
- Uses a deterministic, image-wide sample of at most 4096 outside pixels and
  robust percentile clipping instead of letting sparse extrema dominate the
  available palette range.
- Combines an adaptive `asinh` highlight compression curve with a bounded gamma
  correction derived from the sampled value distribution.
- Tone parameters are temporally smoothed across related pan and zoom frames;
  flights use stronger damping to avoid exposure pumping.
- Large scene changes converge faster, while viewport, resolution, palette and
  color-cycle changes do not unnecessarily reset exposure.
- Newton rendering keeps automatic mode linear so its three root regions remain
  correctly encoded.

### CUDA presentation path

- Adaptive tone mapping keeps iteration values and the inside mask on the GPU.
- CUDA transfers only a small stratified sample for parameter analysis and then
  performs tone curve, palette lookup and color cycling on the GPU.
- The optimized path still returns only the final RGB image, plus the small
  sample used for automatic exposure.

### Interface and tooling

- The GUI uses automatic tone mapping by default without requiring manual exposure controls.
- Added `--tone-mapping` to single-image, flight and benchmark CLI commands.
- CLI flights preserve and smooth tone state across their frame sequence.
- Reused renderer instances preserve temporally smoothed tone state across GUI frames.

### Validation

- Added automatic-curve, outlier-resistance, temporal-smoothing, scene-reset,
  Newton-preservation and large-frame sampling tests.
- Added CUDA-simulator parity coverage for the optimized automatic tone path.

## 0.6.0 — 2026-07-22

### Perturbation correctness and stability

- Replaced the previous per-frame reference anchoring with a persistent
  high-precision reference orbit cache.
- Related pan and zoom frames now reuse the same reference anchor; pixel
  offsets are computed relative to that anchor with arbitrary precision.
- Replaced the previous "repair by direct absolute FP64 continuation" with
  true perturbation rebasing. The deep parameter `c` is never reconstructed as
  an absolute float64 value.
- Added a cancellation-based glitch criterion and repair by rebasing the orbit
  representation to `Z_0 = 0`.
- Reference candidates are sampled across the current viewport and the
  longest-lived candidate is preferred, avoiding rapidly escaping reference
  orbits where possible.
- Escaped reference orbits have an explicit rebase limit, so kernels do not
  continue through overflowing reference values.
- CUDA keeps reused reference orbits resident on the device instead of
  uploading them for every frame.
- The GUI reports whether a perturbation reference was newly created or reused.

### Validation

- Added integer-pixel pan overlap regression tests; overlapping regions are
  bit-identical with a reused reference.
- Added `scripts/check_pan_stability.py` for reproducible CPU/CUDA validation on
  the target system.
- Expanded the test suite to 31 tests.

## 0.5.0 — 2026-07-22

### Deep zoom stability

- Added conservative rebasing / repair heuristics to the Mandelbrot
  perturbation renderer.
- Added glitch detection for unstable perturbation pixels.
- Unstable pixels switched from the perturbation path to a continued direct
  FP64 orbit from their current absolute state. This implementation was later
  replaced in 0.6.0 because it lost the deep parameter precision.
- CPU and CUDA backends report rebase/glitch activity.

## 0.4.0 — 2026-07-22

- Added Mandelbrot perturbation deep zoom with high-precision viewport storage.
- Added render modes `auto`, `direct`, and `perturbation`.
- Added configurable reference precision and CPU/CUDA perturbation kernels.

## 0.3.0 — 2026-07-22

- Added persistent CUDA buffers, true FP32/FP64 kernels, GPU palette mapping,
  and one RGB readback per interactive frame.
