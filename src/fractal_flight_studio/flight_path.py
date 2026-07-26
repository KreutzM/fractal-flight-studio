from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

import mpmath as mp

from .camera import CameraState


class Easing(str, Enum):
    """Interpolation curve used by a keyframe's outgoing segment."""

    LINEAR = "linear"
    SMOOTHSTEP = "smoothstep"
    SMOOTHERSTEP = "smootherstep"

    def apply(self, progress: mp.mpf) -> mp.mpf:
        if progress <= 0:
            return mp.mpf("0")
        if progress >= 1:
            return mp.mpf("1")
        if self is Easing.LINEAR:
            return progress
        if self is Easing.SMOOTHSTEP:
            return progress * progress * (3 - 2 * progress)
        return progress * progress * progress * (
            progress * (progress * 6 - 15) + 10
        )


@dataclass(frozen=True, slots=True)
class FlightKeyframe:
    """One exact camera sample on a deterministic flight timeline."""

    time_seconds_text: str
    camera: CameraState
    easing: Easing | str = Easing.SMOOTHSTEP

    def __post_init__(self) -> None:
        object.__setattr__(self, "easing", Easing(self.easing))

    def time_seconds(self, *, digits: int) -> mp.mpf:
        with mp.workdps(digits):
            value = mp.mpf(self.time_seconds_text)
        if not mp.isfinite(value) or value < 0:
            raise ValueError("keyframe time must be finite and non-negative")
        self.camera.values(digits=digits)
        return value


class CameraPath:
    """Immutable, deterministic interpolation through exact camera keyframes."""

    def __init__(self, keyframes: Iterable[FlightKeyframe], *, digits: int = 80) -> None:
        if digits < 20:
            raise ValueError("path precision must be at least 20 decimal digits")
        frames = tuple(keyframes)
        if len(frames) < 2:
            raise ValueError("a camera path requires at least two keyframes")
        times = tuple(frame.time_seconds(digits=digits) for frame in frames)
        if times[0] != 0:
            raise ValueError("the first keyframe must start at zero seconds")
        if any(right <= left for left, right in zip(times, times[1:])):
            raise ValueError("keyframe times must be strictly increasing")
        self._keyframes = frames
        self._times = times
        self._digits = digits

    @property
    def keyframes(self) -> tuple[FlightKeyframe, ...]:
        return self._keyframes

    @property
    def digits(self) -> int:
        return self._digits

    @property
    def duration_text(self) -> str:
        return self._keyframes[-1].time_seconds_text

    def evaluate(self, time_seconds: str | int | float | mp.mpf) -> CameraState:
        with mp.workdps(self._digits):
            time_value = _to_mpf(time_seconds)
            if not mp.isfinite(time_value):
                raise ValueError("evaluation time must be finite")
            if time_value <= self._times[0]:
                return self._keyframes[0].camera
            if time_value >= self._times[-1]:
                return self._keyframes[-1].camera

            segment_index = next(
                index
                for index, end_time in enumerate(self._times[1:])
                if time_value <= end_time
            )
            start = self._keyframes[segment_index]
            end = self._keyframes[segment_index + 1]
            start_time = self._times[segment_index]
            end_time = self._times[segment_index + 1]
            progress = (time_value - start_time) / (end_time - start_time)
            eased = start.easing.apply(progress)

            start_x, start_y, start_width = start.camera.values(digits=self._digits)
            end_x, end_y, end_width = end.camera.values(digits=self._digits)
            center_x = start_x + (end_x - start_x) * eased
            center_y = start_y + (end_y - start_y) * eased
            log_width = mp.log(start_width) + (mp.log(end_width) - mp.log(start_width)) * eased
            return CameraState.from_values(
                center_x,
                center_y,
                mp.exp(log_width),
                digits=self._digits,
            )


def _to_mpf(value: str | int | float | mp.mpf) -> mp.mpf:
    if isinstance(value, float):
        return mp.mpf(repr(value))
    return mp.mpf(value)
