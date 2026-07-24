# Changelog

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
