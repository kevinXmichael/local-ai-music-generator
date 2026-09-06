from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from local_ai_music_generator.config import VoiceGender

AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".aac", ".wma"}
LYRIC_EXTS = {".txt", ".srt", ".lrc"}

_SPACEY = re.compile(r"[\s_\-]+")


def _norm_stem(name: str) -> str:
    stem = Path(name).stem.lower().strip()
    return _SPACEY.sub(" ", stem)


@dataclass(frozen=True)
class InputJob:
    """One drop-folder job discovered under MUSIC_INPUT."""

    folder: Path
    audio: Path
    lyrics_new: Path
    lyrics_original: Path | None
    voice: VoiceGender
    output_name: str


class InputDiscoveryError(ValueError):
    """User-facing problem with MUSIC_INPUT layout."""


def discover_jobs(music_input: Path) -> list[InputJob]:
    """Find jobs from fixed filenames — no CLI flags needed.

    Layout A — files directly in MUSIC_INPUT::

        MUSIC_INPUT/
          song.m4a              # or audio.* / track.* / any single audio file
          lyrics new.txt
          lyrics original.txt   # optional but recommended
          voice.txt             # optional: male|female (default female)

    Layout B — one subfolder per song::

        MUSIC_INPUT/
          hot-mess/
            song.m4a
            lyrics new.txt
            lyrics original.txt
            voice.txt
    """
    music_input = music_input.resolve()
    if not music_input.is_dir():
        raise InputDiscoveryError(f"MUSIC_INPUT missing: {music_input}")

    jobs: list[InputJob] = []

    # Prefer explicit job subfolders (ignore samples/ docs / hidden)
    subdirs = [
        p
        for p in sorted(music_input.iterdir())
        if p.is_dir() and not p.name.startswith(".") and p.name.lower() not in {"samples"}
    ]
    for folder in subdirs:
        if _looks_like_job(folder):
            jobs.append(_job_from_folder(folder, output_fallback=folder.name))

    # Root-level job if files sit directly in MUSIC_INPUT
    if _looks_like_job(music_input):
        jobs.append(_job_from_folder(music_input, output_fallback="cover"))

    if not jobs:
        raise InputDiscoveryError(
            "Keine Inputs gefunden. Lege in MUSIC_INPUT ab:\n"
            "  song.m4a  (oder audio.*/track.*)\n"
            "  lyrics new.txt\n"
            "  lyrics original.txt  (empfohlen)\n"
            "  voice.txt            (optional: female|male)\n"
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
    voice = _read_voice(folder)
    output_name = _read_output_name(folder) or audio.stem or output_fallback
    return InputJob(
        folder=folder,
        audio=audio,
        lyrics_new=lyrics_new,
        lyrics_original=lyrics_original,
        voice=voice,
        output_name=output_name,
    )


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


def _read_voice(folder: Path) -> VoiceGender:
    path = _find_by_aliases(folder, {"voice", "gender", "stimme"}, {".txt", ".cfg", ".ini"})
    if not path:
        return "female"
    raw = path.read_text(encoding="utf-8").strip().splitlines()
    value = (raw[0] if raw else "").strip().lower()
    if value not in {"male", "female"}:
        raise InputDiscoveryError(
            f"{path.name} muss 'male' oder 'female' enthalten (gefunden: {value!r})"
        )
    return value  # type: ignore[return-value]


def _read_output_name(folder: Path) -> str | None:
    path = _find_by_aliases(
        folder,
        {"output name", "output", "name", "titel", "title"},
        {".txt"},
    )
    if not path:
        return None
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return lines[0] if lines else None
