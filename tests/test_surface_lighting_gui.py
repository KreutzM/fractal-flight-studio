from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from fractal_flight_studio.app import FractalStudioApp
from fractal_flight_studio.models import RenderRequest
from fractal_flight_studio.service import render_rgb
from fractal_flight_studio.surface_lighting import SurfaceLightingSettings


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _app_settings(**changes):
    values = {
        "surface_lighting_enabled_var": _Var(False),
        "surface_lighting_strength_var": _Var(1.5),
        "surface_lighting_azimuth_var": _Var(315.0),
        "surface_lighting_elevation_var": _Var(45.0),
    }
    for name, value in changes.items():
        values[name] = _Var(value)
    return SimpleNamespace(**values)


def test_app_surface_lighting_defaults_are_disabled() -> None:
    settings = FractalStudioApp._surface_lighting_settings(_app_settings())

    assert settings == SurfaceLightingSettings()


def test_app_surface_lighting_reads_gui_values() -> None:
    settings = FractalStudioApp._surface_lighting_settings(
        _app_settings(
            surface_lighting_enabled_var=True,
            surface_lighting_strength_var=2.25,
            surface_lighting_azimuth_var=210.0,
            surface_lighting_elevation_var=52.0,
        )
    )

    assert settings.enabled is True
    assert settings.strength == 2.25
    assert settings.azimuth_degrees == 210.0
    assert settings.elevation_degrees == 52.0
    assert settings.ambient == 0.35
    assert settings.diffuse == 0.65


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("surface_lighting_strength_var", -0.1),
        ("surface_lighting_azimuth_var", float("nan")),
        ("surface_lighting_elevation_var", 0.0),
    ],
)
def test_app_surface_lighting_rejects_invalid_gui_values(field: str, value: float) -> None:
    with pytest.raises(ValueError):
        FractalStudioApp._surface_lighting_settings(
            _app_settings(**{field: value})
        )


def test_render_rgb_forwards_surface_lighting(monkeypatch) -> None:
    captured = {}

    class _Renderer:
        def render_frame(self, request, *args, **kwargs):
            captured["request"] = request
            captured["surface_lighting"] = kwargs.get("surface_lighting")
            return SimpleNamespace(
                rgb=np.zeros((request.height, request.width, 3), dtype=np.uint8),
                backend="fake",
                details={},
            )

    monkeypatch.setattr(
        "fractal_flight_studio.service.select_renderer",
        lambda _backend: _Renderer(),
    )
    request = RenderRequest(width=12, height=8, max_iterations=20)
    settings = SurfaceLightingSettings(enabled=True, strength=2.0)

    rgb, result = render_rgb(
        request,
        backend="fake",
        surface_lighting=settings,
    )

    assert rgb.shape == (8, 12, 3)
    assert result.backend == "fake"
    assert captured["request"] is request
    assert captured["surface_lighting"] is settings
