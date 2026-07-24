"""Headless-friendly GUI smoke test; use xvfb-run on Linux."""

from __future__ import annotations

import tkinter as tk

from fractal_flight_studio.app import FractalStudioApp


def main() -> int:
    root = tk.Tk()
    app = FractalStudioApp(root)
    app.preview_scale_var.set(0.15)

    # Exercise automatic flight termination without waiting through a deep zoom.
    app.flight_target_text = ("-0.743643887037151", "0.13182590420533")
    app.view_width_text = "1e-90"
    app.toggle_flight()
    assert app.flight_running is False
    assert app.flight_stop_notice is not None

    root.after(250, app.request_render)
    root.after(2500, app._on_close)
    root.mainloop()
    print("GUI smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
