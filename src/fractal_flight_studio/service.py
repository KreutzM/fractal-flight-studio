from __future__ import annotations

from pathlib import Path

from PIL import Image

from .models import RenderRequest
from .renderers import select_renderer


def render_rgb(
    request: RenderRequest,
    backend: str = "auto",
    palette: str = "inferno",
    cycles: float = 1.0,
    phase: float = 0.0,
):
    renderer = select_renderer(backend)
    result = renderer.render_frame(request, palette, cycles, phase)
    return result.rgb, result


def save_png(
    request: RenderRequest,
    output: str | Path,
    backend: str = "auto",
    palette: str = "inferno",
    cycles: float = 1.0,
    phase: float = 0.0,
):
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rgb, result = render_rgb(request, backend, palette, cycles, phase)
    Image.fromarray(rgb, mode="RGB").save(output_path)
    return result
