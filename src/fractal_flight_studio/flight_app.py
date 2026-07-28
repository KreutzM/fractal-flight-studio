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
from .flight_plan import (
    EvaluatedFlightFrame,
    FlightPlanDefaults,
    FlightScene,
    RenderProfile,
)
from .flight_plan_io import (
    FLIGHT_PLAN_EXTENSION,
    load_flight_plan,
    save_flight_plan,
    suggested_flight_plan_name,
)
from .flight_plan_session import FlightPlanSession
from .flight_plan_playback import PlaybackSample
from .flight_playback_panel import FlightPlanPlaybackPanel
from .flight_quality import FrameVisualQuality, analyze_frame_visual_quality
from .models import FractalKind, RenderRequest
from .path_editor import CameraPathDraft
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
        self.flight_playback_panel: FlightPlanPlaybackPanel | None = None
        self._applying_flight_plan_settings = False
        self._last_session_document_state: tuple[object, ...] | None = None
        self._path_preview_frame: EvaluatedFlightFrame | None = None
        self.deep_zoom_targets_by_name = {target.name: target for target in self.deep_zoom_targets}
        super().__init__(root)
        self.flight_plan_session = FlightPlanSession.new(
            self.camera,
            digits=self._work_digits(),
            scene=self._current_flight_scene(),
            render_profile=self._current_render_profile(),
        )
        self.flight_plan_session.add_listener(
            self._on_flight_plan_session_changed,
            notify=True,
        )
        for variable in (
            self.fractal_var,
            self.iterations_var,
            self.reference_bits_var,
            self.palette_var,
            self.cycles_var,
            self.julia_real_var,
            self.julia_imag_var,
            self.exponent_var,
        ):
            variable.trace_add("write", self._sync_primary_flight_settings)
        self._build_deep_zoom_target_bar()
        self._build_flight_playback_bar()

    @property
    def camera_path(self) -> CameraPath | None:
        return self.flight_plan_session.camera_path

    @camera_path.setter
    def camera_path(self, path: CameraPath | None) -> None:
        if path is None:
            self.flight_plan_session.set_camera_draft(
                CameraPathDraft(digits=self.flight_plan_session.camera_draft.digits)
            )
        else:
            self.flight_plan_session.set_camera_path(path)

    @property
    def camera_path_file(self) -> Path | None:
        return self.flight_plan_session.file_path

    @property
    def camera_path_name(self) -> str:
        return self.flight_plan_session.name

    @camera_path_name.setter
    def camera_path_name(self, name: str) -> None:
        self.flight_plan_session.set_name(name)

    @property
    def camera_path_dirty(self) -> bool:
        return self.flight_plan_session.dirty

    def _current_flight_scene(self) -> FlightScene:
        return FlightScene(
            FractalKind(self.fractal_var.get()),
            int(self.exponent_var.get()),
            repr(float(self.julia_real_var.get())),
            repr(float(self.julia_imag_var.get())),
        )

    def _current_render_profile(self) -> RenderProfile:
        return RenderProfile(
            max_iterations=int(self.iterations_var.get()),
            reference_bits=int(self.reference_bits_var.get()),
            palette=self.palette_var.get(),
            cycles_text=format(float(self.cycles_var.get()), ".17g"),
        )

    def _migration_defaults(self) -> FlightPlanDefaults:
        return FlightPlanDefaults(
            self._current_flight_scene(),
            self._current_render_profile(),
        )

    def _sync_primary_flight_settings(self, *_args) -> None:
        if self._applying_flight_plan_settings or not hasattr(self, "flight_plan_session"):
            return
        self._path_preview_frame = None
        try:
            self.flight_plan_session.sync_primary_settings(
                self._current_flight_scene(),
                self._current_render_profile(),
            )
        except Exception as exc:
            self.status_var.set(f"Flugplan-Einstellung ungültig: {exc}")

    def _apply_document_primary_settings(self, document) -> None:
        profile = document.render_track.first_profile
        scene = document.scene
        self._applying_flight_plan_settings = True
        try:
            self.fractal_var.set(scene.fractal.value)
            self.exponent_var.set(scene.exponent)
            self.julia_real_var.set(float(scene.julia_c_real_text))
            self.julia_imag_var.set(float(scene.julia_c_imag_text))
            self.iterations_var.set(profile.max_iterations)
            self.reference_bits_var.set(profile.reference_bits)
            self.palette_var.set(profile.palette)
            self.cycles_var.set(profile.cycles)
        finally:
            self._applying_flight_plan_settings = False

    def _on_flight_plan_session_changed(self, session: FlightPlanSession) -> None:
        state = (
            session.camera_draft,
            session.scene,
            session.render_track,
            session.name,
            session.file_path,
            session.dirty,
        )
        if state == self._last_session_document_state:
            return
        self._last_session_document_state = state
        self._path_preview_frame = None
        self._reload_playback_document()
        path = session.camera_path
        marker = " *" if session.dirty else ""
        if path is None:
            self.position_var.set(
                f"Flugplan {session.name}{marker}: Entwurf noch nicht exportierbar.\n"
                f"{session.validation_error}"
            )
        else:
            self.position_var.set(
                f"Flugplan {session.name}{marker}: {len(path.keyframes)} Keyframes, "
                f"Dauer {path.duration_text} s; {len(session.render_track.cues)} Render-Cues."
            )
        if self.export_dialog is not None and self.export_dialog.winfo_exists():
            self.export_dialog.refresh_path_summary()

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

    def _build_flight_playback_bar(self) -> None:
        existing = self.root.winfo_children()
        before = existing[0] if existing else None
        panel = FlightPlanPlaybackPanel(
            self.root,
            on_sample=self._apply_playback_sample,
            render_busy=lambda: self.render_controller.busy,
            request_render=self.request_render,
            keyframe_times=self._keyframe_times,
        )
        pack_options = {"side": tk.TOP, "fill": tk.X}
        if before is not None:
            pack_options["before"] = before
        panel.pack(**pack_options)
        panel.play_button.configure(command=self._play_flight_plan)
        self.flight_playback_panel = panel
        # Compatibility alias used by tests and future non-UI integrations.
        self.flight_plan_playback = panel.controller
        self._reload_playback_document()

    def _playback_document(self):
        if not self.flight_plan_session.valid:
            return None
        return self.flight_plan_session.build_document()

    def _reload_playback_document(self) -> None:
        panel = self.flight_playback_panel
        if panel is None:
            return
        try:
            playhead = float(self.flight_plan_session.playhead_time_text)
        except ValueError:
            playhead = 0.0
        panel.load(self._playback_document(), playhead_seconds=playhead)

    def _interactive_render_scale(self) -> float:
        panel = self.flight_playback_panel
        if panel is not None and panel.playing:
            return self.flight_scale_var.get()
        return super()._interactive_render_scale()

    @staticmethod
    def _format_playback_seconds(value: float) -> str:
        return f"{value:.2f}".replace(".", ",")

    def _apply_playback_sample(
        self, sample: PlaybackSample, status_prefix: str
    ) -> None:
        self._path_preview_frame = sample.frame
        self.camera = sample.frame.camera
        self.flight_plan_session.set_playhead(sample.frame.time_seconds_text)
        ending = " beendet" if sample.reached_end else ""
        self.position_var.set(
            f"{status_prefix}{ending} bei "
            f"{self._format_playback_seconds(sample.playhead_seconds)} s.\n"
            f"Breite: {sample.frame.camera.view_width_text}; "
            f"{sample.frame.render.max_iterations} Iter.; "
            f"{sample.frame.render.reference_bits} Bit; "
            f"Palette {sample.frame.render.palette.description}."
        )

    def _ensure_playback_document(self) -> bool:
        panel = self.flight_playback_panel
        document = self._playback_document()
        if panel is None or document is None:
            messagebox.showinfo(
                "Flugplan-Wiedergabe",
                "Der Flugplan muss mindestens zwei gültige Keyframes enthalten.",
                parent=self.root,
            )
            return False
        if panel.controller.document != document:
            try:
                playhead = float(self.flight_plan_session.playhead_time_text)
            except ValueError:
                playhead = 0.0
            panel.load(document, playhead_seconds=playhead)
        return True

    def _play_flight_plan(self) -> None:
        if not self._ensure_playback_document():
            return
        if self.flight_controller.running:
            self._stop_flight()
        assert self.flight_playback_panel is not None
        self.flight_playback_panel.play()

    def _play_flight_plan_from(self, time_seconds_text: str) -> None:
        if not self._ensure_playback_document():
            return
        if self.flight_controller.running:
            self._stop_flight()
        assert self.flight_playback_panel is not None
        self.flight_playback_panel.seek(float(time_seconds_text))
        self.flight_playback_panel.play()

    def _pause_flight_plan(self, *, request_render: bool = True) -> None:
        if self.flight_playback_panel is not None:
            self.flight_playback_panel.pause(request_render=request_render)

    def _stop_flight_plan(self, *, request_render: bool = True) -> None:
        if self.flight_playback_panel is not None:
            self.flight_playback_panel.stop(request_render=request_render)

    def _seek_flight_plan(self, value: str | float) -> None:
        panel = self.flight_playback_panel
        if panel is None or not panel.loaded:
            return
        try:
            panel.seek(float(value))
        except (TypeError, ValueError):
            return

    def _keyframe_times(self) -> tuple[float, ...]:
        path = self.flight_plan_session.camera_path
        if path is None:
            return ()
        return tuple(float(frame.time_seconds_text) for frame in path.keyframes)

    def _interrupt_plan_playback(self) -> None:
        if self.flight_playback_panel is not None:
            self.flight_playback_panel.interrupt()

    def _request(self, scale: float | None = None) -> RenderRequest:
        request = super()._request(scale)
        frame = self._path_preview_frame
        if frame is None:
            return request
        return frame.build_request(
            request,
            width=request.width,
            height=request.height,
        )

    def _render_palette(self):
        frame = self._path_preview_frame
        return frame.render.palette if frame is not None else super()._render_palette()

    def _render_cycles(self) -> float:
        frame = self._path_preview_frame
        return frame.render.cycles if frame is not None else super()._render_cycles()

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
        interrupt_playback = getattr(self, "_interrupt_plan_playback", None)
        if interrupt_playback is not None:
            interrupt_playback()
        if hasattr(self, "_path_preview_frame"):
            self._path_preview_frame = None
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
            session=self.flight_plan_session,
            get_aspect_ratio=lambda: max(1, self.canvas.winfo_width())
            / max(1, self.canvas.winfo_height()),
            on_play_from=self._play_flight_plan_from,
        )

    def _confirm_discard_flight_plan_changes(self, action: str) -> bool:
        if not self.flight_plan_session.dirty:
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
            document = load_flight_plan(
                path,
                migration_defaults=self._migration_defaults(),
            )
        except Exception as exc:
            messagebox.showerror("Flugplan öffnen", str(exc), parent=self.root)
            return False
        self._apply_document_primary_settings(document)
        self.flight_plan_session.set_document(document, file_path=path, dirty=False)
        migrated = "; Schema 1 wird beim nächsten Speichern auf Schema 2 aktualisiert" if document.source_schema_version == 1 else ""
        self.position_var.set(
            f"Flugplan {document.name} geladen: "
            f"{len(document.path.keyframes)} Keyframes, Dauer {document.path.duration_text} s; "
            f"{len(document.render_track.cues)} Render-Cues{migrated}."
        )
        return True

    def save_flight_plan(self) -> bool:
        if self.flight_plan_session.file_path is None:
            return self.save_flight_plan_as()
        return self._save_flight_plan_path(self.flight_plan_session.file_path)

    def save_flight_plan_as(self) -> bool:
        if self.flight_plan_session.camera_path is None:
            messagebox.showerror(
                "Flugplan speichern",
                "Der Flugplan muss mindestens zwei gültige Keyframes enthalten.",
                parent=self.root,
            )
            return False
        initial_name = (
            self.flight_plan_session.file_path.name
            if self.flight_plan_session.file_path is not None
            else f"{self.flight_plan_session.name}{FLIGHT_PLAN_EXTENSION}"
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
        return self._save_flight_plan_path(
            path,
            name=suggested_flight_plan_name(path),
        )

    def _save_flight_plan_path(self, path: Path, *, name: str | None = None) -> bool:
        if self.flight_plan_session.camera_path is None:
            messagebox.showerror(
                "Flugplan speichern",
                "Der Flugplan muss mindestens zwei gültige Keyframes enthalten.",
                parent=self.root,
            )
            return False
        try:
            document = self.flight_plan_session.build_document(name=name)
            save_flight_plan(path, document)
        except Exception as exc:
            messagebox.showerror("Flugplan speichern", str(exc), parent=self.root)
            return False
        self.flight_plan_session.mark_saved(path, name=document.name)
        self.position_var.set(f"Flugplan {document.name} gespeichert: {path}")
        return True

    def _export_flight_source(self):
        if not self.flight_plan_session.valid:
            return None
        return self.flight_plan_session.build_document()

    def _export_request(self) -> RenderRequest:
        # Export settings are evaluated from the complete flight document.  The
        # template contributes only technical settings and must not inherit a
        # transient single-time preview profile.
        return super()._request(1.0)

    def open_export_dialog(self) -> None:
        if self.export_dialog is not None and self.export_dialog.winfo_exists():
            self.export_dialog.deiconify()
            self.export_dialog.lift()
            self.export_dialog.focus_set()
            self.export_dialog.refresh_path_summary()
            return
        if self.flight_controller.running:
            self._stop_flight()
        if self.flight_plan_playback.playing:
            self._pause_flight_plan(request_render=False)
        self.export_dialog = FlightExportDialog(
            self.root,
            controller=self.export_controller,
            get_path=self._export_flight_source,
            build_request=self._export_request,
            get_renderer=lambda: select_renderer(self.backend_var.get()),
            get_palette=lambda: self.palette_var.get(),
            get_cycles=lambda: float(self.cycles_var.get()),
            ready_for_background_job=self._ready_for_export_job,
            on_job_finished=self.request_render,
        )

    def _ready_for_export_job(self) -> bool:
        if self.flight_controller.running:
            self._stop_flight()
        if self.flight_plan_playback.playing:
            self._pause_flight_plan(request_render=False)
        return not self.render_controller.busy

    def _preview_camera_path(self, camera: CameraState, time_seconds_text: str) -> None:
        del camera  # The complete plan is the source of truth for camera and render state.
        if self.flight_controller.running:
            self._stop_flight()
        if not self._ensure_playback_document():
            return
        assert self.flight_playback_panel is not None
        self.flight_playback_panel.preview(float(time_seconds_text))

    def _clear_path_preview(self) -> None:
        self._interrupt_plan_playback()
        self._path_preview_frame = None

    def _zoom_event(self, event: tk.Event, factor: float) -> None:
        self._clear_path_preview()
        super()._zoom_event(event, factor)

    def _drag_move(self, event: tk.Event) -> None:
        self._clear_path_preview()
        super()._drag_move(event)

    def _set_flight_target(self, event: tk.Event) -> None:
        self._clear_path_preview()
        super()._set_flight_target(event)

    def toggle_flight(self) -> None:
        self._clear_path_preview()
        super().toggle_flight()

    def reset_view(self) -> None:
        self._clear_path_preview()
        super().reset_view()

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
        if self.flight_playback_panel is not None:
            self.flight_playback_panel.close()
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
            panel = getattr(self, "flight_playback_panel", None)
            if panel is not None:
                panel.render_completed()
            return

        if self._should_check_flight_result(generation):
            visual = analyze_frame_visual_quality(result.rgb)
            if not visual.safe:
                self.render_controller.complete(generation)
                self._restore_last_good_flight_frame(visual=visual)
                self.request_render()
                panel = getattr(self, "flight_playback_panel", None)
                if panel is not None:
                    panel.render_completed()
                return
            self.flight_controller.accept(CameraState.from_request(request), result.rgb)

        super()._finish_render(future, generation, request)
        panel = getattr(self, "flight_playback_panel", None)
        if panel is not None:
            panel.render_completed()


def main() -> None:
    root = tk.Tk()
    app = FractalStudioApp(root)
    backends = ", ".join(available_renderers())
    app.status_var.set(f"Verfügbare Backends: {backends}\n{app.cuda_status.summary}")
    root.mainloop()


if __name__ == "__main__":
    main()
