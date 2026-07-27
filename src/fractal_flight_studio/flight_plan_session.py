from __future__ import annotations

from pathlib import Path
from typing import Callable

from .camera import CameraState
from .flight_path import CameraPath, CenterInterpolation, Easing
from .flight_plan import (
    FlightPlanDocument,
    FlightScene,
    RenderProfile,
    RenderTrack,
)
from .path_editor import CameraPathDraft


SessionListener = Callable[["FlightPlanSession"], None]


class FlightPlanSession:
    """Tk-independent mutable owner of one editable flight-plan document."""

    def __init__(
        self,
        *,
        camera_draft: CameraPathDraft,
        scene: FlightScene = FlightScene(),
        render_track: RenderTrack | None = None,
        name: str = "Unbenannter Flugplan",
        file_path: Path | None = None,
        dirty: bool = False,
    ) -> None:
        self._camera_draft = camera_draft
        self._scene = scene
        self._render_track = render_track or RenderTrack.default(digits=camera_draft.digits)
        if self._render_track.digits != camera_draft.digits:
            raise ValueError("camera draft and render track must use the same precision")
        self._name = name
        self._file_path = file_path
        self._dirty = bool(dirty)
        self._selected_keyframe_index: int | None = None
        self._playhead_time_text = "0"
        self._listeners: list[SessionListener] = []
        self._validated_document_name()

    @classmethod
    def new(
        cls,
        camera: CameraState,
        *,
        digits: int,
        scene: FlightScene = FlightScene(),
        render_profile: RenderProfile = RenderProfile(),
        name: str = "Unbenannter Flugplan",
    ) -> "FlightPlanSession":
        draft = CameraPathDraft(digits=digits).add_keyframe(
            "0",
            camera,
            Easing.SMOOTHSTEP,
            CenterInterpolation.FOCUS,
        )
        return cls(
            camera_draft=draft,
            scene=scene,
            render_track=RenderTrack.default(render_profile, digits=digits),
            name=name,
        )

    @property
    def camera_draft(self) -> CameraPathDraft:
        return self._camera_draft

    @property
    def camera_path(self) -> CameraPath | None:
        if not self._camera_draft.valid:
            return None
        return self._camera_draft.build_path()

    @property
    def scene(self) -> FlightScene:
        return self._scene

    @property
    def render_track(self) -> RenderTrack:
        return self._render_track

    @property
    def name(self) -> str:
        return self._name

    @property
    def file_path(self) -> Path | None:
        return self._file_path

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def selected_keyframe_index(self) -> int | None:
        return self._selected_keyframe_index

    @property
    def playhead_time_text(self) -> str:
        return self._playhead_time_text

    @property
    def validation_error(self) -> str | None:
        error = self._camera_draft.validation_error
        if error is not None:
            return error
        try:
            self.build_document()
        except ValueError as exc:
            return str(exc)
        return None

    @property
    def valid(self) -> bool:
        return self.validation_error is None

    def build_document(self, *, name: str | None = None) -> FlightPlanDocument:
        path = self._camera_draft.build_path()
        return FlightPlanDocument(
            self._name if name is None else name,
            path,
            self._scene,
            self._render_track,
        )

    def add_listener(self, listener: SessionListener, *, notify: bool = False) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)
        if notify:
            listener(self)

    def remove_listener(self, listener: SessionListener) -> None:
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass

    def set_camera_draft(self, draft: CameraPathDraft, *, mark_dirty: bool = True) -> None:
        if draft.digits != self._render_track.digits:
            raise ValueError("camera draft and render track must use the same precision")
        if draft == self._camera_draft:
            return
        self._camera_draft = draft
        self._selected_keyframe_index = _bounded_selection(
            self._selected_keyframe_index,
            len(draft.keyframes),
        )
        if mark_dirty:
            self._dirty = True
        self._notify()

    def set_camera_path(self, path: CameraPath, *, mark_dirty: bool = True) -> None:
        render_track = self._render_track
        if render_track.digits != path.digits:
            render_track = RenderTrack(render_track.cues, digits=path.digits)
            self._render_track = render_track
        self.set_camera_draft(CameraPathDraft.from_path(path), mark_dirty=mark_dirty)

    def set_document(
        self,
        document: FlightPlanDocument,
        *,
        file_path: Path | None = None,
        dirty: bool = False,
    ) -> None:
        self._camera_draft = CameraPathDraft.from_path(document.path)
        self._scene = document.scene
        self._render_track = document.render_track
        self._name = document.name
        self._file_path = file_path
        self._dirty = bool(dirty)
        self._selected_keyframe_index = 0
        self._playhead_time_text = "0"
        self._notify()

    def set_name(self, name: str, *, mark_dirty: bool = True) -> None:
        if name == self._name:
            return
        original = self._name
        self._name = name
        try:
            self._validated_document_name()
        except Exception:
            self._name = original
            raise
        if mark_dirty:
            self._dirty = True
        self._notify()

    def set_scene(self, scene: FlightScene, *, mark_dirty: bool = True) -> None:
        if scene == self._scene:
            return
        self._scene = scene
        if mark_dirty:
            self._dirty = True
        self._notify()

    def set_render_track(self, track: RenderTrack, *, mark_dirty: bool = True) -> None:
        if track.digits != self._camera_draft.digits:
            raise ValueError("camera draft and render track must use the same precision")
        if track == self._render_track:
            return
        self._render_track = track
        if mark_dirty:
            self._dirty = True
        self._notify()

    def sync_primary_settings(
        self,
        scene: FlightScene,
        profile: RenderProfile,
        *,
        mark_dirty: bool = True,
    ) -> None:
        track = self._render_track.replace_first_profile(profile)
        if scene == self._scene and track == self._render_track:
            return
        self._scene = scene
        self._render_track = track
        if mark_dirty:
            self._dirty = True
        self._notify()

    def set_selected_keyframe(self, index: int | None) -> None:
        bounded = _bounded_selection(index, len(self._camera_draft.keyframes))
        if bounded == self._selected_keyframe_index:
            return
        self._selected_keyframe_index = bounded
        self._notify()

    def set_playhead(self, time_seconds_text: str) -> None:
        if time_seconds_text == self._playhead_time_text:
            return
        path = self.camera_path
        if path is not None:
            path.evaluate(time_seconds_text)
        self._playhead_time_text = time_seconds_text
        self._notify()

    def mark_saved(self, file_path: Path, *, name: str | None = None) -> None:
        if name is not None:
            document = self.build_document(name=name)
            self._name = document.name
        else:
            self.build_document()
        self._file_path = file_path
        self._dirty = False
        self._notify()

    def mark_dirty(self) -> None:
        if self._dirty:
            return
        self._dirty = True
        self._notify()

    def _validated_document_name(self) -> None:
        if not isinstance(self._name, str):
            raise ValueError("flight-plan name must be a string")
        normalized = self._name.strip()
        if not normalized:
            raise ValueError("flight-plan name must not be empty")
        if len(normalized) > 200:
            raise ValueError("flight-plan name must not exceed 200 characters")
        if any(ord(character) < 32 for character in normalized):
            raise ValueError("flight-plan name must not contain control characters")
        self._name = normalized
        path = self.camera_path
        if path is not None:
            FlightPlanDocument(
                self._name,
                path,
                self._scene,
                self._render_track,
            )

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener(self)



def _bounded_selection(index: int | None, length: int) -> int | None:
    if index is None or length <= 0:
        return None
    return min(max(int(index), 0), length - 1)
