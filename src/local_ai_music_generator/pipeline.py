from __future__ import annotations

import json
import re
import shutil
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from local_ai_music_generator.audio_io import load_audio, mix_tracks, save_audio
from local_ai_music_generator.cleanup import cleanup_caches, format_bytes
from local_ai_music_generator.config import GenerateRequest, Paths
from local_ai_music_generator.engines.base import CoverResult
from local_ai_music_generator.engines.mock_engine import MockLyricCoverEngine
from local_ai_music_generator.engines.separator import get_separator
from local_ai_music_generator.engines.yingmusic import YingMusicCoverEngine
from local_ai_music_generator.lyrics import load_lyrics
from local_ai_music_generator.lyrics_diff import should_use_surgical
from local_ai_music_generator.polish import polish_vocals, studio_mix
from local_ai_music_generator.surgical import surgical_cover

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


class EngineNotReadyError(RuntimeError):
    """Raised when auto/yingmusic is requested but YingMusic is missing."""


def resolve_engine(name: str):
    if name == "mock":
        return MockLyricCoverEngine()
    if name in {"auto", "yingmusic"}:
        engine = YingMusicCoverEngine()
        if engine.available():
            return engine
        raise EngineNotReadyError(
            "YingMusic ist nicht installiert — ohne das werden Lyrics NICHT neu gesungen "
            "und der Sound bleibt schlecht (alter Mock-Pfad).\n\n"
            "Einmalig einrichten:\n"
            "  ./scripts/generate.sh setup-yingmusic\n\n"
            "Nur Pipeline testen (ändert keine Lyrics):\n"
            "  ./scripts/generate.sh --engine mock"
        )
    raise ValueError(f"Unknown engine: {name}")


