from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .app import FractalStudioApp as BaseFractalStudioApp
from .camera import CameraState
from .deep_zoom import PixelGridExhaustedError
from .deep_zoom_targets import DeepZoomTarget, favorite_deep_zoom_targets, load_deep_zoom_targets
from .export_controller import FlightExportController
from .export_warning_dialog import FlightExportDialog
from .flight_path import CameraPath
from .flight_plan_io import (
    FLIGHT_PLAN_EXTENSION,
    FlightPlanDocument,
    load_flight_plan,
    save_flight_plan,
    suggested_flight_plan_name,
)
from .flight_quality import FrameVisualQuality, analyze_frame_visual_quality
from .models import RenderRequest
from .target_browser import DeepZoomTargetBrowser
from .timeline_editor import CameraPathEditorWindow
from .renderers import available_renderers, select_renderer


class FractalStudioApp(BaseFractalStudioApp):
    """GUI adapter that rejects numerically or visually exhausted flight frames."""

    def __init__(self, root: tk.Tk) -> None:
        self.deep_zoom_targets = favorite_deep_zoom_targets()
        self.all_deep_zoom_targets = load_deep_zoom_targets()
        self.target_browser: DeepZoomTargetBrowser | None = None
        self.timeline_editor: CameraPathEditorWindow | None = None
        self.export_dialog: FlightExportDialog | None = None
        self.export_controller = FlightExportController()
        self.camera_path: CameraPath | None = None
        self.camera_path_file: Path | None = None
        self.camera_path_name = "Unbenannter Flugplan"
        self.camera_path_dirty = False
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
        ttk.Button(bar, text="Ziele durchsuchen …", command=self.open_target_browser).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Button(bar, text="Flugplan …", command=self.open_timeline_editor).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Button(bar, text="Öffnen …", command=self.open_flight_plan).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Button(bar, text="Speichern", command=self.save_flight_plan).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Button(bar, text="Speichern unter …", command=self.save_flight_plan_as).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Button(bar, text="Video exportieren …", command=self.open_export_dialog).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        self.deep_zoom_target_summary_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.deep_zoom_target_summary_var, foreground="#555").pack(
            side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True
        )
        self._update_deep_zoom_target_summary()


    def request_render(self) -> None:
        if self.export_controller.busy:
            return
        super().request_render()

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
        if self.flight_controller.running:
            self._stop_flight()
        self.fractal_var.set(target.fractal.value)
        self.iterations_var.set(target.recommended_iterations)
        self.reference_bits_var.set(target.reference_bits)
        self.palette_var.set(target.palette)
        self.flight_controller.set_target(target.center_x_text, target.center_y_text)

        action = "als Flugziel gesetzt"
        if load_view:
            self.camera = CameraState(
                target.center_x_text,
                target.center_y_text,
                target.view_width_text,
            )
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

    def _apply_browser_target(self, target: DeepZoomTarget, *, load_view: bool) -> None:
        if target.name in self.deep_zoom_targets_by_name:
            self.deep_zoom_target_var.set(target.name)
            self._update_deep_zoom_target_summary()
        self._apply_deep_zoom_target(target, load_view=load_view)

    def open_target_browser(self) -> None:
        if self.target_browser is not None and self.target_browser.winfo_exists():
            self.target_browser.deiconify()
            self.target_browser.lift()
            self.target_browser.focus_set()
            return
        self.target_browser = DeepZoomTargetBrowser(
            self.root,
            self.all_deep_zoom_targets,
            on_set_target=lambda target: self._apply_browser_target(target, load_view=False),
            on_load_view=lambda target: self._apply_browser_target(target, load_view=True),
        )

    def open_timeline_editor(self) -> None:
        if self.timeline_editor is not None and self.timeline_editor.winfo_exists():
            self.timeline_editor.deiconify()
            self.timeline_editor.lift()
            self.timeline_editor.focus_set()
            return
        self.timeline_editor = CameraPathEditorWindow(
            self.root,
            get_current_camera=lambda: self.camera,
            targets=self.all_deep_zoom_targets,
            on_preview=self._preview_camera_path,
            on_path_changed=self._store_camera_path,
            initial_path=self.camera_path,
            digits=self._work_digits(),
        )

    def _store_camera_path(self, path: CameraPath | None) -> None:
        if path != self.camera_path:
            self.camera_path_dirty = True
        self.camera_path = path
        if path is not None:
            marker = " *" if self.camera_path_dirty else ""
            self.position_var.set(
                f"Flugplan {self.camera_path_name}{marker}: "
                f"{len(path.keyframes)} Keyframes, Dauer {path.duration_text} s."
            )
        if self.export_dialog is not None and self.export_dialog.winfo_exists():
            self.export_dialog.refresh_path_summary()

    def _confirm_discard_flight_plan_changes(self, action: str) -> bool:
        if not self.camera_path_dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Ungespeicherte Änderungen",
            f"Der Flugplan wurde geändert. Vor {action} speichern?",
            parent=self.root,
        )
        if answer is None:
            return False
        if answer:
            return self.save_flight_plan()
        return True

    def open_flight_plan(self) -> None:
        if not self._confirm_discard_flight_plan_changes("dem Öffnen"):
            return
        selected = filedialog.askopenfilename(
            parent=self.root,
            title="Flugplan öffnen",
            filetypes=(
                ("Fractal-Flight-Flugplan", f"*{FLIGHT_PLAN_EXTENSION}"),
                ("JSON-Dateien", "*.json"),
                ("Alle Dateien", "*.*"),
            ),
        )
        if selected:
            self._load_flight_plan_path(Path(selected))

    def _load_flight_plan_path(self, path: Path) -> bool:
        try:
            document = load_flight_plan(path)
        except Exception as exc:
            messagebox.showerror("Flugplan öffnen", str(exc), parent=self.root)
            return False
        self.camera_path = document.path
        self.camera_path_file = path
        self.camera_path_name = document.name
        self.camera_path_dirty = False
        if self.timeline_editor is not None and self.timeline_editor.winfo_exists():
            self.timeline_editor.destroy()
            self.timeline_editor = None
            self.open_timeline_editor()
        self.position_var.set(
            f"Flugplan {document.name} geladen: "
            f"{len(document.path.keyframes)} Keyframes, Dauer {document.path.duration_text} s."
        )
        if self.export_dialog is not None and self.export_dialog.winfo_exists():
            self.export_dialog.refresh_path_summary()
        return True

    def save_flight_plan(self) -> bool:
        if self.camera_path_file is None:
            return self.save_flight_plan_as()
        return self._save_flight_plan_path(self.camera_path_file)

    def save_flight_plan_as(self) -> bool:
        if self.camera_path is None:
            messagebox.showerror(
                "Flugplan speichern",
                "Der Flugplan muss mindestens zwei gültige Keyframes enthalten.",
                parent=self.root,
            )
            return False
        initial_name = (
            self.camera_path_file.name
            if self.camera_path_file is not None
            else f"{self.camera_path_name}{FLIGHT_PLAN_EXTENSION}"
        )
        selected = filedialog.asksaveasfilename(
            parent=self.root,
            title="Flugplan speichern unter",
            defaultextension=FLIGHT_PLAN_EXTENSION,
            initialfile=initial_name,
            filetypes=(("Fractal-Flight-Flugplan", f"*{FLIGHT_PLAN_EXTENSION}"),),
        )
        if not selected:
            return False
        path = Path(selected)
        self.camera_path_name = suggested_flight_plan_name(path)
        return self._save_flight_plan_path(path)

    def _save_flight_plan_path(self, path: Path) -> bool:
        if self.camera_path is None:
            messagebox.showerror(
                "Flugplan speichern",
                "Der Flugplan muss mindestens zwei gültige Keyframes enthalten.",
                parent=self.root,
            )
            return False
        try:
            save_flight_plan(
                path,
                FlightPlanDocument(self.camera_path_name, self.camera_path),
            )
        except Exception as exc:
            messagebox.showerror("Flugplan speichern", str(exc), parent=self.root)
            return False
        self.camera_path_file = path
        self.camera_path_dirty = False
        self.position_var.set(f"Flugplan {self.camera_path_name} gespeichert: {path}")
        return True

    def open_export_dialog(self) -> None:
        if self.export_dialog is not None and self.export_dialog.winfo_exists():
            self.export_dialog.deiconify()
            self.export_dialog.lift()
            self.export_dialog.focus_set()
            self.export_dialog.refresh_path_summary()
            return
        if self.flight_controller.running:
            self._stop_flight()
        self.export_dialog = FlightExportDialog(
            self.root,
            controller=self.export_controller,
            get_path=lambda: self.camera_path,
            build_request=lambda: self._request(1.0),
            get_renderer=lambda: select_renderer(self.backend_var.get()),
            get_palette=lambda: self.palette_var.get(),
            get_cycles=lambda: float(self.cycles_var.get()),
            ready_for_background_job=self._ready_for_export_job,
            on_job_finished=self.request_render,
        )

    def _ready_for_export_job(self) -> bool:
        if self.flight_controller.running:
            self._stop_flight()
        return not self.render_controller.busy

    def _preview_camera_path(self, camera: CameraState, time_seconds_text: str) -> None:
        if self.flight_controller.running:
            self._stop_flight()
        self.camera = camera
        self.position_var.set(
            f"Flugplan-Vorschau bei {time_seconds_text} s.\n"
            f"Zentrum: {camera.center_x_text}, {camera.center_y_text}; "
            f"Breite: {camera.view_width_text}"
        )
        self.request_render()

    def _should_check_flight_result(self, generation: int) -> bool:
        return self.flight_controller.should_check_result(
            generation,
            self.render_controller.generation,
        )

    def _restore_last_good_flight_frame(
        self,
        error: PixelGridExhaustedError | None = None,
        visual: FrameVisualQuality | None = None,
    ) -> None:
        camera, rgb = self.flight_controller.reject()
        if camera is not None:
            self.camera = camera
        if rgb is not None:
            self.last_rgb = rgb

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

        self._stop_flight(
            "Flug automatisch gestoppt: Der nächste Frame ist nicht mehr sinnvoll aufgelöst.\n"
            + details
        )

    def _on_close(self) -> None:
        if not self._confirm_discard_flight_plan_changes("dem Beenden"):
            return
        self.export_controller.cancel()
        self.export_controller.shutdown()
        super()._on_close()

    def _finish_render(self, future: Future, generation: int, request: RenderRequest) -> None:
        try:
            result = future.result()
        except PixelGridExhaustedError as error:
            render_invalidated = self.render_controller.complete(generation)
            if self._should_check_flight_result(generation):
                self._restore_last_good_flight_frame(error)
                self.request_render()
            else:
                self.status_var.set(f"Rendergrenze erreicht: {error}")
                if render_invalidated:
                    self.request_render()
            return

        if self._should_check_flight_result(generation):
            visual = analyze_frame_visual_quality(result.rgb)
            if not visual.safe:
                self.render_controller.complete(generation)
                self._restore_last_good_flight_frame(visual=visual)
                self.request_render()
                return
            self.flight_controller.accept(CameraState.from_request(request), result.rgb)

        super()._finish_render(future, generation, request)


def main() -> None:
    root = tk.Tk()
    app = FractalStudioApp(root)
    backends = ", ".join(available_renderers())
    app.status_var.set(f"Verfügbare Backends: {backends}\n{app.cuda_status.summary}")
    root.mainloop()


if __name__ == "__main__":
    main()
