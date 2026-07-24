from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import math
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import mpmath as mp
from PIL import Image, ImageTk

from .deep_zoom import digits_for_bits
from .gpu_info import inspect_cuda
from .models import FractalKind, Precision, RenderMode, RenderRequest, Viewport
from .palettes import palette_names
from .renderers import available_renderers, select_renderer


class FractalStudioApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Fractal Flight Studio")
        self.root.geometry("1260x820")
        self.root.minsize(900, 600)

        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fractal-render")
        self.render_generation = 0
        self.render_in_progress = False
        self.last_rgb = None
        self.photo: ImageTk.PhotoImage | None = None
        self.drag_start: tuple[int, int] | None = None
        self.flight_running = False
        self.flight_target_text: tuple[str, str] | None = None
        self.last_frame_time = time.perf_counter()
        self.cuda_status = inspect_cuda()

        self.center_x_text = "-0.5"
        self.center_y_text = "0.0"
        self.view_width_text = "3.5"

        self._build_ui()
        self._bind_events()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self.request_render)

    def _build_ui(self) -> None:
        outer = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        outer.pack(fill=tk.BOTH, expand=True)

        controls = ttk.Frame(outer, padding=10)
        viewer = ttk.Frame(outer)
        outer.add(controls, weight=0)
        outer.add(viewer, weight=1)

        self.canvas = tk.Canvas(viewer, background="#080808", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.fractal_var = tk.StringVar(value=FractalKind.MANDELBROT.value)
        self.backend_var = tk.StringVar(value="auto")
        self.precision_var = tk.StringVar(value=Precision.FLOAT32.value)
        self.render_mode_var = tk.StringVar(value=RenderMode.AUTO.value)
        self.reference_bits_var = tk.IntVar(value=256)
        self.palette_var = tk.StringVar(value="inferno")
        self.iterations_var = tk.IntVar(value=400)
        self.cycles_var = tk.DoubleVar(value=1.0)
        self.julia_real_var = tk.DoubleVar(value=-0.8)
        self.julia_imag_var = tk.DoubleVar(value=0.156)
        self.exponent_var = tk.IntVar(value=3)
        default_scale = 1.0 if self.cuda_status.available else 0.75
        self.preview_scale_var = tk.DoubleVar(value=default_scale)
        self.flight_scale_var = tk.DoubleVar(value=default_scale)
        self.flight_rate_var = tk.DoubleVar(value=1.035)
        self.status_var = tk.StringVar(value="Initialisierung …")
        self.position_var = tk.StringVar(value="")

        row = 0
        ttk.Label(controls, text="Fraktal", font=("TkDefaultFont", 11, "bold")).grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Combobox(
            controls,
            textvariable=self.fractal_var,
            values=[f.value for f in FractalKind],
            state="readonly",
            width=20,
        ).grid(row=row, column=0, sticky="ew", pady=(2, 8))
        row += 1

        ttk.Label(controls, text="Backend").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Combobox(
            controls,
            textvariable=self.backend_var,
            values=("auto", "cpu", "cuda"),
            state="readonly",
        ).grid(row=row, column=0, sticky="ew", pady=(2, 8))
        row += 1

        ttk.Label(controls, text="Präzision").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Combobox(
            controls,
            textvariable=self.precision_var,
            values=[p.value for p in Precision],
            state="readonly",
        ).grid(row=row, column=0, sticky="ew", pady=(2, 8))
        row += 1

        ttk.Label(controls, text="Berechnungsmodus").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Combobox(
            controls,
            textvariable=self.render_mode_var,
            values=[m.value for m in RenderMode],
            state="readonly",
        ).grid(row=row, column=0, sticky="ew", pady=(2, 8))
        row += 1

        ttk.Label(controls, text="Referenzpräzision (Bits)").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Combobox(
            controls,
            textvariable=self.reference_bits_var,
            values=(128, 192, 256, 384, 512, 768, 1024),
            state="readonly",
        ).grid(row=row, column=0, sticky="ew", pady=(2, 8))
        row += 1

        ttk.Label(controls, text="Vorschau-Skalierung").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Combobox(
            controls,
            textvariable=self.preview_scale_var,
            values=(0.5, 0.75, 1.0),
            state="readonly",
        ).grid(row=row, column=0, sticky="ew", pady=(2, 8))
        row += 1

        ttk.Label(controls, text="Iterationen").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Spinbox(controls, from_=20, to=100000, textvariable=self.iterations_var, increment=20).grid(
            row=row, column=0, sticky="ew", pady=(2, 8)
        )
        row += 1

        ttk.Label(controls, text="Palette").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Combobox(
            controls,
            textvariable=self.palette_var,
            values=palette_names(),
            state="readonly",
        ).grid(row=row, column=0, sticky="ew", pady=(2, 8))
        row += 1

        ttk.Label(controls, text="Farbzyklen").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Scale(controls, from_=0.25, to=8.0, variable=self.cycles_var, orient=tk.HORIZONTAL).grid(
            row=row, column=0, sticky="ew", pady=(2, 8)
        )
        row += 1

        julia = ttk.LabelFrame(controls, text="Julia / Multibrot", padding=6)
        julia.grid(row=row, column=0, sticky="ew", pady=6)
        ttk.Label(julia, text="c real").grid(row=0, column=0, sticky="w")
        ttk.Entry(julia, textvariable=self.julia_real_var, width=12).grid(row=0, column=1)
        ttk.Label(julia, text="c imag").grid(row=1, column=0, sticky="w")
        ttk.Entry(julia, textvariable=self.julia_imag_var, width=12).grid(row=1, column=1)
        ttk.Label(julia, text="Exponent").grid(row=2, column=0, sticky="w")
        ttk.Spinbox(julia, from_=2, to=8, textvariable=self.exponent_var, width=10).grid(row=2, column=1)
        row += 1

        flight = ttk.LabelFrame(controls, text="Flug", padding=6)
        flight.grid(row=row, column=0, sticky="ew", pady=6)
        ttk.Label(flight, text="Zoom pro Frame").grid(row=0, column=0, sticky="w")
        ttk.Entry(flight, textvariable=self.flight_rate_var, width=10).grid(row=0, column=1)
        ttk.Label(flight, text="Render-Skalierung").grid(row=1, column=0, sticky="w")
        ttk.Combobox(
            flight,
            textvariable=self.flight_scale_var,
            values=(0.5, 0.75, 1.0),
            state="readonly",
            width=8,
        ).grid(row=1, column=1)
        self.flight_button = ttk.Button(flight, text="Flug starten", command=self.toggle_flight)
        self.flight_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Label(flight, text="Rechtsklick setzt Ziel", foreground="#555").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )
        row += 1

        buttons = ttk.Frame(controls)
        buttons.grid(row=row, column=0, sticky="ew", pady=(8, 4))
        ttk.Button(buttons, text="Rendern", command=self.request_render).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(buttons, text="Reset", command=self.reset_view).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
        row += 1
        ttk.Button(controls, text="PNG exportieren", command=self.export_png).grid(row=row, column=0, sticky="ew")
        row += 1
        ttk.Button(controls, text="GPU-Diagnose", command=self.show_gpu_diagnostics).grid(
            row=row, column=0, sticky="ew", pady=(4, 0)
        )
        row += 1

        ttk.Separator(controls).grid(row=row, column=0, sticky="ew", pady=8)
        row += 1
        ttk.Label(controls, textvariable=self.status_var, wraplength=240).grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Label(controls, textvariable=self.position_var, wraplength=240).grid(row=row, column=0, sticky="w", pady=(4, 0))
        controls.columnconfigure(0, weight=1)

        for variable in (
            self.fractal_var,
            self.backend_var,
            self.precision_var,
            self.render_mode_var,
            self.reference_bits_var,
            self.palette_var,
            self.iterations_var,
            self.cycles_var,
            self.julia_real_var,
            self.julia_imag_var,
            self.exponent_var,
            self.preview_scale_var,
            self.flight_scale_var,
        ):
            variable.trace_add("write", lambda *_: self.root.after_idle(self.request_render))

    def _bind_events(self) -> None:
        self.canvas.bind("<Configure>", lambda _event: self.request_render())
        self.canvas.bind("<ButtonPress-1>", self._drag_begin)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        self.canvas.bind("<Button-3>", self._set_flight_target)
        self.canvas.bind("<Motion>", self._show_coordinate)
        self.canvas.bind("<MouseWheel>", self._mousewheel)
        self.canvas.bind("<Button-4>", lambda event: self._zoom_event(event, 1.35))
        self.canvas.bind("<Button-5>", lambda event: self._zoom_event(event, 1 / 1.35))

    def _work_digits(self) -> int:
        return digits_for_bits(int(self.reference_bits_var.get()))

    def _format_precise(self, value: mp.mpf) -> str:
        return mp.nstr(value, n=self._work_digits())

    @staticmethod
    def _format_display(value: mp.mpf, digits: int = 14) -> str:
        return mp.nstr(value, n=digits)

    def _view_values(self) -> tuple[mp.mpf, mp.mpf, mp.mpf]:
        with mp.workdps(self._work_digits()):
            return (
                mp.mpf(self.center_x_text),
                mp.mpf(self.center_y_text),
                mp.mpf(self.view_width_text),
            )

    def _set_view_values(self, center_x: mp.mpf, center_y: mp.mpf, width: mp.mpf) -> None:
        self.center_x_text = self._format_precise(center_x)
        self.center_y_text = self._format_precise(center_y)
        self.view_width_text = self._format_precise(width)

    def _proxy_float(self, text: str, minimum_positive: float | None = None) -> float:
        with mp.workdps(self._work_digits()):
            value = mp.mpf(text)
        try:
            converted = float(value)
        except OverflowError:
            converted = math.copysign(float("inf"), float(value))
        if minimum_positive is not None and converted == 0.0 and value > 0:
            return minimum_positive
        return converted

    def _pixel_to_complex_hp(self, px: float, py: float) -> tuple[mp.mpf, mp.mpf]:
        canvas_width = max(1, self.canvas.winfo_width())
        canvas_height = max(1, self.canvas.winfo_height())
        with mp.workdps(self._work_digits()):
            center_x, center_y, width = self._view_values()
            aspect = mp.mpf(canvas_height) / mp.mpf(canvas_width)
            x = center_x + (mp.mpf(px) / canvas_width - mp.mpf("0.5")) * width
            y = center_y + (mp.mpf(py) / canvas_height - mp.mpf("0.5")) * width * aspect
            return x, y

    def _zoom_view_hp(self, px: float, py: float, factor: float) -> None:
        if factor <= 0:
            return
        with mp.workdps(self._work_digits()):
            before_x, before_y = self._pixel_to_complex_hp(px, py)
            center_x, center_y, width = self._view_values()
            width = width / mp.mpf(factor)
            self._set_view_values(center_x, center_y, width)
            after_x, after_y = self._pixel_to_complex_hp(px, py)
            center_x, center_y, width = self._view_values()
            self._set_view_values(
                center_x + before_x - after_x,
                center_y + before_y - after_y,
                width,
            )

    def _pan_view_hp(self, dx_pixels: float, dy_pixels: float) -> None:
        canvas_width = max(1, self.canvas.winfo_width())
        with mp.workdps(self._work_digits()):
            center_x, center_y, width = self._view_values()
            units_per_pixel = width / canvas_width
            self._set_view_values(
                center_x - mp.mpf(dx_pixels) * units_per_pixel,
                center_y - mp.mpf(dy_pixels) * units_per_pixel,
                width,
            )

    def _request(self, scale: float | None = None) -> RenderRequest:
        scale = self.preview_scale_var.get() if scale is None else scale
        canvas_width = max(64, self.canvas.winfo_width())
        canvas_height = max(64, self.canvas.winfo_height())
        width = max(64, int(canvas_width * scale))
        height = max(64, int(canvas_height * scale))
        proxy_viewport = Viewport(
            center_x=self._proxy_float(self.center_x_text),
            center_y=self._proxy_float(self.center_y_text),
            width=self._proxy_float(self.view_width_text, minimum_positive=1e-300),
        )
        return RenderRequest(
            width=width,
            height=height,
            viewport=proxy_viewport,
            fractal=FractalKind(self.fractal_var.get()),
            max_iterations=int(self.iterations_var.get()),
            julia_c_real=float(self.julia_real_var.get()),
            julia_c_imag=float(self.julia_imag_var.get()),
            exponent=int(self.exponent_var.get()),
            precision=Precision(self.precision_var.get()),
            render_mode=RenderMode(self.render_mode_var.get()),
            reference_bits=int(self.reference_bits_var.get()),
            center_x_text=self.center_x_text,
            center_y_text=self.center_y_text,
            view_width_text=self.view_width_text,
        )

    def request_render(self) -> None:
        self.render_generation += 1
        if self.render_in_progress:
            return
        try:
            scale = self.flight_scale_var.get() if self.flight_running else self.preview_scale_var.get()
            request = self._request(scale)
            backend_name = self.backend_var.get()
            renderer = select_renderer(backend_name)
            palette = self.palette_var.get()
            cycles = float(self.cycles_var.get())
        except Exception as exc:
            self.status_var.set(str(exc))
            return

        self.render_in_progress = True
        generation = self.render_generation
        self.status_var.set(
            f"Rendere mit {renderer.name} ({request.width}×{request.height}, {request.precision.value}, {request.render_mode.value}) …"
        )
        future = self.executor.submit(renderer.render_frame, request, palette, cycles, 0.0)
        self.root.after(10, self._poll_render, future, generation)

    def _poll_render(self, future: Future, generation: int) -> None:
        if future.done():
            self._finish_render(future, generation)
            return
        self.root.after(20, self._poll_render, future, generation)

    def _finish_render(self, future: Future, generation: int) -> None:
        self.render_in_progress = False
        try:
            result = future.result()
            rgb = result.rgb
            self.last_rgb = rgb
            display_started = time.perf_counter()
            image = Image.fromarray(rgb, mode="RGB")
            canvas_size = (
                max(1, self.canvas.winfo_width()),
                max(1, self.canvas.winfo_height()),
            )
            if image.size != canvas_size:
                image = image.resize(canvas_size, Image.Resampling.BILINEAR)
            self.photo = ImageTk.PhotoImage(image)
            if getattr(self, "canvas_image_id", None) is None:
                self.canvas_image_id = self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
            else:
                self.canvas.itemconfigure(self.canvas_image_id, image=self.photo)
            display_seconds = time.perf_counter() - display_started
            total_seconds = result.elapsed_seconds + display_seconds
            fps = 1.0 / total_seconds if total_seconds > 0 else float("inf")
            device = result.details.get("device")
            device_line = f"\nGPU: {device}" if device else ""
            fallback_line = ""
            if result.backend == "cpu-numba" and self.backend_var.get() == "auto" and not self.cuda_status.available:
                fallback_line = f"\nAuto-Fallback: {self.cuda_status.reason}"
            optimized = "GPU-RGB" if result.details.get("optimized_frame_path") else "CPU-RGB"
            allocation = float(result.details.get("allocation_seconds", 0.0))
            reference_upload = float(result.details.get("reference_upload_seconds", 0.0))
            allocation_line = f"; Puffer {allocation * 1000:.1f} ms" if allocation > 0 else ""
            upload_line = f"; Ref {reference_upload * 1000:.1f} ms" if reference_upload > 0 else ""
            render_mode = result.details.get("render_mode", "direct")
            ref_bits = int(result.details.get("reference_bits", 0) or 0)
            repair_line = ""
            if result.details.get("rebasing_enabled"):
                if "rebase_pixels" in result.details:
                    repair_line += f"; Rebases {int(result.details['rebase_pixels'])}"
                else:
                    repair_line += "; Rebasing aktiv"
            if result.details.get("glitch_detection_enabled"):
                if "glitch_pixels" in result.details:
                    repair_line += f"; Glitch-Reparaturen {int(result.details['glitch_pixels'])}"
                else:
                    repair_line += "; Glitch-Reparatur aktiv"
            reference_line = ""
            if render_mode == "perturbation":
                reference_line = "; Referenz wiederverwendet" if result.details.get("reference_reused") else "; Referenz neu"
            deep_line = (
                f"; Modus {render_mode}"
                + (f"; RefBits {ref_bits}" if ref_bits else "")
                + reference_line
                + repair_line
            )
            self.status_var.set(
                f"{result.backend}/{optimized}: Rechnen+Transfer {result.elapsed_seconds * 1000:.1f} ms; "
                f"Anzeige {display_seconds * 1000:.1f} ms; ca. {fps:.1f} FPS"
                f"{allocation_line}{upload_line}{deep_line}"
                f"{device_line}{fallback_line}\n"
                f"Rendergröße: {rgb.shape[1]}×{rgb.shape[0]}; Ansichtsbreite: {self.view_width_text}"
            )
        except Exception as exc:
            self.status_var.set(f"Renderfehler: {exc}")

        if generation != self.render_generation:
            self.request_render()

    def _mousewheel(self, event: tk.Event) -> None:
        self._zoom_event(event, 1.35 if event.delta > 0 else 1 / 1.35)

    def _zoom_event(self, event: tk.Event, factor: float) -> None:
        self._zoom_view_hp(event.x, event.y, factor)
        self.request_render()

    def _drag_begin(self, event: tk.Event) -> None:
        self.drag_start = (event.x, event.y)

    def _drag_move(self, event: tk.Event) -> None:
        if self.drag_start is None:
            return
        dx = event.x - self.drag_start[0]
        dy = event.y - self.drag_start[1]
        self._pan_view_hp(dx, dy)
        self.drag_start = (event.x, event.y)
        self.request_render()

    def _drag_end(self, _event: tk.Event) -> None:
        self.drag_start = None

    def _set_flight_target(self, event: tk.Event) -> None:
        x, y = self._pixel_to_complex_hp(event.x, event.y)
        self.flight_target_text = (self._format_precise(x), self._format_precise(y))
        self.position_var.set(
            f"Flugziel: {self._format_display(x, 16)}, {self._format_display(y, 16)}"
        )

    def _show_coordinate(self, event: tk.Event) -> None:
        x, y = self._pixel_to_complex_hp(event.x, event.y)
        target = " gesetzt" if self.flight_target_text else " nicht gesetzt"
        self.position_var.set(
            f"Cursor: {self._format_display(x, 12)}, {self._format_display(y, 12)}\n"
            f"Flugziel:{target}"
        )

    def toggle_flight(self) -> None:
        if not self.flight_running and self.flight_target_text is None:
            messagebox.showinfo("Flugziel", "Setze zuerst mit Rechtsklick ein Flugziel.")
            return
        self.flight_running = not self.flight_running
        self.flight_button.configure(text="Flug stoppen" if self.flight_running else "Flug starten")
        if self.flight_running:
            self.last_frame_time = time.perf_counter()
            self._flight_step()

    def _flight_step(self) -> None:
        if not self.flight_running or self.flight_target_text is None:
            return
        try:
            rate = max(1.0001, float(self.flight_rate_var.get()))
        except ValueError:
            rate = 1.035
        with mp.workdps(self._work_digits()):
            center_x, center_y, width = self._view_values()
            tx = mp.mpf(self.flight_target_text[0])
            ty = mp.mpf(self.flight_target_text[1])
            attraction = mp.mpf("0.08")
            self._set_view_values(
                center_x + (tx - center_x) * attraction,
                center_y + (ty - center_y) * attraction,
                width / mp.mpf(rate),
            )
        self.request_render()
        self.root.after(33, self._flight_step)

    def reset_view(self) -> None:
        kind = FractalKind(self.fractal_var.get())
        if kind is FractalKind.NEWTON:
            self.center_x_text, self.center_y_text, self.view_width_text = "0.0", "0.0", "4.0"
        elif kind is FractalKind.BURNING_SHIP:
            self.center_x_text, self.center_y_text, self.view_width_text = "-0.5", "-0.5", "3.5"
        else:
            self.center_x_text, self.center_y_text, self.view_width_text = "-0.5", "0.0", "3.5"
        self.request_render()

    def show_gpu_diagnostics(self) -> None:
        self.cuda_status = inspect_cuda()
        messagebox.showinfo("GPU-Diagnose", self.cuda_status.report())

    def export_png(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if not path:
            return
        try:
            renderer = select_renderer(self.backend_var.get())
            request = self._request(1.0)
            result = renderer.render_frame(request, self.palette_var.get(), float(self.cycles_var.get()))
            Image.fromarray(result.rgb, mode="RGB").save(path)
            self.status_var.set(f"Exportiert: {path}")
        except Exception as exc:
            messagebox.showerror("Exportfehler", str(exc))

    def _on_close(self) -> None:
        self.flight_running = False
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = FractalStudioApp(root)
    backends = ", ".join(available_renderers())
    app.status_var.set(f"Verfügbare Backends: {backends}\n{app.cuda_status.summary}")
    root.mainloop()


if __name__ == "__main__":
    main()
