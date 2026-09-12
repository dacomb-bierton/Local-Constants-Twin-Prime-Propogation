"""Pydantic models shared by the API, the exporter and the tests."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

CAMERAS = ["front", "back", "left_repeater", "right_repeater", "left_pillar", "right_pillar"]
CAMERA_LABELS = {
    "front": "Front",
    "back": "Rear",
    "left_repeater": "Left Repeater",
    "right_repeater": "Right Repeater",
    "left_pillar": "Left Pillar",
    "right_pillar": "Right Pillar",
}

Camera = Literal["front", "back", "left_repeater", "right_repeater", "left_pillar", "right_pillar"]
LayoutName = Literal["single", "grid", "pip", "side", "cinematic", "three_wide"]
FitMode = Literal["cover", "contain"]

ASPECT_PRESETS: dict[str, tuple[int, int]] = {
    "16:9": (16, 9),
    "9:16": (9, 16),
    "1:1": (1, 1),
    "4:3": (4, 3),
    "3:4": (3, 4),
    "21:9": (21, 9),
    "4:5": (4, 5),
    "5:4": (5, 4),
    "2:1": (2, 1),
}


class Segment(BaseModel):
    """One minute (usually) of footage starting at `start`, with one file per camera."""

    start: str  # "YYYY-MM-DD_HH-MM-SS"
    start_epoch: float
    duration: float = 60.0
    files: dict[str, str]  # camera -> absolute path


class EventInfo(BaseModel):
    id: str
    kind: Literal["SavedClips", "SentryClips", "RecentClips"]
    folder: str
    title: str
    start: str
    start_epoch: float
    duration: float
    cameras: list[str]
    segment_count: int
    reason: Optional[str] = None
    reason_label: Optional[str] = None
    city: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    trigger_epoch: Optional[float] = None
    trigger_offset: Optional[float] = None  # seconds into the event timeline
    trigger_camera: Optional[str] = None
    has_thumb: bool = False
    size_bytes: int = 0


class EventDetail(EventInfo):
    segments: list[Segment]


class BlurRegion(BaseModel):
    """Normalised (0..1) rectangle on the output canvas that is blurred."""

    x: float
    y: float
    w: float
    h: float


class SequenceItem(BaseModel):
    id: str
    event_id: str
    in_point: float = 0.0  # seconds into the event timeline
    out_point: float  # seconds into the event timeline
    cameras: list[str] = Field(default_factory=lambda: ["front"])
    layout: LayoutName = "single"
    main_camera: str = "front"
    fit: FitMode = "cover"
    speed: float = 1.0
    cycle_enabled: bool = False
    cycle_interval: float = 5.0
    cycle_cameras: list[str] = Field(default_factory=list)  # empty -> use `cameras`
    mirror_rear: bool = False  # flip back/repeaters/pillars horizontally so they read like mirrors
    show_timestamp: bool = True
    show_labels: bool = False
    show_location: bool = False
    blur_regions: list[BlurRegion] = Field(default_factory=list)


class MusicTrack(BaseModel):
    path: str
    name: str = ""
    offset: float = 0.0  # seconds into the music file where playback starts
    volume: float = 1.0  # linear gain (1.0 = unchanged)
    fade_in: float = 1.0
    fade_out: float = 2.0
    loop: bool = True
    video_offset: float = 0.0  # seconds into the video where the music starts


class ExportSettings(BaseModel):
    aspect: str = "16:9"
    resolution: int = 1080  # length of the *short* side of the canvas
    fps: int = 30
    quality: Literal["draft", "standard", "high"] = "standard"
    format: Literal["mp4", "gif"] = "mp4"
    encoder: Literal["auto", "libx264", "h264_nvenc", "h264_amf", "h264_qsv"] = "auto"
    background: str = "#000000"
    watermark_path: Optional[str] = None
    watermark_opacity: float = 0.7
    watermark_scale: float = 0.15  # fraction of canvas width
    watermark_position: Literal["tl", "tr", "bl", "br"] = "br"
    output_dir: Optional[str] = None
    filename: Optional[str] = None


class Project(BaseModel):
    name: str = "Untitled"
    library_root: Optional[str] = None
    items: list[SequenceItem] = Field(default_factory=list)
    music: Optional[MusicTrack] = None
    export: ExportSettings = Field(default_factory=ExportSettings)


class ExportRequest(BaseModel):
    project: Project


class StillRequest(BaseModel):
    event_id: str
    time: float
    cameras: list[str]
    layout: LayoutName = "single"
    main_camera: str = "front"
    aspect: str = "16:9"
    resolution: int = 1080
    fit: FitMode = "cover"
    mirror_rear: bool = False
    show_timestamp: bool = True
    output_dir: Optional[str] = None


class JobStatus(BaseModel):
    id: str
    kind: str
    state: Literal["queued", "running", "done", "error", "cancelled"]
    progress: float = 0.0
    message: str = ""
    output: Optional[str] = None
    error: Optional[str] = None
