from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

import mpmath as mp

from .flight_path import CameraPath
from .models import FractalKind
from .palettes import palette_names


def _finite_decimal(text: str, label: str, *, digits: int = 80) -> mp.mpf:
    if not isinstance(text, str):
        raise ValueError(f"{label} must be a decimal string")
    try:
        with mp.workdps(digits):
            value = mp.mpf(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a decimal number") from exc
    if not mp.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


def _validated_name(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("flight-plan name must be a string")
    name = value.strip()
    if not name:
        raise ValueError("flight-plan name must not be empty")
    if len(name) > 200:
        raise ValueError("flight-plan name must not exceed 200 characters")
    if any(ord(character) < 32 for character in name):
        raise ValueError("flight-plan name must not contain control characters")
    return name


class PaletteTransition(str, Enum):
    """How a render cue changes from the previous palette."""

    HOLD = "hold"
    BLEND = "blend"
    CUT = "cut"


@dataclass(frozen=True, slots=True)
class FlightScene:
    """Portable fractal-space parameters shared by the complete flight."""

    fractal: FractalKind | str = FractalKind.MANDELBROT
    exponent: int = 3
    julia_c_real_text: str = "-0.8"
    julia_c_imag_text: str = "0.156"

    def __post_init__(self) -> None:
        object.__setattr__(self, "fractal", FractalKind(self.fractal))
        if isinstance(self.exponent, bool) or not isinstance(self.exponent, int):
            raise ValueError("scene exponent must be an integer")
        if not 2 <= self.exponent <= 8:
            raise ValueError("scene exponent must be between 2 and 8")
        self.julia_values()

    def julia_values(self) -> tuple[mp.mpf, mp.mpf]:
        real = _finite_decimal(self.julia_c_real_text, "Julia real component")
        imag = _finite_decimal(self.julia_c_imag_text, "Julia imaginary component")
        return real, imag


@dataclass(frozen=True, slots=True)
class RenderProfile:
    """Portable quality and coloring settings active at one timeline cue."""

    max_iterations: int = 400
    reference_bits: int = 256
    palette: str = "inferno"
    cycles_text: str = "1"

    def __post_init__(self) -> None:
        if isinstance(self.max_iterations, bool) or not isinstance(self.max_iterations, int):
            raise ValueError("render max_iterations must be an integer")
        if not 1 <= self.max_iterations <= 100_000:
            raise ValueError("render max_iterations must be between 1 and 100000")
        if isinstance(self.reference_bits, bool) or not isinstance(self.reference_bits, int):
            raise ValueError("render reference_bits must be an integer")
        if not 64 <= self.reference_bits <= 16_384:
            raise ValueError("render reference_bits must be between 64 and 16384")
        if self.palette not in palette_names():
            raise ValueError(f"unknown render palette {self.palette!r}")
        cycles = _finite_decimal(self.cycles_text, "render cycles")
        if cycles <= 0:
            raise ValueError("render cycles must be positive")

    @property
    def cycles(self) -> float:
        return float(_finite_decimal(self.cycles_text, "render cycles"))


@dataclass(frozen=True, slots=True)
class RenderCue:
    """One exact render-profile change on the flight timeline."""

    time_seconds_text: str
    profile: RenderProfile = RenderProfile()
    palette_transition: PaletteTransition | str = PaletteTransition.HOLD

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "palette_transition",
            PaletteTransition(self.palette_transition),
        )

    def time_seconds(self, *, digits: int) -> mp.mpf:
        value = _finite_decimal(self.time_seconds_text, "render cue time", digits=digits)
        if value < 0:
            raise ValueError("render cue time must be non-negative")
        return value


@dataclass(frozen=True, slots=True)
class RenderTrack:
    """Immutable, ordered render cues for one flight plan."""

    cues: tuple[RenderCue, ...] | Iterable[RenderCue]
    digits: int = 80
    _times: tuple[mp.mpf, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not 20 <= self.digits <= 16_384:
            raise ValueError("render-track precision must be between 20 and 16384 digits")
        cues = tuple(self.cues)
        if not cues:
            raise ValueError("a render track requires at least one cue")
        times = tuple(cue.time_seconds(digits=self.digits) for cue in cues)
        if times[0] != 0:
            raise ValueError("the first render cue must start at zero seconds")
        if any(right <= left for left, right in zip(times, times[1:])):
            raise ValueError("render cue times must be strictly increasing")
        object.__setattr__(self, "cues", cues)
        object.__setattr__(self, "_times", times)

    @classmethod
    def default(
        cls,
        profile: RenderProfile = RenderProfile(),
        *,
        digits: int = 80,
    ) -> "RenderTrack":
        return cls((RenderCue("0", profile, PaletteTransition.HOLD),), digits=digits)

    @property
    def first_profile(self) -> RenderProfile:
        return self.cues[0].profile

    @property
    def duration_text(self) -> str:
        return self.cues[-1].time_seconds_text

    def replace_first_profile(self, profile: RenderProfile) -> "RenderTrack":
        first = self.cues[0]
        cues = (
            RenderCue(first.time_seconds_text, profile, first.palette_transition),
            *self.cues[1:],
        )
        return RenderTrack(cues, digits=self.digits)


@dataclass(frozen=True, slots=True)
class FlightPlanDefaults:
    """Defaults used when importing the legacy camera-only schema."""

    scene: FlightScene = FlightScene()
    render_profile: RenderProfile = RenderProfile()


@dataclass(frozen=True, slots=True)
class FlightPlanDocument:
    """Portable camera, scene and render timeline plus document metadata."""

    name: str
    path: CameraPath
    scene: FlightScene = FlightScene()
    render_track: RenderTrack | None = None
    source_schema_version: int = field(default=2, compare=False, repr=False)

    def __post_init__(self) -> None:
        name = _validated_name(self.name)
        object.__setattr__(self, "name", name)
        if isinstance(self.source_schema_version, bool) or not isinstance(
            self.source_schema_version, int
        ):
            raise ValueError("source schema version must be an integer")
        render_track = self.render_track
        if render_track is None:
            render_track = RenderTrack.default(digits=self.path.digits)
            object.__setattr__(self, "render_track", render_track)
        if render_track.digits != self.path.digits:
            raise ValueError("camera and render tracks must use the same decimal precision")
        with mp.workdps(self.path.digits):
            if render_track._times[-1] > mp.mpf(self.path.duration_text):
                raise ValueError("render cues must not extend beyond the camera path")

    @property
    def digits(self) -> int:
        return self.path.digits
