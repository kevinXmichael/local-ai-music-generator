from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from local_ai_music_generator import __version__
from local_ai_music_generator.config import GenerateRequest, Paths, find_project_root
from local_ai_music_generator.discover import InputDiscoveryError, discover_jobs
from local_ai_music_generator.engines.yingmusic import YingMusicCoverEngine, setup_yingmusic
from local_ai_music_generator.pipeline import generate, sanitize_output_name

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
        "Weights laut YingMusic-README von Hugging Face laden "
        "(ASLP-lab/YingMusic-Singer-Plus). GPU empfohlen."
    )


@app.command("doctor")
def doctor_cmd() -> None:
    """Check ffmpeg, Demucs, YingMusic, Ordner."""
    import shutil

    root = find_project_root()
    paths = Paths(root=root)
    paths.ensure()
    console.print(f"project root: {root}")
    console.print(f"ffmpeg: {'yes' if shutil.which('ffmpeg') else 'MISSING'}")
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
            keep_work_files=True,
        )
        result = generate(paths, req)
        console.print(f"[bold green]Done[/bold green] → {result.output_path}")
