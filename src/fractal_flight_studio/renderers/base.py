from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import time
from typing import Any

import numpy as np

from ..models import RenderRequest


@dataclass(slots=True)
class RenderResult:
    values: np.ndarray
    inside: np.ndarray
    backend: str
    elapsed_seconds: float
    details: dict[str, Any]


@dataclass(slots=True)
class FrameResult:
    rgb: np.ndarray
    backend: str
    elapsed_seconds: float
    details: dict[str, Any]


class Renderer(ABC):
    name: str

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def render(self, request: RenderRequest) -> RenderResult:
        raise NotImplementedError

    def render_frame(
        self,
        request: RenderRequest,
        palette: str = "inferno",
        cycles: float = 1.0,
        phase: float = 0.0,
    ) -> FrameResult:
        """Render a display-ready RGB frame.

        Backends may override this to keep post-processing on the accelerator and
        avoid transferring intermediate arrays to the host.
        """
        from ..palettes import colorize

        started = time.perf_counter()
        result = self.render(request)
        color_started = time.perf_counter()
        rgb = colorize(result.values, result.inside, palette, cycles, phase)
        color_seconds = time.perf_counter() - color_started
        details = dict(result.details)
        details.update(
            {
                "compute_seconds": result.elapsed_seconds,
                "color_seconds": color_seconds,
                "transfer_seconds": details.get("transfer_seconds", 0.0),
                "optimized_frame_path": False,
            }
        )
        return FrameResult(
            rgb=rgb,
            backend=result.backend,
            elapsed_seconds=time.perf_counter() - started,
            details=details,
        )
