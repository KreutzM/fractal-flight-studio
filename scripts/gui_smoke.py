"""Headless-friendly GUI smoke test; use xvfb-run on Linux."""

from __future__ import annotations

import tkinter as tk

from fractal_flight_studio.camera import CameraState
from fractal_flight_studio.flight_app import FractalStudioApp
from fractal_flight_studio.flight_path import (
    CameraPath,
    CenterInterpolation,
    FlightKeyframe,
)


def main() -> int:
    root = tk.Tk()
    app = FractalStudioApp(root)
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
    timeline.destroy()
    root.update_idletasks()

    app.camera_path = CameraPath(
        (
            FlightKeyframe("0", CameraState("-0.5", "0", "3.5")),
            FlightKeyframe("2", CameraState("-0.75", "0.1", "0.1")),
        )
    )
    app.open_export_dialog()
    export_dialog = app.export_dialog
    assert export_dialog is not None
    root.update_idletasks()
    assert "2 Keyframes" in export_dialog.path_summary_var.get()
    assert "60 Frames" in export_dialog.plan_summary_var.get()
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
