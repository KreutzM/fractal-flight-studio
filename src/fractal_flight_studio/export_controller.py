from __future__ import annotations

from concurrent.futures import Executor, Future, ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from fractions import Fraction
from pathlib import Path
from threading import Event, Lock
from typing import Any

from .ffmpeg_mp4 import (
    FFmpegInfo,
    Mp4ExportResult,
    Mp4ExportSettings,
    probe_ffmpeg,
)
from .flight_path import CameraPath
from .models import RenderRequest
from .mp4_export import build_mp4_export_plan, export_path_to_mp4
from .offline_render import (
    OfflineFramePlan,
    OfflineRenderSettings,
    build_offline_frame_plan,
)
from .preflight import (
    PreflightReport,
    PreflightSettings,
    build_preflight_plan,
    run_path_preflight,
)


class FlightExportJobKind(str, Enum):
    PROBE = "probe"
    PREFLIGHT = "preflight"
    MP4 = "mp4"


@dataclass(frozen=True, slots=True)
class FlightExportProgress:
    kind: FlightExportJobKind
    completed: int
    total: int
    message: str

    @property
    def fraction(self) -> float:
        if self.total <= 0:
            return 0.0
        return min(1.0, max(0.0, self.completed / self.total))


@dataclass(frozen=True, slots=True)
class FlightExportConfiguration:
    width: int = 1920
    height: int = 1080
    frame_rate_text: str = "30"
    preflight_width: int = 320
    preflight_height: int = 180
    preflight_interval_text: str = "0.5"
    preflight_max_samples: int = 240
    ffmpeg_executable: str = "ffmpeg"
    video_codec: str = "libx264"
    preset: str = "medium"
    crf: int = 18
    output_pixel_format: str = "yuv420p"
    overwrite: bool = False
    max_frames: int = 1_000_000

    def __post_init__(self) -> None:
        numerator, denominator = parse_frame_rate(self.frame_rate_text)
        OfflineRenderSettings(
            width=self.width,
            height=self.height,
            fps_numerator=numerator,
            fps_denominator=denominator,
            append_endpoint=False,
            max_frames=self.max_frames,
        )
        PreflightSettings(
            width=self.preflight_width,
            height=self.preflight_height,
            sample_interval_seconds_text=self.preflight_interval_text,
            max_samples=self.preflight_max_samples,
        )
        Mp4ExportSettings(
            ffmpeg_executable=self.ffmpeg_executable,
            video_codec=self.video_codec,
            preset=self.preset,
            crf=self.crf,
            output_pixel_format=self.output_pixel_format,
            overwrite=self.overwrite,
        )
        if self.output_pixel_format in {"yuv420p", "yuv420p10le"} and (
            self.width % 2 or self.height % 2
        ):
            raise ValueError(
                f"{self.output_pixel_format} requires even video dimensions, got "
                f"{self.width}x{self.height}"
            )

    @property
    def frame_rate(self) -> tuple[int, int]:
        return parse_frame_rate(self.frame_rate_text)

    def offline_settings(self) -> OfflineRenderSettings:
        numerator, denominator = self.frame_rate
        return OfflineRenderSettings(
            width=self.width,
            height=self.height,
            fps_numerator=numerator,
            fps_denominator=denominator,
            append_endpoint=False,
            max_frames=self.max_frames,
        )

    def preflight_settings(self) -> PreflightSettings:
        return PreflightSettings(
            width=self.preflight_width,
            height=self.preflight_height,
            sample_interval_seconds_text=self.preflight_interval_text,
            max_samples=self.preflight_max_samples,
        )

    def mp4_settings(self) -> Mp4ExportSettings:
        return Mp4ExportSettings(
            ffmpeg_executable=self.ffmpeg_executable,
            video_codec=self.video_codec,
            preset=self.preset,
            crf=self.crf,
            output_pixel_format=self.output_pixel_format,
            overwrite=self.overwrite,
        )

    def build_offline_plan(self, path: CameraPath) -> OfflineFramePlan:
        return build_offline_frame_plan(path, self.offline_settings())

    def export_frame_count(self, path: CameraPath) -> int:
        return build_mp4_export_plan(self.build_offline_plan(path)).frame_count

    def preflight_fingerprint(self) -> tuple[object, ...]:
        numerator, denominator = self.frame_rate
        return (
            self.width,
            self.height,
            numerator,
            denominator,
            self.preflight_width,
            self.preflight_height,
            self.preflight_interval_text,
            self.preflight_max_samples,
        )


def parse_frame_rate(text: str) -> tuple[int, int]:
    value = text.strip()
    if not value:
        raise ValueError("frame rate must not be empty")
    try:
        if "/" in value:
            numerator_text, denominator_text = value.split("/", 1)
            rate = Fraction(int(numerator_text.strip()), int(denominator_text.strip()))
        else:
            decimal = Decimal(value)
            if not decimal.is_finite():
                raise ValueError
            rate = Fraction(decimal)
    except (InvalidOperation, ValueError, ZeroDivisionError) as exc:
        raise ValueError(
            "frame rate must be a positive decimal or fraction such as 30 or 30000/1001"
        ) from exc
    if rate <= 0:
        raise ValueError("frame rate must be positive")
    return rate.numerator, rate.denominator


