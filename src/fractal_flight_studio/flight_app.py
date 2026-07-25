from __future__ import annotations

from concurrent.futures import Future
import tkinter as tk
from tkinter import ttk

from .app import FractalStudioApp as BaseFractalStudioApp
from .deep_zoom import PixelGridExhaustedError
from .deep_zoom_targets import DeepZoomTarget, favorite_deep_zoom_targets
from .flight_quality import FrameVisualQuality, analyze_frame_visual_quality
from .models import RenderRequest
from .renderers import available_renderers


class FractalStudioApp(BaseFractalStudioApp):
    """GUI variant that rejects numerically or visually exhausted flight frames."""

    def __init__(self, root: tk.Tk) -> None:
        self.last_good_flight_view: tuple[str, str, str] | None = None
        self.last_good_flight_rgb = None
        self.pending_final_flight_quality_check = False
        self.deep_zoom_targets = favorite_deep_zoom_targets()
        self.deep_zoom_targets_by_name = {target.name: target for target in self.deep_zoom_targets}
        super().__init__(root)
        self._build_deep_zoom_target_bar()

    def _build_deep_zoom_target_bar(self) -> None:
        existing = self.root.winfo_children()
        before = existing[0] if existing else None
        bar = ttk.Frame(self.root, padding=(8, 5))
        pack_options = {"side": tk.TOP, "fill": tk.X}
        if before is not None:
            pack_options["before"] = before
        bar.pack(**pack_options)

        ttk.Label(bar, text="Deep-Zoom-Ziel:").pack(side=tk.LEFT)
        first_name = self.deep_zoom_targets[0].name if self.deep_zoom_targets else ""
        self.deep_zoom_target_var = tk.StringVar(value=first_name)
        combo = ttk.Combobox(
            bar,
            textvariable=self.deep_zoom_target_var,
            values=tuple(target.name for target in self.deep_zoom_targets),
            state="readonly",
            width=29,
        )
        combo.pack(side=tk.LEFT, padx=(6, 6))
        combo.bind("<<ComboboxSelected>>", self._on_deep_zoom_target_selected)
        ttk.Button(bar, text="Als Flugziel", command=self.set_catalog_flight_target).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(bar, text="Ansicht laden", command=self.load_catalog_target_view).pack(
            side=tk.LEFT
        )
        self.deep_zoom_target_summary_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.deep_zoom_target_summary_var, foreground="#555").pack(
            side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True
        )
        self._update_deep_zoom_target_summary()

    def _selected_deep_zoom_target(self) -> DeepZoomTarget | None:
        return self.deep_zoom_targets_by_name.get(self.deep_zoom_target_var.get())

    def _update_deep_zoom_target_summary(self) -> None:
        target = self._selected_deep_zoom_target()
        if target is None:
            self.deep_zoom_target_summary_var.set("")
            return
        self.deep_zoom_target_summary_var.set(
            f"{target.recommended_iterations} Iter.; {target.reference_bits} Bit; {target.palette}"
        )

    def _on_deep_zoom_target_selected(self, _event: tk.Event | None = None) -> None:
        self._update_deep_zoom_target_summary()

    def _apply_deep_zoom_target(self, target: DeepZoomTarget, *, load_view: bool) -> None:
        if self.flight_running:
            self._stop_flight()
        self.fractal_var.set(target.fractal.value)
        self.iterations_var.set(target.recommended_iterations)
        self.reference_bits_var.set(target.reference_bits)
        self.palette_var.set(target.palette)
        self.flight_target_text = (target.center_x_text, target.center_y_text)

        action = "als Flugziel gesetzt"
        if load_view:
            self.center_x_text = target.center_x_text
            self.center_y_text = target.center_y_text
            self.view_width_text = target.view_width_text
            action = "geladen und als Flugziel gesetzt"
            self.request_render()

        self.position_var.set(
            f"{target.name} {action}.\n"
            f"Zentrum: {target.center_x_text}, {target.center_y_text}; "
            f"Breite: {target.view_width_text}"
        )

    def set_catalog_flight_target(self) -> None:
        target = self._selected_deep_zoom_target()
        if target is not None:
            self._apply_deep_zoom_target(target, load_view=False)

    def load_catalog_target_view(self) -> None:
        target = self._selected_deep_zoom_target()
        if target is not None:
            self._apply_deep_zoom_target(target, load_view=True)

    def toggle_flight(self) -> None:
        starting = not self.flight_running and self.flight_target_text is not None
        if starting:
            self.pending_final_flight_quality_check = False
            self.last_good_flight_view = (
                self.center_x_text,
                self.center_y_text,
                self.view_width_text,
            )
            self.last_good_flight_rgb = self.last_rgb.copy() if self.last_rgb is not None else None
        super().toggle_flight()

    def _stop_flight(self, message: str | None = None) -> None:
        # The base implementation submits the numerically clamped final frame
        # before it clears flight_running. Keep that one candidate under the
        # visual-quality gate even when an earlier render is still finishing.
        if self.flight_running and message and "numerische Präzisionsgrenze" in message:
            self.pending_final_flight_quality_check = True
        super()._stop_flight(message)

    def _should_check_flight_result(self, generation: int) -> bool:
        return self.flight_running or (
            self.pending_final_flight_quality_check and generation == self.render_generation
        )

    def _restore_last_good_flight_frame(
        self, error: PixelGridExhaustedError | None = None, visual: FrameVisualQuality | None = None
    ) -> None:
        if self.last_good_flight_view is not None:
            self.center_x_text, self.center_y_text, self.view_width_text = self.last_good_flight_view
        if self.last_good_flight_rgb is not None:
            self.last_rgb = self.last_good_flight_rgb

        if error is not None:
            quality = error.quality
            details = (
                f"Eindeutige Pixelkoordinaten: X {quality.x_unique_fraction:.1%}, "
                f"Y {quality.y_unique_fraction:.1%}; "
                f"größter Block: {quality.maximum_equal_run} Pixel."
            )
        elif visual is not None:
            details = (
                f"Grund: {visual.reason}; dominante Farbe {visual.dominant_color_fraction:.1%}; "
                f"wiederholte Zeilen/Spalten {visual.repeated_row_fraction:.1%}/"
                f"{visual.repeated_column_fraction:.1%}."
            )
        else:
            details = "Die Bildqualität ist unter die Fluggrenze gefallen."

        self.pending_final_flight_quality_check = False
        self._stop_flight(
            "Flug automatisch gestoppt: Der nächste Frame ist nicht mehr sinnvoll aufgelöst.\n"
            + details
        )

    def _finish_render(self, future: Future, generation: int, request: RenderRequest) -> None:
        try:
            result = future.result()
        except PixelGridExhaustedError as error:
            self.render_in_progress = False
            if self._should_check_flight_result(generation):
                self._restore_last_good_flight_frame(error)
                self.render_generation += 1
                self.request_render()
            else:
                self.status_var.set(f"Rendergrenze erreicht: {error}")
            return

        check_flight_quality = self._should_check_flight_result(generation)
        if check_flight_quality:
            visual = analyze_frame_visual_quality(result.rgb)
            if not visual.safe:
                self.render_in_progress = False
                self._restore_last_good_flight_frame(visual=visual)
                self.render_generation += 1
                self.request_render()
                return

            self.last_good_flight_view = (
                request.center_x_text or repr(request.viewport.center_x),
                request.center_y_text or repr(request.viewport.center_y),
                request.view_width_text or repr(request.viewport.width),
            )
            self.last_good_flight_rgb = result.rgb.copy()
            if self.pending_final_flight_quality_check and generation == self.render_generation:
                self.pending_final_flight_quality_check = False

        super()._finish_render(future, generation, request)


def main() -> None:
    root = tk.Tk()
    app = FractalStudioApp(root)
    backends = ", ".join(available_renderers())
    app.status_var.set(f"Verfügbare Backends: {backends}\n{app.cuda_status.summary}")
    root.mainloop()


if __name__ == "__main__":
    main()
