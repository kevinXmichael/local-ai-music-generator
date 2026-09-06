from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from local_ai_music_generator.audio_io import load_audio, mix_tracks, save_audio
from local_ai_music_generator.config import GenerateRequest, Paths
from local_ai_music_generator.engines.mock_engine import MockLyricCoverEngine
from local_ai_music_generator.engines.separator import get_separator
from local_ai_music_generator.engines.yingmusic import YingMusicCoverEngine
from local_ai_music_generator.lyrics import load_lyrics

console = Console()

_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")


@dataclass
class GenerateResult:
    output_path: Path
    engine: str
    notes: str
    work_dir: Path


def sanitize_output_name(name: str) -> str:
    name = name.strip().replace(" ", "-")
    name = _SAFE_NAME.sub("-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-._")
    return name or "cover"


def resolve_engine(name: str):
    if name == "mock":
        return MockLyricCoverEngine()
    if name == "yingmusic":
        engine = YingMusicCoverEngine()
        if not engine.available():
            raise RuntimeError(
                "Engine 'yingmusic' requested but not installed. "
                "Run: python -m local_ai_music_generator setup-yingmusic"
            )
        return engine
    # auto
    ym = YingMusicCoverEngine()
    if ym.available():
        return ym
    console.print(
        "[yellow]YingMusic not found — falling back to mock engine. "
        "Run setup-yingmusic for real lyric re-singing.[/yellow]"
    )
    return MockLyricCoverEngine()


def generate(paths: Paths, request: GenerateRequest) -> GenerateResult:
    paths.ensure()
    output_name = sanitize_output_name(request.output_name)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    work_dir = paths.work / f"{output_name}-{stamp}"
    work_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Loading audio[/bold] {request.audio}")
    audio, sr = load_audio(request.audio, sample_rate=request.sample_rate)
    save_audio(work_dir / "input.wav", audio, sr)

    target = load_lyrics(request.lyrics)
    if request.original_lyrics:
        original = load_lyrics(request.original_lyrics)
    else:
        original = target
        console.print(
            "[yellow]No --original-lyrics given; using target lyrics as reference "
            "(best results need the originally sung text).[/yellow]"
        )

    (work_dir / "target_lyrics.txt").write_text(target.text, encoding="utf-8")
    (work_dir / "original_lyrics.txt").write_text(original.text, encoding="utf-8")

    prefer_demucs = request.engine != "mock"
    separator = get_separator(prefer_demucs=prefer_demucs)
    console.print(f"[bold]Separating[/bold] with {separator.name}")
    separation = separator.separate(audio, sr, work_dir / "separate")
    save_audio(work_dir / "vocals_template.wav", separation.vocals, separation.sample_rate)
    save_audio(
        work_dir / "instrumental.wav",
        separation.instrumental,
        separation.sample_rate,
    )

    engine = resolve_engine(request.engine)
    console.print(f"[bold]Cover engine[/bold] {engine.name} · voice={request.voice}")
    cover = engine.cover(
        vocals=separation.vocals,
        sample_rate=separation.sample_rate,
        original_lyrics=original,
        target_lyrics=target,
        voice=request.voice,
        work_dir=work_dir / "cover",
    )
    save_audio(work_dir / "vocals_new.wav", cover.vocals, cover.sample_rate)

    mixed = mix_tracks(cover.vocals, separation.instrumental)
    out_path = paths.music_output / f"{output_name}.wav"
    save_audio(out_path, mixed, cover.sample_rate)

    meta = {
        "output": str(out_path),
        "audio": str(request.audio),
        "lyrics": str(request.lyrics),
        "original_lyrics": str(request.original_lyrics) if request.original_lyrics else None,
        "voice": request.voice,
        "engine": cover.engine,
        "separator": separator.name,
        "notes": cover.notes,
        "created_utc": stamp,
    }
    (work_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (paths.music_output / f"{output_name}.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    if request.keep_work_files:
        console.print(f"Work files kept at {work_dir}")

    console.print(f"[green]Wrote[/green] {out_path}")
    if cover.notes:
        console.print(f"[dim]{cover.notes}[/dim]")

    return GenerateResult(
        output_path=out_path,
        engine=cover.engine,
        notes=cover.notes,
        work_dir=work_dir,
    )


def cleanup_work(work_dir: Path) -> None:
    if work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
