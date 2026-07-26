"""Fractal Flight Studio."""

from .camera import CameraState
from .flight_path import CameraPath, Easing, FlightKeyframe
from .models import FractalKind, Precision, RenderMode, RenderRequest, Viewport
from .offline_render import (
    OfflineFrame,
    OfflineFrameJob,
    OfflineFramePlan,
    OfflineFrameRenderError,
    OfflineRenderSettings,
    build_offline_frame_plan,
    iter_offline_frame_jobs,
    render_offline_frame,
    render_offline_frames,
)
from .preflight import (
    PreflightIssue,
    PreflightIssueKind,
    PreflightPlan,
    PreflightReport,
    PreflightSample,
    PreflightSettings,
    build_preflight_plan,
    run_path_preflight,
)

__all__ = [
    "CameraPath",
    "CameraState",
    "Easing",
    "FlightKeyframe",
    "FractalKind",
    "OfflineFrame",
    "OfflineFrameJob",
    "OfflineFramePlan",
    "OfflineFrameRenderError",
    "OfflineRenderSettings",
    "Precision",
    "PreflightIssue",
    "PreflightIssueKind",
    "PreflightPlan",
    "PreflightReport",
    "PreflightSample",
    "PreflightSettings",
    "RenderMode",
    "RenderRequest",
    "Viewport",
    "build_offline_frame_plan",
    "build_preflight_plan",
    "iter_offline_frame_jobs",
    "render_offline_frame",
    "render_offline_frames",
    "run_path_preflight",
]
__version__ = "0.9.0"
