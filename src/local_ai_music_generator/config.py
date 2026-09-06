from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

VoiceGender = Literal["male", "female"]
EngineName = Literal["auto", "mock", "yingmusic"]
OutputFormat = Literal["m4a", "mp3", "wav"]
CoverMode = Literal["auto", "surgical", "full"]

DEFAULT_OUTPUT_FORMAT: OutputFormat = "m4a"


def normalize_output_format(value: str | None) -> OutputFormat:
    """m4a = default (AAC, gute Qualität, kleine Datei). Auch mp3|wav."""
    raw = (value or DEFAULT_OUTPUT_FORMAT).strip().lower().lstrip(".")
    if raw in {"m4a", "aac", "mp4"}:
        return "m4a"
    if raw == "mp3":
        return "mp3"
    if raw == "wav":
        return "wav"
    raise ValueError(f"output_format muss m4a|mp3|wav sein (gefunden: {value!r})")


@dataclass
class Paths:
    """Project folder layout."""

    root: Path
    music_input: Path = field(init=False)
    music_output: Path = field(init=False)
    models: Path = field(init=False)
    work: Path = field(init=False)

    def __post_init__(self) -> None:
        self.root = self.root.resolve()
        self.music_input = self.root / "MUSIC_INPUT"
        self.music_output = self.root / "MUSIC_OUTPUT"
        self.models = self.root / "models"
        self.work = self.root / ".work"

    def ensure(self) -> None:
        for path in (self.music_input, self.music_output, self.models, self.work):
            path.mkdir(parents=True, exist_ok=True)


@dataclass
class GenerateRequest:
    audio: Path
    lyrics: Path
    output_name: str
    voice: VoiceGender = "female"
    original_lyrics: Path | None = None
    engine: EngineName = "auto"
    output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT
    apply_voice_gender: bool = False
    chunk_seconds: float = 20.0
    max_seconds: float | None = None
    nfe_step: int | None = None
    mode: CoverMode = "auto"
    polish: bool = True
    vocal_gain: float = 1.06
    instrumental_gain: float = 0.9
    reverb_mix: float | None = None  # None = auto from original wetness
    demucs_model: str = "htdemucs_ft"
    sample_rate: int = 44100
    keep_work_files: bool = False


def find_project_root(start: Path | None = None) -> Path:
    """Walk upward until MUSIC_INPUT + pyproject.toml (or src layout) is found."""
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / "MUSIC_INPUT").is_dir() and (
            (candidate / "pyproject.toml").is_file()
            or (candidate / "src" / "local_ai_music_generator").is_dir()
        ):
            return candidate
    return cur
