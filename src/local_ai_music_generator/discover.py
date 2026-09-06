from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from local_ai_music_generator.config import (
    CoverMode,
    OutputFormat,
    VoiceGender,
    normalize_output_format,
)

AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".aac", ".wma"}
LYRIC_EXTS = {".txt", ".srt", ".lrc"}

_SPACEY = re.compile(r"[\s_\-]+")
_SETTINGS_NAMES = {"settings", "config", "job"}


def _norm_stem(name: str) -> str:
    stem = Path(name).stem.lower().strip()
    return _SPACEY.sub(" ", stem)


@dataclass(frozen=True)
class JobSettings:
    """Per-job settings from settings.json (extensible)."""

    voice: VoiceGender = "female"
    output_name: str | None = None
    output_format: OutputFormat = "m4a"
    apply_voice_gender: bool = False
    chunk_seconds: float = 20.0
    max_seconds: float | None = None
    nfe_step: int | None = None
    mode: CoverMode = "auto"
    polish: bool = True
    vocal_gain: float = 1.06
    instrumental_gain: float = 0.9
    reverb_mix: float | None = None
    demucs_model: str = "htdemucs_ft"
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class InputJob:
    """One drop-folder job discovered under MUSIC_INPUT."""

    folder: Path
    audio: Path
    lyrics_new: Path
    lyrics_original: Path | None
    settings: JobSettings

    @property
    def voice(self) -> VoiceGender:
        return self.settings.voice

    @property
    def output_name(self) -> str:
        return self.settings.output_name or self.audio.stem or self.folder.name or "cover"

    @property
    def output_format(self) -> OutputFormat:
        return self.settings.output_format

    @property
    def apply_voice_gender(self) -> bool:
        return self.settings.apply_voice_gender

    @property
    def chunk_seconds(self) -> float:
        return self.settings.chunk_seconds

    @property
    def max_seconds(self) -> float | None:
        return self.settings.max_seconds

    @property
    def nfe_step(self) -> int | None:
        return self.settings.nfe_step

    @property
    def mode(self) -> CoverMode:
        return self.settings.mode

    @property
    def polish(self) -> bool:
        return self.settings.polish

    @property
    def vocal_gain(self) -> float:
        return self.settings.vocal_gain

    @property
    def instrumental_gain(self) -> float:
        return self.settings.instrumental_gain

    @property
    def reverb_mix(self) -> float | None:
        return self.settings.reverb_mix

    @property
    def demucs_model(self) -> str:
        return self.settings.demucs_model


class InputDiscoveryError(ValueError):
    """User-facing problem with MUSIC_INPUT layout."""


def discover_jobs(music_input: Path) -> list[InputJob]:
    """Find jobs from fixed filenames — no CLI flags needed.

    Layout::

        MUSIC_INPUT/hot-mess/
          song.m4a
          lyrics new.txt
          lyrics original.txt
          settings.json     # voice, output_name, output_format, …
    """
    music_input = music_input.resolve()
    if not music_input.is_dir():
        raise InputDiscoveryError(f"MUSIC_INPUT missing: {music_input}")

    jobs: list[InputJob] = []

    subdirs = [
        p
        for p in sorted(music_input.iterdir())
        if p.is_dir() and not p.name.startswith(".") and p.name.lower() not in {"samples"}
    ]
    for folder in subdirs:
        if _looks_like_job(folder):
            jobs.append(_job_from_folder(folder, output_fallback=folder.name))

    if _looks_like_job(music_input):
        jobs.append(_job_from_folder(music_input, output_fallback="cover"))

    if not jobs:
        raise InputDiscoveryError(
            "Keine Inputs gefunden. Lege in MUSIC_INPUT ab:\n"
            "  song.m4a  (oder audio.*/track.*)\n"
            "  lyrics new.txt\n"
            "  lyrics original.txt  (empfohlen)\n"
            "  settings.json        (optional: voice, output_name, output_format)\n"
            "Oder dasselbe in einem Unterordner, z.B. MUSIC_INPUT/mein-song/"
        )
    return jobs


def _looks_like_job(folder: Path) -> bool:
    try:
        _find_lyrics_new(folder)
        _find_audio(folder)
        return True
    except InputDiscoveryError:
        return False


def _job_from_folder(folder: Path, *, output_fallback: str) -> InputJob:
    audio = _find_audio(folder)
    lyrics_new = _find_lyrics_new(folder)
    lyrics_original = _find_lyrics_original(folder)
    settings = load_settings(folder, output_fallback=output_fallback, audio_stem=audio.stem)
    return InputJob(
        folder=folder,
        audio=audio,
        lyrics_new=lyrics_new,
        lyrics_original=lyrics_original,
        settings=settings,
    )