def flight_export_fingerprint(
    path: CameraPath,
    request: RenderRequest,
    renderer_name: str,
    palette: str,
    cycles: float,
    configuration: FlightExportConfiguration,
) -> tuple[object, ...]:
    keyframes = tuple(
        (
            frame.time_seconds_text,
            frame.camera.center_x_text,
            frame.camera.center_y_text,
            frame.camera.view_width_text,
            frame.easing.value,
        )
        for frame in path.keyframes
    )
    return (
        path.digits,
        keyframes,
        request.fractal.value,
        request.max_iterations,
        request.escape_radius,
        request.julia_c_real,
        request.julia_c_imag,
        request.exponent,
        request.precision.value,
        request.render_mode.value,
        request.reference_bits,
        renderer_name,
        palette,
        cycles,
        configuration.preflight_fingerprint(),
    )


class FlightExportController:
    """Single-worker, Tk-independent lifecycle for preflight and MP4 export."""

    def __init__(self, executor: Executor | None = None) -> None:
        self._executor = executor or ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="fractal-export",
        )
        self._owns_executor = executor is None
        self._cancel = Event()
        self._lock = Lock()
        self._future: Future[Any] | None = None
        self._progress: FlightExportProgress | None = None

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._future is not None

    @property
    def progress(self) -> FlightExportProgress | None:
        with self._lock:
            return self._progress

    def start_probe(self, executable: str) -> Future[FFmpegInfo]:
        def job() -> FFmpegInfo:
            info = probe_ffmpeg(executable)
            self._set_progress(FlightExportJobKind.PROBE, 1, 1, info.version_line)
            return info

        return self._submit(
            FlightExportJobKind.PROBE,
            total=1,
            message="Prüfe FFmpeg …",
            job=job,
        )

    def start_preflight(
        self,
        path: CameraPath,
        request_template: RenderRequest,
        renderer,
        settings: PreflightSettings,
        *,
        palette: str,
        cycles: float,
        tone_mapping: str = "auto",
    ) -> Future[PreflightReport]:
        total = len(build_preflight_plan(path, settings).sample_times_text)

        def update(sample, sample_total: int) -> None:
            self._set_progress(
                FlightExportJobKind.PREFLIGHT,
                sample.index + 1,
                sample_total,
                f"Preflight {sample.index + 1}/{sample_total} bei {sample.time_seconds_text} s",
            )

        def job() -> PreflightReport:
            return run_path_preflight(
                path,
                request_template,
                renderer,
                settings,
                palette=palette,
                cycles=cycles,
                tone_mapping=tone_mapping,
                progress=update,
                cancellation_requested=self._cancel.is_set,
            )

        return self._submit(
            FlightExportJobKind.PREFLIGHT,
            total=total,
            message=f"Preflight mit {total} Stichproben …",
            job=job,
        )

    def start_mp4(
        self,
        path: CameraPath,
        request_template: RenderRequest,
        renderer,
        offline_plan: OfflineFramePlan,
        output_path: str | Path,
        settings: Mp4ExportSettings,
        *,
        palette: str,
        cycles: float,
        tone_mapping: str = "auto",
    ) -> Future[Mp4ExportResult]:
        total = build_mp4_export_plan(offline_plan).frame_count

        def update(progress) -> None:
            self._set_progress(
                FlightExportJobKind.MP4,
                progress.frames_written,
                progress.total_frames,
                f"Kodiere Frame {progress.frames_written}/{progress.total_frames}",
            )

        def job() -> Mp4ExportResult:
            return export_path_to_mp4(
                path,
                request_template,
                renderer,
                offline_plan,
                output_path,
                settings,
                palette=palette,
                cycles=cycles,
                tone_mapping=tone_mapping,
                progress=update,
                cancellation_requested=self._cancel.is_set,
            )

        return self._submit(
            FlightExportJobKind.MP4,
            total=total,
            message=f"Rendere und kodiere {total} Frames …",
            job=job,
        )

    def cancel(self) -> None:
        self._cancel.set()
        with self._lock:
            current = self._progress
            if current is not None:
                self._progress = FlightExportProgress(
                    current.kind,
                    current.completed,
                    current.total,
                    "Abbruch angefordert …",
                )

    def complete(self, future: Future[Any]) -> None:
        with self._lock:
            if self._future is not future:
                raise ValueError("future does not belong to the active export job")
            self._future = None

    def shutdown(self) -> None:
        self.cancel()
        if self._owns_executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

    def _submit(
        self,
        kind: FlightExportJobKind,
        *,
        total: int,
        message: str,
        job,
    ):
        with self._lock:
            if self._future is not None:
                raise RuntimeError("another flight export job is already running")
            self._cancel.clear()
            self._progress = FlightExportProgress(kind, 0, total, message)
            future = self._executor.submit(job)
            self._future = future
            return future

    def _set_progress(
        self,
        kind: FlightExportJobKind,
        completed: int,
        total: int,
        message: str,
    ) -> None:
        with self._lock:
            if self._cancel.is_set():
                message = "Abbruch angefordert …"
            self._progress = FlightExportProgress(kind, completed, total, message)
