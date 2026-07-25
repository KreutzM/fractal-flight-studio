"""Headless-friendly GUI smoke test; use xvfb-run on Linux."""

from __future__ import annotations

import tkinter as tk

from fractal_flight_studio.flight_app import FractalStudioApp


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
    root.update_idletasks()
    app.preview_scale_var.set(0.15)
    root.after(250, app.request_render)
    root.after(2500, app._on_close)
    root.mainloop()
    print("GUI smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