def load_settings(
    folder: Path,
    *,
    output_fallback: str,
    audio_stem: str,
) -> JobSettings:
    path = _find_settings_file(folder)
    raw: dict[str, Any] = {}
    if path is not None:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise InputDiscoveryError(f"Ungültiges JSON in {path}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise InputDiscoveryError(f"{path.name} muss ein JSON-Objekt sein")
        raw = loaded

    voice = str(raw.get("voice", "female")).strip().lower()
    if voice not in {"male", "female"}:
        raise InputDiscoveryError(
            f"settings.json voice muss 'male' oder 'female' sein (gefunden: {voice!r})"
        )

    output_name = raw.get("output_name")
    if output_name is not None:
        output_name = str(output_name).strip() or None
    if not output_name:
        output_name = audio_stem or output_fallback

    try:
        output_format = normalize_output_format(raw.get("output_format", "m4a"))
    except ValueError as exc:
        raise InputDiscoveryError(str(exc)) from exc

    apply_voice_gender = bool(raw.get("apply_voice_gender", False))

    chunk_seconds = float(raw.get("chunk_seconds", 20))
    if chunk_seconds < 0:
        raise InputDiscoveryError("chunk_seconds muss >= 0 sein (0 = ein Stück)")

    max_seconds_raw = raw.get("max_seconds")
    max_seconds: float | None
    if max_seconds_raw is None or max_seconds_raw == "":
        max_seconds = None
    else:
        max_seconds = float(max_seconds_raw)
        if max_seconds <= 0:
            max_seconds = None

    nfe_raw = raw.get("nfe_step")
    nfe_step = int(nfe_raw) if nfe_raw is not None else None

    mode_raw = str(raw.get("mode", "auto")).strip().lower()
    if mode_raw not in {"auto", "surgical", "full"}:
        raise InputDiscoveryError("mode muss auto|surgical|full sein")
    mode: CoverMode = mode_raw  # type: ignore[assignment]

    polish = bool(raw.get("polish", True))
    vocal_gain = float(raw.get("vocal_gain", 1.06))
    instrumental_gain = float(raw.get("instrumental_gain", 0.9))
    if vocal_gain <= 0 or instrumental_gain <= 0:
        raise InputDiscoveryError("vocal_gain / instrumental_gain müssen > 0 sein")

    reverb_raw = raw.get("reverb_mix", None)
    reverb_mix: float | None
    if reverb_raw is None or reverb_raw == "" or reverb_raw == "auto":
        reverb_mix = None
    else:
        reverb_mix = float(reverb_raw)
        if not 0.0 <= reverb_mix <= 0.45:
            raise InputDiscoveryError("reverb_mix muss zwischen 0 und 0.45 liegen (oder auto)")

    demucs_model = str(raw.get("demucs_model", "htdemucs_ft")).strip() or "htdemucs_ft"

    known = {
        "voice",
        "output_name",
        "output_format",
        "apply_voice_gender",
        "chunk_seconds",
        "max_seconds",
        "nfe_step",
        "mode",
        "polish",
        "vocal_gain",
        "instrumental_gain",
        "reverb_mix",
        "demucs_model",
    }
    extra = {k: v for k, v in raw.items() if k not in known}

    return JobSettings(
        voice=voice,  # type: ignore[arg-type]
        output_name=output_name,
        output_format=output_format,
        apply_voice_gender=apply_voice_gender,
        chunk_seconds=chunk_seconds,
        max_seconds=max_seconds,
        nfe_step=nfe_step,
        mode=mode,
        polish=polish,
        vocal_gain=vocal_gain,
        instrumental_gain=instrumental_gain,
        reverb_mix=reverb_mix,
        demucs_model=demucs_model,
        extra=extra or None,
    )


def _find_settings_file(folder: Path) -> Path | None:
    for path in _iter_files(folder):
        if path.suffix.lower() != ".json":
            continue
        if _norm_stem(path.name) in _SETTINGS_NAMES:
            return path
    return None


def _iter_files(folder: Path) -> list[Path]:
    return [p for p in folder.iterdir() if p.is_file() and not p.name.startswith(".")]


def _find_by_aliases(folder: Path, aliases: set[str], exts: set[str]) -> Path | None:
    files = _iter_files(folder)
    for path in files:
        if path.suffix.lower() not in exts:
            continue
        if _norm_stem(path.name) in aliases:
            return path
    return None


def _find_audio(folder: Path) -> Path:
    preferred = _find_by_aliases(
        folder,
        {"song", "audio", "track", "input", "music", "source"},
        AUDIO_EXTS,
    )
    if preferred:
        return preferred

    audio_files = [p for p in _iter_files(folder) if p.suffix.lower() in AUDIO_EXTS]
    if len(audio_files) == 1:
        return audio_files[0]
    if not audio_files:
        raise InputDiscoveryError(
            f"Kein Audio in {folder}. Erwarte z.B. song.m4a / audio.mp3"
        )
    raise InputDiscoveryError(
        f"Mehrere Audio-Dateien in {folder}. Benenne die Vorlage `song.*` "
        f"(gefunden: {', '.join(p.name for p in audio_files)})"
    )


def _find_lyrics_new(folder: Path) -> Path:
    path = _find_by_aliases(
        folder,
        {
            "lyrics new",
            "lyricsnew",
            "new lyrics",
            "lyrics target",
            "target lyrics",
            "lyrics",
        },
        LYRIC_EXTS,
    )
    if path:
        return path
    raise InputDiscoveryError(
        f"Fehlt `lyrics new.txt` (oder lyrics_new / new lyrics) in {folder}"
    )


def _find_lyrics_original(folder: Path) -> Path | None:
    return _find_by_aliases(
        folder,
        {
            "lyrics original",
            "lyricsoriginal",
            "original lyrics",
            "lyrics source",
            "source lyrics",
            "lyrics old",
            "old lyrics",
        },
        LYRIC_EXTS,
    )
