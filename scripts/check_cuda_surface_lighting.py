from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import platform
import statistics
import time
from typing import Iterable

import numba
import numpy as np

from fractal_flight_studio.deep_zoom import should_use_perturbation
from fractal_flight_studio.models import Precision, RenderMode, RenderRequest, Viewport
from fractal_flight_studio.palettes import tone_mapped_colorize
from fractal_flight_studio.renderers.cuda_double_single_renderer import CudaRenderer
from fractal_flight_studio.surface_lighting import (
    SurfaceLightingSettings,
    apply_surface_lighting,
)


@dataclass(frozen=True, slots=True)
class ValidationCase:
    id: str
    request: RenderRequest
    expected_arithmetic: str
    expected_render_mode: str


def _cases(width: int, height: int) -> tuple[ValidationCase, ...]:
    return (
        ValidationCase(
            "direct-fp32",
            RenderRequest(
                width=width,
                height=height,
                max_iterations=320,
                precision=Precision.FLOAT32,
                render_mode=RenderMode.DIRECT,
            ),
            "float32",
            "direct",
        ),
        ValidationCase(
            "direct-double-single",
            RenderRequest(
                width=width,
                height=height,
                max_iterations=800,
                precision=Precision.FLOAT64,
                render_mode=RenderMode.AUTO,
                center_x_text="-0.743643887037",
                center_y_text="0.131825904205",
                view_width_text="0.0001",
                viewport=Viewport(-0.743643887037, 0.131825904205, 0.0001),
            ),
            "double-single",
            "direct",
        ),
        ValidationCase(
            "deep-double-single-perturbation",
            RenderRequest(
                width=width,
                height=height,
                max_iterations=1200,
                precision=Precision.FLOAT64,
                render_mode=RenderMode.AUTO,
                reference_bits=384,
                center_x_text="-0.743643887037151",
                center_y_text="0.13182590420533",
                view_width_text="1e-13",
                viewport=Viewport(
                    -0.743643887037151,
                    0.13182590420533,
                    1e-13,
                ),
            ),
            "double-single",
            "perturbation",
        ),
    )


def _median_frame_seconds(
    renderer: CudaRenderer,
    request: RenderRequest,
    settings: SurfaceLightingSettings | None,
    repeats: int,
) -> float:
    for _ in range(2):
        renderer.render_frame(
            request,
            tone_mapping="linear",
            surface_lighting=settings,
        )
    samples = []
    for _ in range(repeats):
        result = renderer.render_frame(
            request,
            tone_mapping="linear",
            surface_lighting=settings,
        )
        samples.append(float(result.elapsed_seconds))
    return statistics.median(samples)


def validate_case(
    renderer: CudaRenderer,
    case: ValidationCase,
    settings: SurfaceLightingSettings,
    repeats: int,
) -> dict[str, object]:
    planned_render_mode = (
        "perturbation" if should_use_perturbation(case.request) else "direct"
    )
    if planned_render_mode != case.expected_render_mode:
        raise RuntimeError(
            f"validation case {case.id!r} plans {planned_render_mode}, "
            f"expected {case.expected_render_mode}; adjust its view or dimensions"
        )

    rendered = renderer.render(case.request)
    colored, _tone_state, _tone_details = tone_mapped_colorize(
        rendered.values,
        rendered.inside,
        palette="inferno",
        tone_mapping="linear",
    )
    expected = apply_surface_lighting(
        rendered.values,
        rendered.inside,
        colored,
        settings,
    )
    actual = renderer.render_frame(
        case.request,
        palette="inferno",
        tone_mapping="linear",
        surface_lighting=settings,
    )
    baseline = renderer.render_frame(case.request, tone_mapping="linear")
    disabled = renderer.render_frame(
        case.request,
        tone_mapping="linear",
        surface_lighting=SurfaceLightingSettings(enabled=False),
    )

    delta = np.abs(actual.rgb.astype(np.int16) - expected.astype(np.int16))
    maximum_delta = int(delta.max(initial=0))
    mismatch_fraction = float(np.count_nonzero(delta) / delta.size)
    disabled_matches = bool(np.array_equal(disabled.rgb, baseline.rgb))
    optimized = bool(actual.details.get("optimized_frame_path"))
    transfer = str(actual.details.get("transfer", ""))
    arithmetic = str(actual.details.get("arithmetic", ""))
    render_mode = str(actual.details.get("render_mode", ""))
    route_matches = (
        arithmetic == case.expected_arithmetic
        and render_mode == case.expected_render_mode
    )

    unlit_seconds = _median_frame_seconds(
        renderer, case.request, None, repeats
    )
    lit_seconds = _median_frame_seconds(
        renderer, case.request, settings, repeats
    )

    passed = (
        maximum_delta <= 1
        and disabled_matches
        and optimized
        and transfer == "single RGB readback"
        and route_matches
    )
    return {
        "id": case.id,
        "passed": passed,
        "maximum_channel_delta": maximum_delta,
        "channel_mismatch_fraction": mismatch_fraction,
        "disabled_matches_baseline": disabled_matches,
        "optimized_frame_path": optimized,
        "transfer": transfer,
        "render_mode": render_mode,
        "planned_render_mode": planned_render_mode,
        "arithmetic": arithmetic,
        "expected_render_mode": case.expected_render_mode,
        "expected_arithmetic": case.expected_arithmetic,
        "route_matches": route_matches,
        "median_unlit_seconds": unlit_seconds,
        "median_lit_seconds": lit_seconds,
        "lighting_overhead_seconds": lit_seconds - unlit_seconds,
        "lighting_time_ratio": lit_seconds / unlit_seconds if unlit_seconds else None,
    }


def run(
    cases: Iterable[ValidationCase],
    settings: SurfaceLightingSettings,
    repeats: int,
) -> dict[str, object]:
    renderer = CudaRenderer()
    if not renderer.is_available():
        raise RuntimeError("CUDA is not available")
    records = [validate_case(renderer, case, settings, repeats) for case in cases]
    return {
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "numba": numba.__version__,
            "device": renderer._device_name(),
        },
        "settings": asdict(settings),
        "cases": records,
        "passed": all(bool(record["passed"]) for record in records),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate GPU-native surface lighting on a physical CUDA device."
    )
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=180)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.width <= 0 or args.height <= 0:
        parser.error("dimensions must be positive")
    if args.repeats < 1:
        parser.error("repeats must be at least one")

    settings = SurfaceLightingSettings(
        enabled=True,
        strength=2.0,
        azimuth_degrees=315.0,
        elevation_degrees=45.0,
        ambient=0.35,
        diffuse=0.65,
    )
    started = time.perf_counter()
    report = run(_cases(args.width, args.height), settings, args.repeats)
    report["elapsed_seconds"] = time.perf_counter() - started
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
