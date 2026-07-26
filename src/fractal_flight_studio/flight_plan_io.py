from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

from .camera import CameraState
from .flight_path import (
    CameraPath,
    CenterInterpolation,
    Easing,
    FlightKeyframe,
)

FLIGHT_PLAN_FORMAT = "fractal-flight-studio.camera-path"
FLIGHT_PLAN_SCHEMA_VERSION = 1
FLIGHT_PLAN_EXTENSION = ".fractal-flight.json"
MAX_FLIGHT_PLAN_BYTES = 10 * 1024 * 1024
MAX_FLIGHT_PLAN_KEYFRAMES = 100_000
_MAX_DIGITS = 16_384


class FlightPlanError(ValueError):
    """Base class for invalid or unsupported flight-plan documents."""


class FlightPlanFormatError(FlightPlanError):
    """Raised when a flight-plan document violates its JSON schema."""


@dataclass(frozen=True, slots=True)
class FlightPlanDocument:
    """Portable camera path plus user-facing document metadata."""

    name: str
    path: CameraPath

    def __post_init__(self) -> None:
        normalized = _validated_name(self.name)
        object.__setattr__(self, "name", normalized)
        _validated_digits(self.path.digits)
        if len(self.path.keyframes) > MAX_FLIGHT_PLAN_KEYFRAMES:
            raise FlightPlanFormatError(
                f"flight plan exceeds {MAX_FLIGHT_PLAN_KEYFRAMES} keyframes"
            )


def flight_plan_to_dict(document: FlightPlanDocument) -> dict[str, Any]:
    """Convert a document to the versioned, lossless JSON representation."""

    return {
        "format": FLIGHT_PLAN_FORMAT,
        "schema_version": FLIGHT_PLAN_SCHEMA_VERSION,
        "name": document.name,
        "digits": document.path.digits,
        "keyframes": [
            {
                "time_seconds": frame.time_seconds_text,
                "center_x": frame.camera.center_x_text,
                "center_y": frame.camera.center_y_text,
                "view_width": frame.camera.view_width_text,
                "easing": frame.easing.value,
                "center_interpolation": frame.center_interpolation.value,
            }
            for frame in document.path.keyframes
        ],
    }


def serialize_flight_plan(document: FlightPlanDocument) -> str:
    """Return deterministic UTF-8 JSON text ending with one newline."""

    return json.dumps(
        flight_plan_to_dict(document),
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    ) + "\n"


