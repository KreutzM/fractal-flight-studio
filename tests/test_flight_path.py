from __future__ import annotations

import mpmath as mp
import pytest

from fractal_flight_studio.camera import CameraState
from fractal_flight_studio.flight_path import CameraPath, Easing, FlightKeyframe


def _path(*, easing: Easing = Easing.LINEAR) -> CameraPath:
    return CameraPath(
        (
            FlightKeyframe("0", CameraState("-0.5", "0", "4"), easing),
            FlightKeyframe("10", CameraState("-0.75", "0.125", "4e-40")),
        ),
        digits=100,
    )


def test_path_clamps_to_exact_endpoint_cameras():
    path = _path()
    assert path.evaluate("-3") is path.keyframes[0].camera
    assert path.evaluate("20") is path.keyframes[-1].camera


def test_linear_path_interpolates_xy_and_width_logarithmically():
    camera = _path().evaluate("5")
    x, y, width = camera.values(digits=100)
    assert abs(x - mp.mpf("-0.625")) < mp.mpf("1e-95")
    assert abs(y - mp.mpf("0.0625")) < mp.mpf("1e-95")
    with mp.workdps(100):
        assert abs(width / mp.mpf("4e-20") - 1) < mp.mpf("1e-95")


def test_smoothstep_is_applied_to_outgoing_segment():
    path = CameraPath(
        (
            FlightKeyframe("0", CameraState("0", "0", "1"), Easing.SMOOTHSTEP),
            FlightKeyframe("4", CameraState("1", "2", "1e-8"), Easing.LINEAR),
            FlightKeyframe("8", CameraState("3", "6", "1e-16")),
        ),
        digits=80,
    )
    first = path.evaluate("1")
    second = path.evaluate("5")
    assert mp.almosteq(mp.mpf(first.center_x_text), mp.mpf("0.15625"))
    assert mp.almosteq(mp.mpf(second.center_x_text), mp.mpf("1.5"))


def test_deep_zoom_path_is_deterministic_and_preserves_sub_float64_motion():
    path = CameraPath(
        (
            FlightKeyframe(
                "0",
                CameraState(
                    "-0.743643887037158704752191506114774",
                    "0.131825904205311970493132056385139",
                    "1e-300",
                ),
                Easing.SMOOTHERSTEP,
            ),
            FlightKeyframe(
                "1",
                CameraState(
                    "-0.743643887037158704752191506114775",
                    "0.131825904205311970493132056385140",
                    "1e-500",
                ),
            ),
        ),
        digits=180,
    )
    first = path.evaluate("0.375")
    second = path.evaluate(mp.mpf("0.375"))
    assert first == second
    assert first.center_x_text not in {
        path.keyframes[0].camera.center_x_text,
        path.keyframes[1].camera.center_x_text,
    }
    assert mp.mpf("1e-500") < mp.mpf(first.view_width_text) < mp.mpf("1e-300")


@pytest.mark.parametrize(
    "frames, message",
    [
        ((FlightKeyframe("0", CameraState()),), "at least two"),
        (
            (
                FlightKeyframe("0", CameraState()),
                FlightKeyframe("0", CameraState("0", "0", "1")),
            ),
            "strictly increasing",
        ),
        (
            (
                FlightKeyframe("1", CameraState()),
                FlightKeyframe("1", CameraState("0", "0", "1")),
            ),
            "start at zero",
        ),
    ],
)
def test_path_rejects_invalid_keyframe_sequences(frames, message):
    with pytest.raises(ValueError, match=message):
        CameraPath(frames)


def test_path_rejects_invalid_time_and_width():
    with pytest.raises(ValueError, match="finite and non-negative"):
        CameraPath(
            (FlightKeyframe("nan", CameraState()), FlightKeyframe("1", CameraState()))
        )
    with pytest.raises(ValueError, match="camera width"):
        CameraPath(
            (
                FlightKeyframe("0", CameraState("0", "0", "0")),
                FlightKeyframe("1", CameraState()),
            )
        )
    with pytest.raises(ValueError, match="evaluation time"):
        _path().evaluate("inf")
