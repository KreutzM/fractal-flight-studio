"""Headless-friendly GUI smoke test; use xvfb-run on Linux."""

from __future__ import annotations

import tkinter as tk

from fractal_flight_studio.app import FractalStudioApp


def main() -> int:
    root = tk.Tk()
    app = FractalStudioApp(root)
    app.preview_scale_var.set(0.15)
    root.after(250, app.request_render)
    root.after(2500, app._on_close)
    root.mainloop()
    print("GUI smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
