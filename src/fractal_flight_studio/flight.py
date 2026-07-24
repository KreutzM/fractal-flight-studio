from __future__ import annotations

from dataclasses import dataclass
import sys

import mpmath as mp
from .deep_zoom import coordinate_ulp
from .models import FractalKind, Precision, RenderMode, RenderRequest

# Keep several representable coordinate steps between neighbouring pixels.
# This stops before adjacent pixels collapse onto the same numerical value.
_DIRECT_ULP_MARGIN = 8
_PERTURBATION_ULP_MARGIN = 32
_PERTURBATION_NORMAL_MARGIN = 32
_FLIGHT_ATTRACTION = mp.mpf("0.08")


@dataclass(frozen=True, slots=True)
class FlightLimit:
    minimum_width: mp.mpf
    mode: str


@dataclass(frozen=True, slots=True)
class FlightStep:
    center_x: mp.mpf
    center_y: mp.mpf
    width: mp.mpf
    stopped: bool
    limit: FlightLimit


def _coordinate_scale(request: RenderRequest, target_x: mp.mpf, target_y: mp.mpf) -> mp.mpf:
    center_x = mp.mpf(request.center_x_text or repr(request.viewport.center_x))
    center_y = mp.mpf(request.center_y_text or repr(request.viewport.center_y))
    return max(mp.mpf(1), abs(center_x), abs(center_y), abs(target_x), abs(target_y))


def minimum_flight_width(
    request: RenderRequest,
    target_x: mp.mpf,
    target_y: mp.mpf,
) -> FlightLimit:
    """Return the smallest viewport width that still has useful pixel spacing."""

    scale = _coordinate_scale(request, target_x, target_y)
    image_width = mp.mpf(max(1, request.width))
    uses_perturbation = (
        request.fractal is FractalKind.MANDELBROT
        and request.render_mode is not RenderMode.DIRECT
    )

    if uses_perturbation:
        reference_ulp = scale * mp.power(2, 1 - int(request.reference_bits))
        delta_floor = mp.mpf(repr(sys.float_info.min))
        pixel_floor = max(
            reference_ulp * _PERTURBATION_ULP_MARGIN,
            delta_floor * _PERTURBATION_NORMAL_MARGIN,
        )
        return FlightLimit(pixel_floor * image_width, "Perturbations-/Referenzpräzision")

    pixel_floor = mp.mpf(repr(coordinate_ulp(float(scale), request.precision))) * _DIRECT_ULP_MARGIN
    return FlightLimit(pixel_floor * image_width, f"{request.precision.value}-Koordinatenpräzision")


def advance_flight(
    request: RenderRequest,
    target_x: mp.mpf,
    target_y: mp.mpf,
    rate: float,
) -> FlightStep:
    """Advance one GUI flight frame and clamp it to the numerical limit."""

    center_x = mp.mpf(request.center_x_text or repr(request.viewport.center_x))
    center_y = mp.mpf(request.center_y_text or repr(request.viewport.center_y))
    width = mp.mpf(request.view_width_text or repr(request.viewport.width))
    limit = minimum_flight_width(request, target_x, target_y)
    if width <= limit.minimum_width:
        return FlightStep(center_x, center_y, width, True, limit)

    next_center_x = center_x + (target_x - center_x) * _FLIGHT_ATTRACTION
    next_center_y = center_y + (target_y - center_y) * _FLIGHT_ATTRACTION
    next_width = width / mp.mpf(max(1.0001, rate))
    stopped = next_width <= limit.minimum_width
    if stopped:
        next_width = limit.minimum_width

    return FlightStep(next_center_x, next_center_y, next_width, stopped, limit)
