from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from local_ai_music_generator import __version__
from local_ai_music_generator.config import GenerateRequest, Paths, find_project_root
from local_ai_music_generator.engines.yingmusic import YingMusicCoverEngine, setup_yingmusic
from local_ai_music_generator.pipeline import generate, sanitize_output_name

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Local free AI lyric-cover generator (template song → new lyrics).",
)
console = Console()


@app.callback()
def _root() -> None:
    """Local AI music generator."""


@app.command("version")
def version_cmd() -> None:
    console.print(__version__)


@app.command("generate")
def generate_cmd(
    audio: Path = typer.Option(..., "--audio", "-a", help="Template song (mp3/m4a/wav/…)"),
    lyrics: Path = typer.Option(..., "--lyrics", "-l", help="Target lyrics (.txt/.srt/.lrc)"),
    output_name: str = typer.Option(
        ...,
        "--output-name",
        "-o",
        help="Base name for MUSIC_OUTPUT/<name>.wav",
    ),
    voice: str = typer.Option(
        "female",
        "--voice",
        "-v",
        help="Voice gender: male or female",
        case_sensitive=False,
    ),
    original_lyrics: Path | None = typer.Option(
        None,
        "--original-lyrics",
        help="Lyrics as sung on the template (needed for accurate lyric edits)",
    ),
    engine: str = typer.Option(
        "auto",
        "--engine",
        "-e",
        help="auto | yingmusic | mock",
    ),
    keep_work: bool = typer.Option(
        True,
        "--keep-work/--no-keep-work",
        help="Keep intermediate stems under .work/",
    ),
    project_root: Path | None = typer.Option(
        None,
        "--project-root",
        help="Project root containing MUSIC_INPUT / MUSIC_OUTPUT",
    ),
) -> None:
    """Create a cover from a template track + adapted lyrics."""
    voice_norm = voice.lower().strip()
    if voice_norm not in {"male", "female"}:
        raise typer.BadParameter("voice must be 'male' or 'female'")
    engine_norm = engine.lower().strip()
    if engine_norm not in {"auto", "yingmusic", "mock"}:
        raise typer.BadParameter("engine must be auto|yingmusic|mock")

    root = find_project_root(project_root)
    paths = Paths(root=root)
    req = GenerateRequest(
        audio=audio.expanduser().resolve(),
        lyrics=lyrics.expanduser().resolve(),
        original_lyrics=original_lyrics.expanduser().resolve() if original_lyrics else None,
        output_name=sanitize_output_name(output_name),
        voice=voice_norm,  # type: ignore[arg-type]
        engine=engine_norm,  # type: ignore[arg-type]
        keep_work_files=keep_work,
    )
    if not req.audio.is_file():
        raise typer.BadParameter(f"audio not found: {req.audio}")
    if not req.lyrics.is_file():
        raise typer.BadParameter(f"lyrics not found: {req.lyrics}")

    result = generate(paths, req)
    console.print(f"[bold green]Done[/bold green] → {result.output_path}")


@app.command("setup-yingmusic")
def setup_yingmusic_cmd(
    vendor_dir: Path | None = typer.Option(
        None,
        "--vendor-dir",
        help="Clone target (default: ./vendor/YingMusic-Singer-Plus)",
    ),
    project_root: Path | None = typer.Option(None, "--project-root"),
) -> None:
    """Clone YingMusic-Singer-Plus for real melody-preserving lyric covers."""
    root = find_project_root(project_root)
    target = (vendor_dir or (root / "vendor" / "YingMusic-Singer-Plus")).resolve()
    console.print(f"Installing YingMusic into {target} …")
    path = setup_yingmusic(target)
    console.print(
        f"[green]Ready:[/green] {path}\n"
        "Set export YINGMUSIC_HOME if you move it.\n"
        "Follow their README to download model weights "
        "(Hugging Face: ASLP-lab/YingMusic-Singer-Plus). GPU strongly recommended."
    )


@app.command("doctor")
def doctor_cmd(project_root: Path | None = typer.Option(None, "--project-root")) -> None:
    """Check ffmpeg, folders, and optional engines."""
    import shutil

    root = find_project_root(project_root)
    paths = Paths(root=root)
    paths.ensure()
    console.print(f"project root: {root}")
    console.print(f"ffmpeg: {'yes' if shutil.which('ffmpeg') else 'MISSING'}")
    try:
        import demucs  # noqa: F401

        console.print("demucs: yes")
    except ImportError:
        console.print("demucs: no (optional — pip install '.[separate]')")
    ym = YingMusicCoverEngine(home=root / "vendor" / "YingMusic-Singer-Plus")
    console.print(f"yingmusic: {'yes' if ym.available() else 'no (run setup-yingmusic)'}")
    console.print(f"MUSIC_INPUT: {paths.music_input}")
    console.print(f"MUSIC_OUTPUT: {paths.music_output}")