def generate(paths: Paths, request: GenerateRequest) -> GenerateResult:
    paths.ensure()
    cleaned = cleanup_caches(paths.root, keep_work=2, delete_unused_hf=True, dry_run=False)
    if cleaned.freed_bytes > 0:
        console.print(
            f"[dim]cleanup[/dim] freigegeben {format_bytes(cleaned.freed_bytes)} "
            f"({len(cleaned.removed)} Altlasten)"
        )

    output_name = sanitize_output_name(request.output_name)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    work_dir = paths.work / f"{output_name}-{stamp}"
    work_dir.mkdir(parents=True, exist_ok=True)

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)
        warnings.filterwarnings("ignore", category=RuntimeWarning)

        console.print(f"[bold]Loading audio[/bold] {request.audio}")
        audio, sr = load_audio(request.audio, sample_rate=request.sample_rate)
        save_audio(work_dir / "input.wav", audio, sr)

        target = load_lyrics(request.lyrics)
        if request.original_lyrics:
            original = load_lyrics(request.original_lyrics)
        else:
            original = target
            console.print(
                "[yellow]Kein lyrics original — Target wird auch als Referenz genutzt.[/yellow]"
            )

        (work_dir / "target_lyrics.txt").write_text(target.text, encoding="utf-8")
        (work_dir / "original_lyrics.txt").write_text(original.text, encoding="utf-8")

        engine = resolve_engine(request.engine)
        prefer_demucs = engine.name != "mock"
        separator = get_separator(
            prefer_demucs=prefer_demucs,
            demucs_model=request.demucs_model,
        )
        console.print(
            f"[bold]Separating[/bold] with {separator.name}"
            + (f" ({getattr(separator, 'model', '')})" if prefer_demucs else "")
        )
        separation = separator.separate(audio, sr, work_dir / "separate")
        save_audio(work_dir / "vocals_template.wav", separation.vocals, separation.sample_rate)
        save_audio(
            work_dir / "instrumental.wav",
            separation.instrumental,
            separation.sample_rate,
        )

        use_surgical = False
        if engine.name == "yingmusic":
            if request.mode == "surgical":
                use_surgical = True
            elif request.mode == "full":
                use_surgical = False
            else:
                use_surgical = should_use_surgical(original, target)

        if use_surgical and isinstance(engine, YingMusicCoverEngine):
            console.print(
                "[bold]Mode surgical[/bold] — Originalstimme bleibt, "
                "nur geänderte Wörter/Phrasen werden neu gesungen"
            )
            nfe = request.nfe_step if request.nfe_step is not None else 28
            vocals_new, notes = surgical_cover(
                engine=engine,
                vocals=separation.vocals,
                sample_rate=separation.sample_rate,
                original_lyrics=original,
                target_lyrics=target,
                work_dir=work_dir / "surgical",
                nfe_step=nfe,
            )
            cover = CoverResult(
                vocals=vocals_new,
                sample_rate=separation.sample_rate,
                engine="yingmusic-surgical",
                notes=notes,
            )
        else:
            console.print(f"[bold]Cover engine[/bold] {engine.name} · voice={request.voice}")
            if engine.name == "yingmusic":
                dur = len(audio) / float(sr)
                console.print(
                    f"[dim]Song ~{dur:.0f}s — full/chunked resynthesis "
                    "(Stimme wird neu generiert).[/dim]"
                )
            cover_kwargs: dict = {
                "vocals": separation.vocals,
                "sample_rate": separation.sample_rate,
                "original_lyrics": original,
                "target_lyrics": target,
                "voice": request.voice,
                "work_dir": work_dir / "cover",
                "apply_gender": request.apply_voice_gender,
                "source_mix": None,
            }
            if engine.name == "yingmusic":
                cover_kwargs["chunk_seconds"] = request.chunk_seconds
                cover_kwargs["max_seconds"] = request.max_seconds
                if request.nfe_step is not None:
                    cover_kwargs["nfe_step"] = request.nfe_step
            cover = engine.cover(**cover_kwargs)

        vocals_out = cover.vocals
        polish_note = ""
        if request.polish and engine.name != "mock":
            console.print(
                "[bold]Studio polish[/bold] — Timbre-Glue, Kompression, "
                "Presence, Reverb, Cover-Mix (lokal)"
            )
            vocals_out = polish_vocals(
                vocals_out,
                sample_rate=cover.sample_rate,
                reference=separation.vocals,
                reverb_mix=request.reverb_mix,
            )
            polish_note = " + studio polish"
            save_audio(work_dir / "vocals_polished.wav", vocals_out, cover.sample_rate)

        save_audio(work_dir / "vocals_new.wav", cover.vocals, cover.sample_rate)

        if cover.already_mixed:
            mixed = vocals_out
        elif request.polish and engine.name != "mock":
            mixed = studio_mix(
                vocals_out,
                separation.instrumental,
                vocal_gain=request.vocal_gain,
                instrumental_gain=request.instrumental_gain,
            )
        else:
            mixed = mix_tracks(vocals_out, separation.instrumental)

        ext = f".{request.output_format}"
        out_path = paths.music_output / f"{output_name}{ext}"
        saved = save_audio(out_path, mixed, cover.sample_rate)

    notes = f"{cover.notes}{polish_note}".strip()
    meta = {
        "output": str(saved),
        "audio": str(request.audio),
        "lyrics": str(request.lyrics),
        "original_lyrics": str(request.original_lyrics) if request.original_lyrics else None,
        "voice": request.voice,
        "output_format": request.output_format,
        "mode": request.mode,
        "polish": request.polish,
        "engine": cover.engine,
        "separator": separator.name,
        "demucs_model": getattr(separator, "model", None),
        "notes": notes,
        "created_utc": stamp,
    }
    (work_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (paths.music_output / f"{output_name}.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    if request.keep_work_files:
        console.print(f"Work files kept at {work_dir}")

    console.print(f"[green]Wrote[/green] {saved}")
    if notes:
        console.print(f"[dim]{notes}[/dim]")

    return GenerateResult(
        output_path=saved,
        engine=cover.engine,
        notes=notes,
        work_dir=work_dir,
    )


def cleanup_work(work_dir: Path) -> None:
    if work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
