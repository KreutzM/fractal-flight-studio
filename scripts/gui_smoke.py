"""Headless-friendly GUI smoke test; use xvfb-run on Linux."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import tkinter as tk

from fractal_flight_studio.camera import CameraState
from fractal_flight_studio.flight_app import FractalStudioApp
from fractal_flight_studio.flight_path import (
    CameraPath,
    CenterInterpolation,
    FlightKeyframe,
)
from fractal_flight_studio.flight_plan import (
    FlightPlanDocument,
    PaletteTransition,
    RenderCue,
    RenderProfile,
    RenderTrack,
)
from fractal_flight_studio.flight_plan_io import FLIGHT_PLAN_SCHEMA_VERSION, load_flight_plan
from fractal_flight_studio.palettes import PaletteBlend


def main() -> int:
    root = tk.Tk()
    app = FractalStudioApp(root)
    assert app.flight_plan_session.render_track.first_profile.palette == "inferno"
    assert app.flight_plan_session.scene.fractal.value == "mandelbrot"
    assert len(app.deep_zoom_targets) == 10
    assert app.deep_zoom_target_var.get() == app.deep_zoom_targets[0].name
    app.set_catalog_flight_target()
    assert app.flight_controller.target_text == (
        app.deep_zoom_targets[0].center_x_text,
        app.deep_zoom_targets[0].center_y_text,
    )
    app.open_target_browser()
    browser = app.target_browser
    assert browser is not None
    root.update_idletasks()
    assert len(browser._visible_targets) == 10
    browser.search_var.set("spiral")
    root.update_idletasks()
    assert browser._visible_targets
    assert all(
        "spiral" in " ".join((target.name, target.description, *target.tags)).casefold()
        for target in browser._visible_targets
    )
    selected = browser.selected_target
    assert selected is not None
    browser._set_selected_target()
    assert app.flight_controller.target_text == (selected.center_x_text, selected.center_y_text)
    assert app.deep_zoom_target_var.get() == selected.name
    browser.destroy()
    root.update_idletasks()

    app.open_timeline_editor()
    timeline = app.timeline_editor
    assert timeline is not None
    assert (
        timeline.draft.keyframes[0].center_interpolation
        is CenterInterpolation.FOCUS
    )
    timeline._draft = timeline.draft.add_keyframe(
        "2",
        CameraState("-0.75", "0.1", "0.01"),
        center_interpolation=CenterInterpolation.FOCUS,
    )
    timeline._refresh_tree(select_time="2")
    timeline._publish_path_state()
    assert app.camera_path_dirty
    with TemporaryDirectory() as directory:
        plan_path = Path(directory) / "smoke.fractal-flight.json"
        app.camera_path_name = "GUI smoke"
        assert app._save_flight_plan_path(plan_path)
        assert plan_path.exists()
        saved = load_flight_plan(plan_path)
        assert saved.source_schema_version == FLIGHT_PLAN_SCHEMA_VERSION
        assert saved.render_track.first_profile.palette == app.palette_var.get()
        assert not app.camera_path_dirty
        timeline._draft = timeline.draft.remove_keyframe(1)
        timeline._refresh_tree()
        timeline._publish_path_state()
        assert app.camera_path_dirty
        assert app._load_flight_plan_path(plan_path)
        timeline = app.timeline_editor
        assert timeline is not None
        assert len(timeline.draft.keyframes) == 2
        assert app.camera_path_file == plan_path
        assert app.camera_path_name == "GUI smoke"
        assert not app.camera_path_dirty
    timeline.destroy()
    root.update_idletasks()

    app.flight_plan_session.set_camera_path(
        CameraPath(
            (
                FlightKeyframe("0", CameraState("-0.5", "0", "3.5")),
                FlightKeyframe("2", CameraState("-0.75", "0.1", "0.1")),
            )
        ),
        mark_dirty=False,
    )
    app.flight_plan_session.set_render_track(
        RenderTrack(
            (
                RenderCue(
                    "0",
                    RenderProfile(400, 256, "inferno", "1"),
                    PaletteTransition.HOLD,
                ),
                RenderCue(
                    "2",
                    RenderProfile(1200, 512, "ocean", "2"),
                    PaletteTransition.BLEND,
                ),
            )
        ),
        mark_dirty=False,
    )
    app._preview_camera_path(app.camera_path.evaluate("1"), "1")
    preview_request = app._request(0.1)
    assert preview_request.max_iterations == 1200
    assert preview_request.reference_bits == 512
    assert app._render_palette() == PaletteBlend("inferno", "ocean", 0.5)
    assert app._render_cycles() == 1.5

    app.open_export_dialog()
    export_dialog = app.export_dialog
    assert export_dialog is not None
    root.update_idletasks()
    assert "2 Keyframes" in export_dialog.path_summary_var.get()
    assert "60 Frames" in export_dialog.plan_summary_var.get()
    assert export_dialog.tone_stability_var.get() == "Zeitlich stabilisiert"
    assert "Tone Mapping: Zeitlich stabilisiert" in export_dialog.plan_summary_var.get()
    export_source, _config, export_request, *_rest = export_dialog._context()
    assert isinstance(export_source, FlightPlanDocument)
    assert len(export_source.render_track.cues) == 2
    assert export_request.max_iterations == int(app.iterations_var.get())
    export_dialog.destroy()
    root.update_idletasks()

    app.preview_scale_var.set(0.15)
    root.after(250, app.request_render)
    root.after(2500, app._on_close)
    root.mainloop()
    print("GUI smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
