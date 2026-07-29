from __future__ import annotations

import numpy as np

from ..deep_zoom import direct_pixel_size, direct_precision_pixel_limit
from ..models import FractalKind, Precision, RenderMode, RenderRequest
from .cuda_double_single import (
    cuda_mandelbrot_double_single_kernel,
    launch_geometry as double_single_launch_geometry,
)
from .cuda_tonemap import CudaRenderer as _BaseCudaRenderer


class CudaRenderer(_BaseCudaRenderer):
    """CUDA renderer with an internal double-single Mandelbrot direct tier."""

    def __init__(self) -> None:
        super().__init__()
        self._last_arithmetic = Precision.FLOAT32.value

    @staticmethod
    def _can_use_double_single(request: RenderRequest) -> bool:
        if request.render_mode is not RenderMode.AUTO:
            return False
        if request.precision is not Precision.FLOAT64:
            return False
        if request.fractal is not FractalKind.MANDELBROT:
            return False
        if request.width >= 1 << 24 or request.height >= 1 << 24:
            return False
        return direct_pixel_size(request) > direct_precision_pixel_limit(
            request, Precision.FLOAT64
        )

    def _launch_fractal(self, request: RenderRequest, blocks, threads, perturb=None) -> float:
        if perturb is not None or not self._can_use_double_single(request):
            self._last_arithmetic = Precision.FLOAT64.value if (
                perturb is not None or request.precision is Precision.FLOAT64
            ) else Precision.FLOAT32.value
            return super()._launch_fractal(request, blocks, threads, perturb)

        try:
            geometry = double_single_launch_geometry(request)
        except (OverflowError, ValueError):
            self._last_arithmetic = Precision.FLOAT64.value
            return super()._launch_fractal(request, blocks, threads, perturb)

        cuda_mandelbrot_double_single_kernel[blocks, threads, self._stream](
            self._values_device,
            self._inside_device,
            request.width,
            request.height,
            *geometry,
            request.max_iterations,
            np.float32(request.escape_radius * request.escape_radius),
        )
        self._last_arithmetic = "double-single"
        return 0.0

    def _annotate_arithmetic(self, result):
        result.details["arithmetic"] = self._last_arithmetic
        result.details["double_single_enabled"] = self._last_arithmetic == "double-single"
        return result

    def render(self, request: RenderRequest):
        return self._annotate_arithmetic(super().render(request))

    def render_frame(self, request: RenderRequest, *args, **kwargs):
        return self._annotate_arithmetic(super().render_frame(request, *args, **kwargs))
