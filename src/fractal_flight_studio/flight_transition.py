from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

import mpmath as mp

from .camera import CameraState
from .deep_zoom_targets import DeepZoomTarget
from .flight_path import CenterInterpolation, Easing, FlightKeyframe
from .flight_plan import (
    FlightScene,
    PaletteTransition,
    RenderCue,
    RenderProfile,
)


class TransitionMode(str, Enum):
    """Available camera-routing strategies for one appended target."""

    AUTO = "auto"
    DIRECT = "direct"
    BRIDGE = "bridge"
    OVERVIEW = "overview"
    CUT = "cut"


@dataclass(frozen=True, slots=True)
class TransitionTarget:
    """One exact camera and render-profile destination."""

    name: str
    camera: CameraState
    render_profile: RenderProfile
    scene: FlightScene

    @classmethod
    def from_deep_zoom_target(
        cls,
        target: DeepZoomTarget,
        *,
        scene: FlightScene,
        cycles_text: str = "1",
    ) -> TransitionTarget:
        return cls(
            target.name,
            CameraState(
                target.center_x_text,
                target.center_y_text,
                target.view_width_text,
            ),
            RenderProfile(
                target.recommended_iterations,
                target.reference_bits,
                target.palette,
                cycles_text,
            ),
            scene,
        )


@dataclass(frozen=True, slots=True)
class FreeTargetValues:
    """Portable user-editable values for one free flight target."""

    center_x_text: str
    center_y_text: str
    view_width_text: str
    max_iterations: int
    reference_bits: int
    palette: str
    cycles_text: str


@dataclass(frozen=True, slots=True)
class TransitionSettings:
    """Deterministic heuristics used to route and time one transition."""

    aspect_ratio_text: str = "1.7777777777777778"
    overview_camera: CameraState = CameraState("-0.5", "0", "3.5")
    zoom_stops_per_second_text: str = "3"
    pan_viewports_per_second_text: str = "0.8"
    hold_before_text: str = "0.75"
    hold_after_text: str = "1"
    cut_seconds_text: str = "0.033333333333333333"
    bridge_margin_text: str = "1.35"
    direct_distance_threshold_text: str = "0.85"
    overview_threshold_text: str = "0.78"
    minimum_segment_seconds_text: str = "0.35"
    maximum_segment_seconds_text: str = "12"

    def values(self, *, digits: int) -> tuple[mp.mpf, ...]:
        with mp.workdps(digits):
            aspect = _positive_decimal(self.aspect_ratio_text, "aspect ratio", digits=digits)
            zoom_speed = _positive_decimal(
                self.zoom_stops_per_second_text,
                "zoom speed",
                digits=digits,
            )
            pan_speed = _positive_decimal(
                self.pan_viewports_per_second_text,
                "pan speed",
                digits=digits,
            )
            hold_before = _non_negative_decimal(
                self.hold_before_text,
                "hold before",
                digits=digits,
            )
            hold_after = _non_negative_decimal(
                self.hold_after_text,
                "hold after",
                digits=digits,
            )
            cut_seconds = _positive_decimal(
                self.cut_seconds_text,
                "cut duration",
                digits=digits,
            )
            bridge_margin = _positive_decimal(
                self.bridge_margin_text,
                "bridge margin",
                digits=digits,
            )
            direct_threshold = _positive_decimal(
                self.direct_distance_threshold_text,
                "direct distance threshold",
                digits=digits,
            )
            overview_threshold = _positive_decimal(
                self.overview_threshold_text,
                "overview threshold",
                digits=digits,
            )
            minimum_segment = _positive_decimal(
                self.minimum_segment_seconds_text,
                "minimum segment duration",
                digits=digits,
            )
            maximum_segment = _positive_decimal(
                self.maximum_segment_seconds_text,
                "maximum segment duration",
                digits=digits,
            )
            if overview_threshold > 1:
                raise ValueError("overview threshold must not exceed one")
            if maximum_segment < minimum_segment:
                raise ValueError(
                    "maximum segment duration must be at least the minimum"
                )
            return (
                aspect,
                zoom_speed,
                pan_speed,
                hold_before,
                hold_after,
                cut_seconds,
                bridge_margin,
                direct_threshold,
                overview_threshold,
                minimum_segment,
                maximum_segment,
            )


