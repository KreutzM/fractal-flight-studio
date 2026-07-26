from __future__ import annotations

import json
from pathlib import Path

import pytest

from fractal_flight_studio.camera import CameraState
from fractal_flight_studio.flight_path import (
    CameraPath,
    CenterInterpolation,
    Easing,
    FlightKeyframe,
)
from fractal_flight_studio.flight_plan_io import (
    FLIGHT_PLAN_EXTENSION,
    FlightPlanDocument,
    FlightPlanFormatError,
    deserialize_flight_plan,
    load_flight_plan,
    save_flight_plan,
    serialize_flight_plan,
    suggested_flight_plan_name,
)


def _document() -> FlightPlanDocument:
    return FlightPlanDocument(
        name="Seahorse Δ",
        path=CameraPath(
            (
                FlightKeyframe(
                    "0",
                    CameraState("-0.5", "0", "4"),
                    Easing.SMOOTHERSTEP,
                    CenterInterpolation.FOCUS,
                ),
                FlightKeyframe(
                    "2.5000000000000000001",
                    CameraState(
                        "-0.743643887037158704752191506114774",
                        "0.131825904205311970493132056385139",
                        "1e-420",
                    ),
                    Easing.LINEAR,
                    CenterInterpolation.LINEAR,
                ),
            ),
            digits=180,
        ),
    )


def test_round_trip_preserves_exact_text_and_segment_modes(tmp_path: Path) -> None:
    target = tmp_path / f"seahorse{FLIGHT_PLAN_EXTENSION}"

    save_flight_plan(target, _document())
    loaded = load_flight_plan(target)

    assert loaded == _document()
    assert loaded.path.keyframes[1].camera.center_x_text.endswith("4774")
    assert loaded.path.keyframes[1].camera.view_width_text == "1e-420"
    assert loaded.path.keyframes[0].center_interpolation is CenterInterpolation.FOCUS
    assert loaded.path.digits == 180


def test_serialization_is_deterministic_utf8_and_uses_string_numbers() -> None:
    first = serialize_flight_plan(_document())
    second = serialize_flight_plan(_document())
    value = json.loads(first)

    assert first == second
    assert first.endswith("\n") and not first.endswith("\n\n")
    assert "Seahorse Δ" in first
    assert value["keyframes"][1]["center_x"].endswith("4774")
    assert isinstance(value["keyframes"][1]["view_width"], str)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(schema_version=99), "unsupported schema_version"),
        (lambda value: value.update(format="other"), "format must be"),
        (lambda value: value.update(digits=True), "digits must be an integer"),
        (lambda value: value.update(extra=True), "unexpected 'extra'"),
        (lambda value: value.pop("name"), "missing 'name'"),
        (lambda value: value.update(keyframes=[]), "at least two keyframes"),
        (
            lambda value: value["keyframes"][1].update(view_width=1e-20),
            "view_width must be a string",
        ),
        (
            lambda value: value["keyframes"][0].update(easing="bounce"),
            "'bounce' is not a valid Easing",
        ),
    ],
)
def test_schema_validation_rejects_invalid_documents(mutation, message: str) -> None:
    value = json.loads(serialize_flight_plan(_document()))
    mutation(value)

    with pytest.raises(FlightPlanFormatError, match=message):
        deserialize_flight_plan(json.dumps(value))


def test_duplicate_json_members_and_nonstandard_constants_are_rejected() -> None:
    with pytest.raises(FlightPlanFormatError, match="duplicate JSON member 'name'"):
        deserialize_flight_plan(
            '{"schema_version":1,"format":"x","name":"x","name":"y",'
            '"digits":80,"keyframes":[]}'
        )

    with pytest.raises(FlightPlanFormatError, match="invalid JSON constant"):
        deserialize_flight_plan(
            '{"schema_version":NaN,"format":"x","name":"x",'
            '"digits":80,"keyframes":[]}'
        )


def test_invalid_camera_path_is_reported_with_source_context() -> None:
    value = json.loads(serialize_flight_plan(_document()))
    value["keyframes"][0]["time_seconds"] = "1"

    with pytest.raises(FlightPlanFormatError, match="plan.json: invalid camera path"):
        deserialize_flight_plan(json.dumps(value), source="plan.json")


def test_load_rejects_invalid_utf8(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_bytes(b"\xff\xfe")

    with pytest.raises(FlightPlanFormatError, match="not valid UTF-8"):
        load_flight_plan(path)


def test_atomic_save_keeps_existing_file_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fractal_flight_studio.flight_plan_io as module

    target = tmp_path / "plan.json"
    target.write_text("old content", encoding="utf-8")

    def fail_replace(_source, _target) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated"):
        save_flight_plan(target, _document())

    assert target.read_text(encoding="utf-8") == "old content"
    assert list(tmp_path.glob(".plan.json.*.tmp")) == []


def test_suggested_name_strips_known_extensions() -> None:
    assert suggested_flight_plan_name("My Zoom.fractal-flight.json") == "My Zoom"
    assert suggested_flight_plan_name("plain.json") == "plain"
    assert suggested_flight_plan_name(".json") == "Flugplan"
