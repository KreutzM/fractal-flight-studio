from __future__ import annotations

from typing import Any

import numpy as np

from .tonemapping import ToneMapState, apply_tone_mapping

_PALETTES: dict[str, tuple[tuple[float, tuple[int, int, int]], ...]] = {
    "inferno": (
        (0.00, (0, 0, 4)),
        (0.18, (43, 11, 84)),
        (0.40, (120, 28, 109)),
        (0.62, (203, 70, 76)),
        (0.82, (248, 148, 65)),
        (1.00, (252, 255, 164)),
    ),
    "ocean": (
        (0.00, (0, 4, 20)),
        (0.22, (0, 48, 100)),
        (0.48, (0, 130, 170)),
        (0.72, (80, 220, 210)),
        (1.00, (240, 255, 220)),
    ),
    "electric": (
        (0.00, (0, 0, 0)),
        (0.16, (35, 0, 95)),
        (0.36, (0, 80, 255)),
        (0.58, (0, 255, 220)),
        (0.78, (255, 230, 0)),
        (1.00, (255, 255, 255)),
    ),
    "ember": (
        (0.00, (3, 0, 0)),
        (0.25, (70, 0, 5)),
        (0.50, (185, 30, 0)),
        (0.75, (255, 145, 0)),
        (1.00, (255, 250, 210)),
    ),
    "monochrome": (
        (0.00, (0, 0, 0)),
        (1.00, (255, 255, 255)),
    ),
}


def palette_names() -> tuple[str, ...]:
    return tuple(_PALETTES)


def palette_lut(name: str, size: int = 2048) -> np.ndarray:
    if name not in _PALETTES:
        raise KeyError(f"unknown palette: {name}")
    stops = _PALETTES[name]
    positions = np.array([s[0] for s in stops], dtype=np.float32)
    colors = np.array([s[1] for s in stops], dtype=np.float32)
    x = np.linspace(0.0, 1.0, size, dtype=np.float32)
    lut = np.empty((size, 3), dtype=np.float32)
    for channel in range(3):
        lut[:, channel] = np.interp(x, positions, colors[:, channel])
    return np.clip(lut, 0, 255).astype(np.uint8)


def colorize(
    values: np.ndarray,
    inside: np.ndarray,
    palette: str = "inferno",
    cycles: float = 1.0,
    phase: float = 0.0,
) -> np.ndarray:
    """Map normalized values to RGB using a fixed palette.

    This is the low-level linear palette lookup used by the optimized CUDA frame
    path. For automatic contrast enhancement, use :func:`tone_mapped_colorize`.
    """
    if values.shape != inside.shape:
        raise ValueError("values and inside masks must have the same shape")
    if cycles <= 0:
        raise ValueError("cycles must be positive")
    lut = palette_lut(palette)
    wrapped = np.mod(values * cycles + phase, 1.0)
    indices = np.minimum((wrapped * (len(lut) - 1)).astype(np.int32), len(lut) - 1)
    rgb = lut[indices]
    rgb = rgb.copy()
    rgb[inside] = 0
    return rgb


def tone_mapped_colorize(
    values: np.ndarray,
    inside: np.ndarray,
    palette: str = "inferno",
    cycles: float = 1.0,
    phase: float = 0.0,
    tone_mapping: str = "auto",
    tone_state: ToneMapState | None = None,
    scene_key: tuple[Any, ...] | None = None,
    tone_smoothing: float = 0.16,
) -> tuple[np.ndarray, ToneMapState | None, dict[str, Any]]:
    mapped, next_state, details = apply_tone_mapping(
        values,
        inside,
        tone_mapping,
        tone_state,
        scene_key,
        tone_smoothing,
    )
    rgb = colorize(mapped, inside, palette, cycles, phase)
    return rgb, next_state, details