@dataclass(frozen=True, slots=True)
class TransitionPlan:
    """Deterministic camera and render-cue additions for one destination."""

    source_camera: CameraState
    source_profile: RenderProfile
    scene: FlightScene
    mode: TransitionMode
    requested_mode: TransitionMode
    start_time_text: str
    arrival_time_text: str
    end_time_text: str
    keyframes: tuple[FlightKeyframe, ...]
    render_cues: tuple[RenderCue, ...]
    bridge_width_text: str | None
    target_name: str
    digits: int = 80

    def __post_init__(self) -> None:
        if not self.keyframes:
            raise ValueError("a transition plan requires camera keyframes")
        with mp.workdps(self.digits):
            start = mp.mpf(self.start_time_text)
            arrival = mp.mpf(self.arrival_time_text)
            end = mp.mpf(self.end_time_text)
            if arrival < start:
                raise ValueError("arrival time must not precede transition start")
            if end < arrival:
                raise ValueError("transition end must not precede arrival")
            if self.keyframes[0].time_seconds(digits=self.digits) < start:
                raise ValueError("transition keyframes must not precede start time")
            if self.keyframes[-1].time_seconds(digits=self.digits) != end:
                raise ValueError("last transition keyframe must match end time")

    @property
    def summary(self) -> str:
        route = self.mode.value
        count = len(self.keyframes)
        bridge = (
            f", Brückenbreite {self.bridge_width_text}"
            if self.bridge_width_text is not None
            else ""
        )
        return (
            f"{route}: {count} neue Keyframes, "
            f"Ankunft {self.arrival_time_text} s, Ende {self.end_time_text} s{bridge}"
        )


