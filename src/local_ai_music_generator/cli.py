from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from local_ai_music_generator import __version__
from local_ai_music_generator.cleanup import cleanup_caches, format_bytes
from local_ai_music_generator.config import GenerateRequest, Paths, find_project_root
from local_ai_music_generator.discover import InputDiscoveryError, discover_jobs
from local_ai_music_generator.engines.yingmusic import YingMusicCoverEngine, setup_yingmusic
from local_ai_music_generator.pipeline import EngineNotReadyError, generate, sanitize_output_name

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    no_args_is_help=False,
    help="Dateien in MUSIC_INPUT legen → Cover in MUSIC_OUTPUT.",
)
console = Console()


@app.callback()
def _root(
    ctx: typer.Context,
    voice: str | None = typer.Option(
        None,
        "--voice",
        "-v",
        help="Override: male|female (sonst settings.json)",
    ),
    engine: str = typer.Option(
        "auto",
        "--engine",
        "-e",
        help="auto | yingmusic | mock",
    ),
) -> None:
    """Ohne Subcommand = run (Drop-in aus MUSIC_INPUT)."""
    if ctx.invoked_subcommand is not None:
        return
    _run_from_music_input(voice=voice, engine=engine)


@app.command("run")
def run_cmd(
    voice: str | None = typer.Option(None, "--voice", "-v"),
    engine: str = typer.Option("auto", "--engine", "-e"),
) -> None:
    """Baue alles aus MUSIC_INPUT (Default-Workflow)."""
    _run_from_music_input(voice=voice, engine=engine)


@app.command("version")
def version_cmd() -> None:
    console.print(__version__)


@app.command("setup-yingmusic")
def setup_yingmusic_cmd(
    vendor_dir: Path | None = typer.Option(None, "--vendor-dir"),
) -> None:
    """YingMusic-Singer-Plus klonen (für echtes Neu-Singen)."""
    root = find_project_root()
    target = (vendor_dir or (root / "vendor" / "YingMusic-Singer-Plus")).resolve()
    console.print(f"Installing YingMusic into {target} …")
    path = setup_yingmusic(target)
    console.print(
        f"[green]Ready:[/green] {path}\n"
        "Weights: Hugging Face ASLP-lab/YingMusic-Singer (nicht Plus). "
        "GPU empfohlen; auf Mac MPS/CPU. Danach: ./scripts/generate.sh\n"
        "Aufräumen doppelter Caches: ./scripts/generate.sh cleanup"
    )


@app.command("cleanup")
def cleanup_cmd(
    keep_work: int = typer.Option(2, "--keep-work", help="Anzahl neuester .work-Jobs behalten"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Nur anzeigen, nichts löschen"),
    no_hf: bool = typer.Option(
        False,
        "--no-hf",
        help="Hugging-Face-Duplikate nicht löschen",
    ),
) -> None:
    """Doppelte Model-Caches + alte .work-Ordner aufräumen."""
    root = find_project_root()
    result = cleanup_caches(
        root,
        keep_work=keep_work,
        delete_unused_hf=not no_hf,
        dry_run=dry_run,
    )
    for note in result.notes:
        console.print(f"[dim]{note}[/dim]")
    for item in result.kept:
        console.print(f"[green]keep[/green] {item}")
    for item in result.removed:
        console.print(f"[yellow]removed[/yellow] {item}")
    console.print(
        f"{'Würde freigeben' if dry_run else 'Freigegeben'}: "
        f"[bold]{format_bytes(result.freed_bytes)}[/bold]"
    )


@app.command("doctor")
def doctor_cmd() -> None:
    """Check ffmpeg, Demucs, YingMusic, Ordner, Cache-Größen."""
    import shutil

    from local_ai_music_generator.cleanup import HF_HUB, KEEP_HF_REPOS, UNUSED_HF_REPOS, _dir_size

    root = find_project_root()
    paths = Paths(root=root)
    paths.ensure()
    console.print(f"project root: {root}")
    console.print(f"ffmpeg: {'yes' if shutil.which('ffmpeg') else 'MISSING'}")
    console.print(
        f"espeak-ng: {'yes' if shutil.which('espeak-ng') else 'MISSING (brew install espeak-ng)'}"
    )
    try:
        import demucs  # noqa: F401

        console.print("demucs: yes (gute Vocal/Instrumental-Trennung)")
    except ImportError:
        console.print(
            "demucs: no — optional, bessere Stem-Trennung:\n"
            "         pip install -e '.[separate]'",
            markup=False,
        )
    ym = YingMusicCoverEngine(home=root / "vendor" / "YingMusic-Singer-Plus")
    console.print(f"yingmusic: {'yes' if ym.available() else 'no (run setup-yingmusic)'}")
    console.print(f"MUSIC_INPUT: {paths.music_input}")
    console.print(f"MUSIC_OUTPUT: {paths.music_output}")
    for name in [*KEEP_HF_REPOS, *UNUSED_HF_REPOS]:
        path = HF_HUB / name
        if path.exists():
            tag = "keep" if name in KEEP_HF_REPOS else "unused→cleanup"
            console.print(f"HF {tag}: {name} ({format_bytes(_dir_size(path))})")
    work_size = _dir_size(paths.work) if paths.work.exists() else 0
    console.print(f".work: {format_bytes(work_size)}")
    try:
        jobs = discover_jobs(paths.music_input)
        console.print(f"erkannte Jobs: {len(jobs)}")
        for job in jobs:
            name = sanitize_output_name(job.output_name)
            console.print(
                f"  - {job.folder.name}: {job.audio.name} → "
                f"{name}.{job.output_format} (voice={job.voice})"
            )
    except InputDiscoveryError as exc:
        console.print(f"[yellow]noch keine Inputs:[/yellow] {exc}")


def _run_from_music_input(*, voice: str | None, engine: str) -> None:
    engine_norm = engine.lower().strip()
    if engine_norm not in {"auto", "yingmusic", "mock"}:
        raise typer.BadParameter("engine must be auto|yingmusic|mock")

    root = find_project_root()
    paths = Paths(root=root)
    paths.ensure()

    try:
        jobs = discover_jobs(paths.music_input)
    except InputDiscoveryError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    voice_override: str | None = None
    if voice is not None:
        voice_override = voice.lower().strip()
        if voice_override not in {"male", "female"}:
            raise typer.BadParameter("voice must be 'male' or 'female'")

    for job in jobs:
        chosen_voice = voice_override or job.voice
        out_base = sanitize_output_name(job.output_name)
        console.print(
            f"[bold]Job[/bold] {job.folder.name}: "
            f"{job.audio.name} + {job.lyrics_new.name} → "
            f"MUSIC_OUTPUT/{out_base}.{job.output_format} "
            f"(voice={chosen_voice})"
        )
        req = GenerateRequest(
            audio=job.audio,
            lyrics=job.lyrics_new,
            original_lyrics=job.lyrics_original,
            output_name=out_base,
            voice=chosen_voice,  # type: ignore[arg-type]
            engine=engine_norm,  # type: ignore[arg-type]
            output_format=job.output_format,
            apply_voice_gender=job.apply_voice_gender,
            keep_work_files=True,
        )
        try:
            result = generate(paths, req)
        except EngineNotReadyError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
        console.print(f"[bold green]Done[/bold green] → {result.output_path}")
