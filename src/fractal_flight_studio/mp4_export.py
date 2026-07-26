from __future__ import annotations

from pathlib import Path

from .ffmpeg_mp4 import (
    CancellationCheck,
    Mp4ExportPlan,
    Mp4ExportProgress,
    Mp4ExportResult,
    Mp4ExportSettings,
    ProgressCallback,
    encode_mp4_frames,
)
from .flight_path import CameraPath
from .models import RenderRequest
from .offline_render import OfflineFramePlan, render_offline_frames


def build_mp4_export_plan(offline_plan: OfflineFramePlan) -> Mp4ExportPlan:
    """Convert an inclusive offline sampling plan to constant-rate video frames."""

    if offline_plan.endpoint_appended:
        raise ValueError(
            "MP4 export requires a cadence-only offline plan; rebuild it with "
            "append_endpoint=False"
        )
    frame_count = offline_plan.frame_count - int(offline_plan.endpoint_included)
    if frame_count < 1:
        raise ValueError("MP4 export requires at least one cadence frame")
    return Mp4ExportPlan(
        width=offline_plan.width,
        height=offline_plan.height,
        fps_numerator=offline_plan.fps_numerator,
        fps_denominator=offline_plan.fps_denominator,
        duration_text=offline_plan.duration_text,
        digits=offline_plan.digits,
        frame_count=frame_count,
        source_frame_count=offline_plan.frame_count,
    )


def export_path_to_mp4(
    path: CameraPath,
    request_template: RenderRequest,
    renderer,
    offline_plan: OfflineFramePlan,
    output_path: str | Path,
    settings: Mp4ExportSettings = Mp4ExportSettings(),
    *,
    palette: str = "inferno",
    cycles: float = 1.0,
    phase: float = 0.0,
    tone_mapping: str = "auto",
    progress: ProgressCallback | None = None,
    cancellation_requested: CancellationCheck | None = None,
) -> Mp4ExportResult:
    """Render a complete cadence-only path and stream it directly into FFmpeg."""

    mp4_plan = build_mp4_export_plan(offline_plan)
    frames = render_offline_frames(
        path,
        request_template,
        renderer,
        offline_plan,
        stop_index=mp4_plan.frame_count,
        palette=palette,
        cycles=cycles,
        phase=phase,
        tone_mapping=tone_mapping,
    )
    return encode_mp4_frames(
        frames,
        mp4_plan,
        output_path,
        settings,
        progress=progress,
        cancellation_requested=cancellation_requested,
    )
