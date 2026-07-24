from dataclasses import replace

import numpy as np
import pytest

from fractal_flight_studio.models import FractalKind, Precision, RenderRequest, Viewport
from fractal_flight_studio.renderers.cpu import CpuRenderer


@pytest.fixture(scope="module")
def renderer():
    instance = CpuRenderer()
    instance.warm_up()
    return instance


@pytest.mark.parametrize("kind", list(FractalKind))
def test_all_fractals_render_finite_arrays(renderer, kind):
    request = RenderRequest(
        width=64,
        height=48,
        fractal=kind,
        max_iterations=60,
        viewport=Viewport(0.0, 0.0, 4.0) if kind is FractalKind.NEWTON else Viewport(),
    )
    result = renderer.render(request)
    assert result.values.shape == (48, 64)
    assert result.inside.shape == (48, 64)
    assert np.isfinite(result.values).all()
    assert (result.values >= 0).all()
    assert (result.values <= 1).all()


def test_mandelbrot_known_inside_and_outside(renderer):
    request = RenderRequest(width=3, height=1, viewport=Viewport(0.0, 0.0, 4.0), max_iterations=200)
    result = renderer.render(request)
    # Center pixel samples c=0; the right pixel samples c=4/3.
    assert result.inside[0, 1]
    assert not result.inside[0, 2]


def test_float32_and_float64_are_close_for_normal_view(renderer):
    request = RenderRequest(width=80, height=60, max_iterations=80, precision=Precision.FLOAT32)
    a = renderer.render(request)
    b = renderer.render(replace(request, precision=Precision.FLOAT64))
    agreement = np.mean(a.inside == b.inside)
    assert agreement > 0.995
