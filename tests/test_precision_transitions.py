from __future__ import annotations

from types import SimpleNamespace

import mpmath as mp

from fractal_flight_studio.app import FractalStudioApp
from fractal_flight_studio.deep_zoom import (
    digits_for_bits,
    effective_direct_precision,
    minimum_safe_view_width,
    should_use_perturbation,
)
from fractal_flight_studio.models import Precision, RenderMode, RenderRequest, Viewport
from fractal_flight_studio.renderers import select_renderer

DEEP_CENTER_X = "-0.743643887037158704752191506114774"
DEEP_CENTER_Y = "0.131825904205311970493132056385139"


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _Root:
    def __init__(self) -> None:
        self.after_calls = []

    def after(self, *args):
        self.after_calls.append(args)


def test_auto_promotes_float32_before_coordinate_quantization():
    request = RenderRequest(
        width=800,
        height=600,
        viewport=Viewport(-0.5, 0.0, 1e-4),
        precision=Precision.FLOAT32,
        render_mode=RenderMode.AUTO,
        center_x_text="-0.5",
        center_y_text="0.0",
        view_width_text="1e-4",
    )
    assert effective_direct_precision(request) is Precision.FLOAT64
    assert should_use_perturbation(request) is False


def test_auto_uses_perturbation_after_float64_limit():
    request = RenderRequest(
        width=800,
        height=600,
        viewport=Viewport(-0.5, 0.0, 1e-13),
        precision=Precision.FLOAT32,
        render_mode=RenderMode.AUTO,
        center_x_text="-0.5",
        center_y_text="0.0",
        view_width_text="1e-13",
    )
    assert effective_direct_precision(request) is Precision.FLOAT64
    assert should_use_perturbation(request) is True


def test_direct_mode_never_promotes_or_switches_implicitly():
    request = RenderRequest(
        width=800,
        height=600,
        viewport=Viewport(-0.5, 0.0, 1e-13),
        precision=Precision.FLOAT32,
        render_mode=RenderMode.DIRECT,
        center_x_text="-0.5",
        center_y_text="0.0",
        view_width_text="1e-13",
    )
    assert effective_direct_precision(request) is Precision.FLOAT32
    assert should_use_perturbation(request) is False


def test_reference_bits_define_a_finite_flight_floor():
    request_256 = RenderRequest(
        width=1000,
        height=700,
        precision=Precision.FLOAT32,
        render_mode=RenderMode.AUTO,
        reference_bits=256,
        center_x_text=DEEP_CENTER_X,
        center_y_text=DEEP_CENTER_Y,
        view_width_text="1e-20",
    )
    request_512 = RenderRequest(
        width=request_256.width,
        height=request_256.height,
        precision=request_256.precision,
        render_mode=request_256.render_mode,
        reference_bits=512,
        center_x_text=request_256.center_x_text,
        center_y_text=request_256.center_y_text,
        view_width_text=request_256.view_width_text,
    )
    floor_256 = minimum_safe_view_width(request_256)
    floor_512 = minimum_safe_view_width(request_512)
    assert floor_256 > 0
    assert floor_512 > 0
    assert floor_512 < floor_256
    assert floor_256 > mp.mpf("1e-80")


def test_cpu_auto_reports_float32_to_float64_promotion():
    renderer = select_renderer("cpu")
    request = RenderRequest(
        width=40,
        height=30,
        max_iterations=40,
        viewport=Viewport(-0.5, 0.0, 1e-6),
        precision=Precision.FLOAT32,
        render_mode=RenderMode.AUTO,
        center_x_text="-0.5",
        center_y_text="0.0",
        view_width_text="1e-6",
    )
    result = renderer.render(request)
    assert result.details["render_mode"] == "direct"
    assert result.details["requested_precision"] == "float32"
    assert result.details["precision"] == "float64"
    assert result.details["precision_promoted"] is True


def test_flight_stops_at_numerical_precision_floor():
    bits = 64
    base_request = RenderRequest(
        width=100,
        height=80,
        viewport=Viewport(-0.5, 0.0, 1e-10),
        precision=Precision.FLOAT32,
        render_mode=RenderMode.AUTO,
        reference_bits=bits,
        center_x_text="-0.5",
        center_y_text="0.0",
        view_width_text="1e-10",
    )
    floor = minimum_safe_view_width(base_request)
    current_width = floor * mp.mpf("1.01")
    request = RenderRequest(
        width=base_request.width,
        height=base_request.height,
        viewport=Viewport(-0.5, 0.0, float(current_width)),
        precision=base_request.precision,
        render_mode=base_request.render_mode,
        reference_bits=bits,
        center_x_text="-0.5",
        center_y_text="0.0",
        view_width_text=mp.nstr(current_width, 40),
    )

    app = SimpleNamespace()
    app.flight_running = True
    app.flight_target_text = ("-0.5", "0.0")
    app.flight_rate_var = _Var(1.035)
    app.flight_scale_var = _Var(1.0)
    app.reference_bits_var = _Var(bits)
    app.root = _Root()
    app._work_digits = lambda: digits_for_bits(bits)
    app._request = lambda _scale: request
    app._view_values = lambda: (mp.mpf("-0.5"), mp.mpf("0.0"), current_width)
    app.final_view = None
    app._set_view_values = lambda x, y, width: setattr(app, "final_view", (x, y, width))
    app.render_count = 0
    app.request_render = lambda: setattr(app, "render_count", app.render_count + 1)
    app.stop_message = None

    def stop_flight(message=None):
        app.flight_running = False
        app.stop_message = message

    app._stop_flight = stop_flight

    FractalStudioApp._flight_step(app)

    assert app.flight_running is False
    assert app.render_count == 1
    assert app.root.after_calls == []
    assert app.final_view is not None
    assert app.final_view[2] == floor
    assert "Präzisionsgrenze" in app.stop_message
