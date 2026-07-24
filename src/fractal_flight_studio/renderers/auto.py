from __future__ import annotations

from .base import Renderer
from .cpu import CpuRenderer
from .cuda_tonemap import CudaRenderer

# Reuse backend instances. In particular, this keeps CUDA contexts, streams and
# device buffers alive across animation frames instead of reallocating them for
# every render request. It also preserves temporally smoothed automatic tone
# parameters across related GUI frames.
_CPU_RENDERER = CpuRenderer()
_CUDA_RENDERER = CudaRenderer()


def available_renderers() -> dict[str, Renderer]:
    candidates: tuple[Renderer, ...] = (_CUDA_RENDERER, _CPU_RENDERER)
    return {renderer.name: renderer for renderer in candidates if renderer.is_available()}


def select_renderer(preference: str = "auto") -> Renderer:
    renderers = available_renderers()
    if preference == "auto":
        return renderers.get("cuda-numba", renderers["cpu-numba"])
    if preference in ("cpu", "cpu-numba"):
        return _CPU_RENDERER
    if preference in ("cuda", "cuda-numba"):
        if not _CUDA_RENDERER.is_available():
            from ..gpu_info import inspect_cuda

            raise RuntimeError(inspect_cuda().summary)
        return _CUDA_RENDERER
    raise ValueError(f"unknown backend preference: {preference}")