def deserialize_flight_plan(
    text: str,
    *,
    source: str = "<memory>",
) -> FlightPlanDocument:
    """Parse and strictly validate one versioned flight-plan document."""

    if not isinstance(text, str):
        raise TypeError("flight-plan JSON input must be text")
    if len(text.encode("utf-8")) > MAX_FLIGHT_PLAN_BYTES:
        raise FlightPlanFormatError(
            f"{source}: flight-plan document exceeds {MAX_FLIGHT_PLAN_BYTES} bytes"
        )
    try:
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except FlightPlanFormatError as exc:
        raise FlightPlanFormatError(f"{source}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise FlightPlanFormatError(
            f"{source}: invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc

    root = _require_object(value, source)
    version = root.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise FlightPlanFormatError(f"{source}: schema_version must be an integer")
    if version != FLIGHT_PLAN_SCHEMA_VERSION:
        raise FlightPlanFormatError(
            f"{source}: unsupported schema_version {version}; "
            f"supported version is {FLIGHT_PLAN_SCHEMA_VERSION}"
        )
    return _deserialize_v1(root, source=source)


def load_flight_plan(path: str | os.PathLike[str]) -> FlightPlanDocument:
    """Load a UTF-8 flight-plan file with a bounded input size."""

    source_path = Path(path)
    with source_path.open("rb") as handle:
        payload = handle.read(MAX_FLIGHT_PLAN_BYTES + 1)
    if len(payload) > MAX_FLIGHT_PLAN_BYTES:
        raise FlightPlanFormatError(
            f"{source_path}: flight-plan document exceeds {MAX_FLIGHT_PLAN_BYTES} bytes"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FlightPlanFormatError(f"{source_path}: document is not valid UTF-8") from exc
    return deserialize_flight_plan(text, source=str(source_path))


def save_flight_plan(
    path: str | os.PathLike[str],
    document: FlightPlanDocument,
) -> Path:
    """Atomically replace a flight-plan file using a sibling temporary file."""

    target = Path(path)
    parent = target.parent
    if not parent.exists():
        raise FileNotFoundError(f"flight-plan directory does not exist: {parent}")
    if not parent.is_dir():
        raise NotADirectoryError(f"flight-plan parent is not a directory: {parent}")

    payload = serialize_flight_plan(document)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, target)
    except BaseException:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return target


def suggested_flight_plan_name(path: str | os.PathLike[str]) -> str:
    """Derive a readable document name from a selected file path."""

    filename = Path(path).name
    lower = filename.casefold()
    if lower.endswith(FLIGHT_PLAN_EXTENSION):
        filename = filename[: -len(FLIGHT_PLAN_EXTENSION)]
    elif lower.endswith(".json"):
        filename = filename[:-5]
    return filename.strip() or "Flugplan"


def _deserialize_v1(
    root: Mapping[str, Any],
    *,
    source: str,
) -> FlightPlanDocument:
    _require_exact_keys(
        root,
        {"format", "schema_version", "name", "digits", "keyframes"},
        source,
    )
    if root["format"] != FLIGHT_PLAN_FORMAT:
        raise FlightPlanFormatError(
            f"{source}: format must be {FLIGHT_PLAN_FORMAT!r}"
        )
    name = _require_string(root["name"], f"{source}: name")
    digits = _validated_digits(root["digits"], source=source)

    keyframe_values = root["keyframes"]
    if not isinstance(keyframe_values, list):
        raise FlightPlanFormatError(f"{source}: keyframes must be an array")
    if len(keyframe_values) < 2:
        raise FlightPlanFormatError(f"{source}: at least two keyframes are required")
    if len(keyframe_values) > MAX_FLIGHT_PLAN_KEYFRAMES:
        raise FlightPlanFormatError(
            f"{source}: keyframes exceeds {MAX_FLIGHT_PLAN_KEYFRAMES} entries"
        )

    frames: list[FlightKeyframe] = []
    expected = {
        "time_seconds",
        "center_x",
        "center_y",
        "view_width",
        "easing",
        "center_interpolation",
    }
    for index, item in enumerate(keyframe_values):
        label = f"{source}: keyframes[{index}]"
        frame_value = _require_object(item, label)
        _require_exact_keys(frame_value, expected, label)
        try:
            frame = FlightKeyframe(
                _require_string(frame_value["time_seconds"], f"{label}.time_seconds"),
                CameraState(
                    _require_string(frame_value["center_x"], f"{label}.center_x"),
                    _require_string(frame_value["center_y"], f"{label}.center_y"),
                    _require_string(frame_value["view_width"], f"{label}.view_width"),
                ),
                Easing(_require_string(frame_value["easing"], f"{label}.easing")),
                CenterInterpolation(
                    _require_string(
                        frame_value["center_interpolation"],
                        f"{label}.center_interpolation",
                    )
                ),
            )
        except ValueError as exc:
            raise FlightPlanFormatError(f"{label}: {exc}") from exc
        frames.append(frame)

    try:
        path = CameraPath(tuple(frames), digits=digits)
    except ValueError as exc:
        raise FlightPlanFormatError(f"{source}: invalid camera path: {exc}") from exc
    return FlightPlanDocument(name=name, path=path)


def _validated_name(value: Any) -> str:
    name = _require_string(value, "flight-plan name").strip()
    if not name:
        raise FlightPlanFormatError("flight-plan name must not be empty")
    if len(name) > 200:
        raise FlightPlanFormatError("flight-plan name must not exceed 200 characters")
    if any(ord(character) < 32 for character in name):
        raise FlightPlanFormatError("flight-plan name must not contain control characters")
    return name


def _validated_digits(value: Any, *, source: str | None = None) -> int:
    label = "digits" if source is None else f"{source}: digits"
    if isinstance(value, bool) or not isinstance(value, int):
        raise FlightPlanFormatError(f"{label} must be an integer")
    if not 20 <= value <= _MAX_DIGITS:
        raise FlightPlanFormatError(f"{label} must be between 20 and {_MAX_DIGITS}")
    return value


def _unique_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise FlightPlanFormatError(f"duplicate JSON member {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise FlightPlanFormatError(f"invalid JSON constant {value!r}")


def _require_object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise FlightPlanFormatError(f"{label}: expected a JSON object")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise FlightPlanFormatError(f"{label} must be a string")
    return value


def _require_exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    label: str,
) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    details: list[str] = []
    if missing:
        details.append("missing " + ", ".join(repr(item) for item in missing))
    if extra:
        details.append("unexpected " + ", ".join(repr(item) for item in extra))
    if details:
        raise FlightPlanFormatError(f"{label}: " + "; ".join(details))
