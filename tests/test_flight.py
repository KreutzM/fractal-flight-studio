import mpmath as mp

from fractal_flight_studio.flight import advance_flight, minimum_flight_width
from fractal_flight_studio.models import FractalKind, Precision, RenderMode, RenderRequest, Viewport


def _request(**changes) -> RenderRequest:
    values = dict(
        width=1000,
        height=700,
        viewport=Viewport(-0.75, 0.1, 1.0),
        center_x_text="-0.75",
        center_y_text="0.1",
        view_width_text="1.0",
        fractal=FractalKind.MANDELBROT,
        precision=Precision.FLOAT64,
        render_mode=RenderMode.AUTO,
        reference_bits=256,
    )
    values.update(changes)
    return RenderRequest(**values)


def test_perturbation_limit_uses_reference_precision():
    target_x = mp.mpf("-0.743643887037151")
    target_y = mp.mpf("0.13182590420533")
    limit_128 = minimum_flight_width(_request(reference_bits=128), target_x, target_y)
    limit_256 = minimum_flight_width(_request(reference_bits=256), target_x, target_y)
    assert limit_256.minimum_width < limit_128.minimum_width
    assert limit_128.minimum_width / limit_256.minimum_width == mp.power(2, 128)


def test_direct_float32_stops_before_float64():
    target_x = mp.mpf("-0.7")
    target_y = mp.mpf("0.0")
    direct32 = _request(
        fractal=FractalKind.JULIA,
        precision=Precision.FLOAT32,
        render_mode=RenderMode.DIRECT,
    )
    direct64 = _request(
        fractal=FractalKind.JULIA,
        precision=Precision.FLOAT64,
        render_mode=RenderMode.DIRECT,
    )
    assert minimum_flight_width(direct32, target_x, target_y).minimum_width > minimum_flight_width(
        direct64, target_x, target_y
    ).minimum_width


def test_advance_flight_clamps_exactly_to_limit():
    base = _request()
    target_x = mp.mpf("-0.743643887037151")
    target_y = mp.mpf("0.13182590420533")
    limit = minimum_flight_width(base, target_x, target_y)
    width = limit.minimum_width * mp.mpf("1.01")
    request = _request(view_width_text=mp.nstr(width, 100), viewport=Viewport(-0.75, 0.1, float(width)))
    step = advance_flight(request, target_x, target_y, 1.035)
    assert step.stopped is True
    assert step.width == step.limit.minimum_width
    assert step.center_x != mp.mpf(request.center_x_text)
    assert step.center_y != mp.mpf(request.center_y_text)


def test_advance_flight_does_not_zoom_out_if_already_below_limit():
    request = _request(view_width_text="1e-90", viewport=Viewport(-0.75, 0.1, 1e-90))
    step = advance_flight(
        request,
        mp.mpf("-0.743643887037151"),
        mp.mpf("0.13182590420533"),
        1.035,
    )
    assert step.stopped is True
    assert step.width == mp.mpf("1e-90")
    assert step.center_x == mp.mpf(request.center_x_text)
    assert step.center_y == mp.mpf(request.center_y_text)


def test_advance_flight_continues_above_limit():
    request = _request(view_width_text="1e-20", viewport=Viewport(-0.75, 0.1, 1e-20))
    step = advance_flight(request, mp.mpf("-0.74"), mp.mpf("0.13"), 2.0)
    assert step.stopped is False
    assert step.width == mp.mpf("5e-21")
