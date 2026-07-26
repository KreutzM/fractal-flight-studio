# Architecture

Fractal Flight Studio separates numerical rendering, application state and Tk presentation so that interactive preview, path editing and offline video rendering can reuse the same core behavior.

## Main components

```text
Tk GUI (`app.py`, `app_ui.py`, `flight_app.py`)
    ├── CameraState
    ├── CameraPath / FlightKeyframe
    ├── path preflight
    ├── offline frame planning / rendering
    ├── RenderController
    ├── FlightController
    ├── target catalog
    └── renderer selection
            ├── CPU renderer
            ├── CUDA renderer
            └── adaptive precision / perturbation
```

### `CameraState`

`CameraState` is the canonical camera representation. It stores the center and view width as decimal text and performs navigation with `mpmath` precision selected from the configured reference bits.

The floating-point `Viewport` inside `RenderRequest` is only a compatibility proxy for direct FP32/FP64 rendering. Deep-zoom setup must continue to use the exact text fields carried by the request.

Responsibilities:

- preserve exact center and width text;
- convert to high-precision values for pan, zoom and flight movement;
- produce a bounded float proxy for direct render paths;
- construct camera snapshots from completed render requests;
- define fractal-specific reset views.

### `CameraPath` and `FlightKeyframe`

`FlightKeyframe` stores an exact decimal timeline position, a `CameraState` and the easing curve for its outgoing segment. `CameraPath` validates an immutable sequence of at least two keyframes that starts at zero seconds and has strictly increasing times.

Path evaluation is independent of Tk, rendering speed and wall-clock time:

- X and Y are interpolated with the path's configured `mpmath` precision;
- view width is interpolated in logarithmic space for visually uniform zoom speed;
- `linear`, `smoothstep` and `smootherstep` easing are available per segment;
- evaluation before or after the timeline returns the exact endpoint camera;
- camera text is never reduced to absolute FP64 values.

This component is the common camera source for a timeline editor, low-resolution preflight and deterministic offline frame renderer.

### Path preflight

`preflight.py` performs a bounded diagnostic render pass over a `CameraPath` without depending on Tk or wall-clock scheduling.

- The path is sampled at exact decimal times and always includes both endpoints.
- A configurable sample cap evenly decimates very long paths without first expanding an unbounded time list.
- Every sample derives a low-resolution `RenderRequest` from an immutable request template while retaining exact camera text.
- Tone state is local to the preflight run and is not stored in widgets or the renderer's implicit GUI session.
- Renderer pixel-grid metadata, explicit grid exhaustion, runtime failures and the shared RGB visual-quality classifier produce structured issues.
- The result is an immutable `PreflightReport`; RGB frames are deliberately not retained.

This layer diagnoses a path before expensive offline rendering. It does not own timeline editing, full-resolution frame production or video encoding.

### Offline frame rendering

`offline_render.py` turns a validated `CameraPath` into deterministic full-resolution frame jobs and rendered RGB frames without depending on Tk, timers or output files.

- Frame cadence is represented exactly by an integer numerator and denominator, including rates such as `30000/1001`.
- `OfflineFramePlan` stores only the duration, cadence and frame count; individual times are calculated lazily by frame index instead of expanding a large timeline.
- A configurable frame cap rejects accidental oversized jobs before rendering begins.
- An exact endpoint may be appended when the path duration is not on the regular cadence. Consumers that require cadence-only output can disable this behavior.
- `iter_offline_frame_jobs` supports deterministic start/stop index ranges for resumable or chunked work.
- Every job derives an immutable `RenderRequest` from the template while retaining exact camera text.
- A single frame can be rendered independently by index. Automatic tone mapping is intentionally stateless at this stage so results do not depend on previously rendered frames or chunk boundaries.
- `OfflineFrame` owns a copied 8-bit RGB array and compact scalar metadata. The iterator does not retain earlier frames.
- Renderer failures are wrapped with the exact frame index and timeline time.

This layer produces frames only. PNG writing, FFmpeg processes, temporal production tone state and higher-bit-depth output remain separate responsibilities.

### `RenderController`

`RenderController` owns the interactive single-render worker, request generations and invalidation coalescing. Tk remains responsible only for scheduling a non-blocking poll and displaying the completed image.

A new UI change invalidates the current generation. If a render is already active, no second worker job is queued. When the active job completes, the GUI submits one render for the newest state.

This boundary remains specific to interactive rendering. Offline rendering follows its deterministic frame plan directly and does not inherit GUI invalidation or coalescing behavior.

### `FlightController`

`FlightController` owns:

- the exact flight target;
- running/stopped state;
- the logarithmic zoom step toward the target;
- numerical final-frame state;
- the last accepted camera and RGB frame.

The Tk adapter decides when to schedule the next step. `flight_app.py` applies the numerical and visual quality gates to completed frames and asks the controller to accept or reject them.

### GUI adapters

`app_ui.py` builds the control widgets. `app.py` translates widget values into `RenderRequest`, displays images and formats status text. It must not implement deep-zoom arithmetic or worker lifecycle state directly.

`flight_app.py` adds the curated target strip and the flight-result quality gate. It should remain an adapter over the controllers rather than a second application state store.

### Renderers

Renderer modules remain responsible for numerical values, perturbation, CUDA execution, tone mapping and RGB production. They receive immutable `RenderRequest` values and must not depend on Tk or controller classes.

## Extension rules

Future PRs should follow these boundaries:

- target previews and search belong to separate UI components backed by the existing catalog;
- timeline editors build `FlightKeyframe` and `CameraPath` values and do not manipulate Tk variables directly;
- preflight evaluates a path through `run_path_preflight` and reports diagnostics without retaining frame images;
- full-resolution work is planned with `build_offline_frame_plan`, evaluated with `iter_offline_frame_jobs` and rendered through the stateless offline-frame API;
- video encoding consumes completed RGB or higher-bit-depth frames and does not own camera interpolation;
- temporal tone state belongs to a render session, not to widgets;
- persistent projects serialize camera/keyframe text without reducing it to absolute `float` values.

## Testing strategy

- camera, path, preflight, offline planning and controller behavior is tested without Tk;
- preflight workload planning and diagnostics use deterministic fake renderers;
- offline frame cadence, random-access jobs, RGB ownership and contextual failures use deterministic fake renderers;
- renderer precision and CPU/CUDA parity remain covered by numerical tests;
- the Xvfb smoke test verifies only the assembled GUI wiring;
- physical CUDA performance and Windows packaging remain separate target-system checks.

## Target browser

`target_browser.py` owns target search, category filtering, packaged preview loading and the browser window. It receives callbacks for applying a target; it
does not mutate camera, renderer or flight state directly. Preview generation
is reproducible through `scripts/generate_target_thumbnails.py`.
