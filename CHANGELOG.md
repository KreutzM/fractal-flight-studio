# Changelog

## Unreleased

### Unified right-click flight targets

- Right-click now opens a compact next-target proposal instead of starting an independent endless zoom flight.
- Free targets can edit exact coordinates, target width, transition mode, quality profile, palette and palette transition before being appended.
- Fresh plans are initialized from the exact camera used for the click only after the proposal is accepted; cancelling leaves the shared session unchanged.
- Catalog quick actions and the visual target browser now use the same automatic transition planner and add/add-and-play workflow.
- The visible legacy instant-flight controls were retired from the normal interface; real-time playback and MP4 export share the same flight plan.

### Validation

- Added regressions for exact suggested widths, fresh-plan initialization, cancellation safety and stale transition sources.
- Extended the Xvfb GUI smoke test through right-click proposal, acceptance, save/reload and catalog transition creation.


### Automatic multi-target transitions

- Added deterministic `auto`, `direct`, `bridge`, `overview` and `cut` routing when appending catalog targets to a flight plan.
- Auto mode chooses the smallest useful bridge width from exact center distance, viewport aspect ratio and both endpoint widths; it uses the full overview only when the bridge is already close to the root view.
- Generated camera and render cues remain ordinary editable timeline entries. Quality requirements are raised before arrival, while palette handling can blend, hold or cut.
- Added a compact target-transition dialog with route summary and “add and play” integration.

### Real-time flight-plan playback

- Added wall-clock-based play, pause, stop, seek, keyframe navigation and playback-rate controls for complete flight plans.
- Interactive playback evaluates the same camera, quality and palette timeline used by preflight and MP4 export.
- Slow renderers coalesce pending requests and jump directly to the latest playhead position instead of replaying obsolete intermediate frames.
- Manual camera interaction pauses plan playback, while timeline previews and the main playback bar share one session playhead.

### Validation

- Added transition-planner regressions for direct, bridge, overview and cut routes, aspect-ratio-aware bridge geometry, exact target coordinates, render-cue merging and atomic session updates.
- Extended the Xvfb GUI smoke test to append a catalog target through the transition workflow.
- Added deterministic controller tests for monotonic timing, pause/resume, seeking, rates and end-of-plan behavior.
- Extended the Xvfb GUI smoke test to cover seek, play, pause and stop.

## 0.9.0 — 2026-07-26

### Visual deep-zoom target browser

- Added a searchable target dialog with category filters, rendered previews,
  descriptions, exact coordinates, recommended settings and source links.
- Added a compressed atlas of 48×30 XPM previews for every curated target and a reproducible
  CPU thumbnail-generation script.
- Kept the compact quick selector and existing free right-click target workflow.

### Validation

- Added filtering, category and packaged-atlas regressions.
- Extended the Xvfb GUI smoke test to open and filter the visual browser.

## 0.8.0 — 2026-07-25

### Curated deep-zoom targets

- Added a packaged, schema-validated JSON catalog with ten curated Mandelbrot
  locations, exact text coordinates, initial view widths, descriptions, tags,
  source links and recommended render settings.
- Added compact controls that can set a catalog entry as the flight target or
  load its complete view while preserving the existing free right-click target.
- Applying a target also selects its recommended iteration count, reference
  precision and palette without converting deep coordinates to absolute floats.

### Validation

- Added catalog schema, exact-coordinate and GUI-application regressions.
- Extended the Xvfb GUI smoke test to exercise the compact target selector and
  exact flight-target application.
- Rendered every packaged target with its recommendations at low resolution and
  confirmed that all ten pass the existing visual-quality classifier.

## 0.7.2 — 2026-07-25

### Visual flight-quality stop

- Added a renderer-level pixel-grid quality check that measures whether
  neighbouring X/Y samples still map to distinct FP32/FP64 coordinates with a
  safety margin of at least four ULPs.
- Deep Mandelbrot flights now rebuild a stale perturbation reference before its
  relative FP64 grid can collapse into repeated coordinates.
- Each completed flight candidate is checked before display for near-uniform
  colour fields, missing edge structure, repeated rows/columns and repeated
  two-dimensional pixel blocks.
- If either the coordinate grid or the rendered image loses useful resolution,
  the GUI rejects that candidate, restores the last good view and stops before
  block or colour-field artifacts are displayed.
- Direct auto-render frames expose grid uniqueness and ULP margin in renderer
  metadata; an exhausted fresh perturbation grid is reported as an explicit
  render boundary.

### Validation

- Added regressions for collapsed coordinate grids, automatic reference
  re-anchoring, uniform colour fields, repeated pixel blocks and last-good-frame
  restoration.

## 0.7.1 — 2026-07-25

### Flight and precision stability

- Added an automatic direct-precision ladder in `auto` mode: fast `float32`
  frames are promoted to `float64` before FP32 coordinate quantization becomes
  visible, followed by Mandelbrot perturbation when direct FP64 becomes unsafe.
- `direct` mode continues to honor the explicitly selected precision without
  hidden promotion.
- Added a conservative minimum viewport width derived from reference bits,
  render width and the FP64 perturbation-delta floor.
- Interactive flights now clamp to that width and stop automatically instead of
  continuing into blocky or single-colour frames.
- The GUI status reports effective precision transitions such as
  `float32→float64`.

### Validation

- Added regression coverage for FP32 promotion, FP64-to-perturbation switching,
  strict direct mode, finite reference-bit flight floors and automatic flight
  stopping.

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