def plan_transition(
    source_camera: CameraState,
    source_profile: RenderProfile,
    target: TransitionTarget,
    *,
    start_time_text: str,
    requested_mode: TransitionMode | str = TransitionMode.AUTO,
    palette_transition: PaletteTransition | str = PaletteTransition.BLEND,
    settings: TransitionSettings = TransitionSettings(),
    digits: int = 80,
) -> TransitionPlan:
    """Plan one deterministic, append-only target transition."""

    requested = TransitionMode(requested_mode)
    palette_mode = PaletteTransition(palette_transition)
    if target.scene.fractal != target.scene.fractal:
        raise ValueError("target scene is invalid")

    with mp.workdps(digits):
        start_time = _non_negative_decimal(
            start_time_text,
            "transition start time",
            digits=digits,
        )
        source_x, source_y, source_width = source_camera.values(digits=digits)
        target_x, target_y, target_width = target.camera.values(digits=digits)
        (
            aspect,
            zoom_speed,
            pan_speed,
            hold_before,
            hold_after,
            cut_seconds,
            bridge_margin,
            direct_threshold,
            overview_threshold,
            minimum_segment,
            maximum_segment,
        ) = settings.values(digits=digits)
        overview_x, overview_y, overview_width = settings.overview_camera.values(
            digits=digits
        )

        dx = abs(target_x - source_x)
        dy = abs(target_y - source_y)
        screen_distance = max(dx, dy * aspect)
        reference_width = max(source_width, target_width)
        normalized_distance = screen_distance / reference_width
        required_bridge = max(
            source_width,
            target_width,
            (screen_distance + (source_width + target_width) / 2)
            * bridge_margin,
        )
        bridge_width = min(required_bridge, overview_width)

        mode = requested
        if requested is TransitionMode.AUTO:
            if normalized_distance <= direct_threshold:
                mode = TransitionMode.DIRECT
            elif required_bridge >= overview_width * overview_threshold:
                mode = TransitionMode.OVERVIEW
            else:
                mode = TransitionMode.BRIDGE

        frames: list[FlightKeyframe] = []
        current = start_time

        def add_frame(
            camera: CameraState,
            duration: mp.mpf,
            *,
            easing: Easing = Easing.SMOOTHSTEP,
            center_interpolation: CenterInterpolation = CenterInterpolation.FOCUS,
        ) -> None:
            nonlocal current
            duration = min(max(duration, minimum_segment), maximum_segment)
            current += duration
            frames.append(
                FlightKeyframe(
                    _format_decimal(current, digits=digits),
                    camera,
                    easing,
                    center_interpolation,
                )
            )

        if hold_before > 0:
            add_frame(
                source_camera,
                hold_before,
                easing=Easing.LINEAR,
                center_interpolation=CenterInterpolation.LINEAR,
            )

        bridge_text: str | None = None
        if mode is TransitionMode.CUT:
            add_frame(
                target.camera,
                cut_seconds,
                easing=Easing.STEP,
                center_interpolation=CenterInterpolation.LINEAR,
            )
        elif mode is TransitionMode.DIRECT:
            add_frame(
                target.camera,
                _direct_duration(
                    source_x,
                    source_y,
                    source_width,
                    target_x,
                    target_y,
                    target_width,
                    aspect=aspect,
                    zoom_speed=zoom_speed,
                    pan_speed=pan_speed,
                ),
                center_interpolation=CenterInterpolation.FOCUS,
            )
        elif mode is TransitionMode.BRIDGE:
            bridge_text = _format_decimal(bridge_width, digits=digits)
            source_bridge = _camera(source_x, source_y, bridge_width, digits=digits)
            target_bridge = _camera(target_x, target_y, bridge_width, digits=digits)
            add_frame(
                source_bridge,
                _zoom_duration(source_width, bridge_width, zoom_speed),
            )
            add_frame(
                target_bridge,
                _pan_duration(screen_distance, bridge_width, pan_speed),
                center_interpolation=CenterInterpolation.LINEAR,
            )
            add_frame(
                target.camera,
                _zoom_duration(bridge_width, target_width, zoom_speed),
            )
        elif mode is TransitionMode.OVERVIEW:
            bridge_text = _format_decimal(overview_width, digits=digits)
            source_overview = _camera(
                source_x, source_y, overview_width, digits=digits
            )
            target_overview = _camera(
                target_x, target_y, overview_width, digits=digits
            )
            add_frame(
                source_overview,
                _zoom_duration(source_width, overview_width, zoom_speed),
            )
            overview_distance = _screen_distance(
                source_x,
                source_y,
                overview_x,
                overview_y,
                aspect=aspect,
            )
            add_frame(
                settings.overview_camera,
                _pan_duration(overview_distance, overview_width, pan_speed),
                center_interpolation=CenterInterpolation.LINEAR,
            )
            target_overview_distance = _screen_distance(
                overview_x,
                overview_y,
                target_x,
                target_y,
                aspect=aspect,
            )
            add_frame(
                target_overview,
                _pan_duration(target_overview_distance, overview_width, pan_speed),
                center_interpolation=CenterInterpolation.LINEAR,
            )
            add_frame(
                target.camera,
                _zoom_duration(overview_width, target_width, zoom_speed),
            )
        else:  # pragma: no cover - enum completeness guard
            raise AssertionError(f"unsupported transition mode: {mode}")

        arrival = current
        if hold_after > 0:
            add_frame(
                target.camera,
                hold_after,
                easing=Easing.LINEAR,
                center_interpolation=CenterInterpolation.LINEAR,
            )
        end = current

        arrival_text = _format_decimal(arrival, digits=digits)
        end_text = _format_decimal(end, digits=digits)
        source_anchor = RenderCue(
            _format_decimal(start_time, digits=digits),
            source_profile,
            PaletteTransition.HOLD,
        )
        effective_palette_mode = (
            PaletteTransition.CUT if mode is TransitionMode.CUT else palette_mode
        )
        target_profile = target.render_profile
        if effective_palette_mode is PaletteTransition.HOLD:
            target_profile = RenderProfile(
                target_profile.max_iterations,
                target_profile.reference_bits,
                source_profile.palette,
                source_profile.cycles_text,
            )
        target_cue = RenderCue(
            arrival_text,
            target_profile,
            effective_palette_mode,
        )
        return TransitionPlan(
            source_camera=source_camera,
            source_profile=source_profile,
            scene=target.scene,
            mode=mode,
            requested_mode=requested,
            start_time_text=_format_decimal(start_time, digits=digits),
            arrival_time_text=arrival_text,
            end_time_text=end_text,
            keyframes=tuple(frames),
            render_cues=(source_anchor, target_cue),
            bridge_width_text=bridge_text,
            target_name=target.name,
            digits=digits,
        )


