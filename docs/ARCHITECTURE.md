# Architecture

Fractal Flight Studio separates numerical rendering, application state and Tk presentation so that interactive preview, path editing and offline video rendering can reuse the same core behavior.

## Main components

```text
Tk GUI (`app.py`, `app_ui.py`, `flight_app.py`)
    ├── CameraState
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

### `RenderController`

`RenderController` owns the single render worker, request generations and invalidation coalescing. Tk remains responsible only for scheduling a non-blocking poll and displaying the completed image.

A new UI change invalidates the current generation. If a render is already active, no second worker job is queued. When the active job completes, the GUI submits one render for the newest state.

This boundary is intentionally independent of Tk so a later offline renderer can use the same lifecycle rules with a different scheduler.

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
- X/Y/zoom keyframes produce `CameraState` values and do not manipulate Tk variables directly;
- offline frame jobs call renderers through a non-Tk orchestration layer;
- video encoding consumes completed RGB or higher-bit-depth frames and does not own camera interpolation;
- temporal tone state belongs to a render session, not to widgets;
- persistent projects serialize camera/keyframe text without reducing it to absolute `float` values.

## Testing strategy

- camera and controller behavior is tested without Tk;
- renderer precision and CPU/CUDA parity remain covered by numerical tests;
- the Xvfb smoke test verifies only the assembled GUI wiring;
- physical CUDA performance and Windows packaging remain separate target-system checks.

## Target browser

`target_browser.py` owns target search, category filtering, packaged preview loading and the browser window. It receives callbacks for applying a target; it
does not mutate camera, renderer or flight state directly. Preview generation
is reproducible through `scripts/generate_target_thumbnails.py`.