def suggested_target_width(
    source_camera: CameraState,
    *,
    zoom_factor_text: str = "1",
    digits: int = 80,
) -> str:
    """Return an exact free-target width without applying hidden zoom by default."""

    with mp.workdps(digits):
        _x, _y, width = source_camera.values(digits=digits)
        factor = _positive_decimal(zoom_factor_text, "zoom factor", digits=digits)
        if factor < 1:
            raise ValueError("zoom factor must be at least one")
        return _format_decimal(width / factor, digits=digits)


def merge_render_cues(
    existing: Iterable[RenderCue],
    additions: Iterable[RenderCue],
    *,
    digits: int,
) -> tuple[RenderCue, ...]:
    """Merge cues by exact time, replacing an existing anchor at the same time."""

    with mp.workdps(digits):
        by_time: dict[mp.mpf, RenderCue] = {
            cue.time_seconds(digits=digits): cue for cue in existing
        }
        for cue in additions:
            by_time[cue.time_seconds(digits=digits)] = cue
        return tuple(by_time[key] for key in sorted(by_time))


def _direct_duration(
    start_x: mp.mpf,
    start_y: mp.mpf,
    start_width: mp.mpf,
    end_x: mp.mpf,
    end_y: mp.mpf,
    end_width: mp.mpf,
    *,
    aspect: mp.mpf,
    zoom_speed: mp.mpf,
    pan_speed: mp.mpf,
) -> mp.mpf:
    zoom = _zoom_duration(start_width, end_width, zoom_speed)
    distance = _screen_distance(
        start_x,
        start_y,
        end_x,
        end_y,
        aspect=aspect,
    )
    pan = _pan_duration(distance, max(start_width, end_width), pan_speed)
    return max(zoom, pan)


def _zoom_duration(start_width: mp.mpf, end_width: mp.mpf, speed: mp.mpf) -> mp.mpf:
    ratio = max(start_width, end_width) / min(start_width, end_width)
    if ratio <= 1:
        return mp.mpf("0")
    return mp.log(ratio, 2) / speed


def _pan_duration(distance: mp.mpf, view_width: mp.mpf, speed: mp.mpf) -> mp.mpf:
    normalized = distance / view_width
    return normalized / speed


def _screen_distance(
    start_x: mp.mpf,
    start_y: mp.mpf,
    end_x: mp.mpf,
    end_y: mp.mpf,
    *,
    aspect: mp.mpf,
) -> mp.mpf:
    return max(abs(end_x - start_x), abs(end_y - start_y) * aspect)


def _camera(
    center_x: mp.mpf,
    center_y: mp.mpf,
    width: mp.mpf,
    *,
    digits: int,
) -> CameraState:
    return CameraState(
        _format_decimal(center_x, digits=digits),
        _format_decimal(center_y, digits=digits),
        _format_decimal(width, digits=digits),
    )


def _positive_decimal(value: str, name: str, *, digits: int) -> mp.mpf:
    parsed = _decimal(value, name, digits=digits)
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return parsed


def _non_negative_decimal(value: str, name: str, *, digits: int) -> mp.mpf:
    parsed = _decimal(value, name, digits=digits)
    if parsed < 0:
        raise ValueError(f"{name} must not be negative")
    return parsed


def _decimal(value: str, name: str, *, digits: int) -> mp.mpf:
    with mp.workdps(digits):
        try:
            parsed = mp.mpf(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a decimal number") from exc
        if not mp.isfinite(parsed):
            raise ValueError(f"{name} must be finite")
        return parsed


def _format_decimal(value: mp.mpf, *, digits: int) -> str:
    text = mp.nstr(value, n=digits, strip_zeros=False)
    if "e" not in text.lower() and "." in text:
        text = text.rstrip("0").rstrip(".")
    return text
