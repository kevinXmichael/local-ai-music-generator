from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import soundfile as sf
from rich.console import Console

from local_ai_music_generator.audio_io import save_audio, to_mono
from local_ai_music_generator.config import VoiceGender
from local_ai_music_generator.engines.base import CoverResult
from local_ai_music_generator.engines.voice_gender import apply_voice_gender
from local_ai_music_generator.lyrics import LyricsDocument

DEFAULT_REPO = "https://github.com/ASLP-lab/YingMusic-Singer-Plus.git"
HF_MODEL = "ASLP-lab/YingMusic-Singer"
console = Console()

# Short chunks keep Apple Silicon responsive; full-song one-shot freezes the Mac.
DEFAULT_CHUNK_SECONDS = 20.0
DEFAULT_NFE_STEP = 16 if platform.system() == "Darwin" else 32


def default_yingmusic_home(project_root: Path | None = None) -> Path:
    root = project_root or Path.cwd()
    return (root / "vendor" / "YingMusic-Singer-Plus").resolve()


def find_project_root_from(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "MUSIC_INPUT").is_dir() and (candidate / "pyproject.toml").is_file():
            return candidate
    return start


def split_phrases_for_chunks(pipe_text: str, n_chunks: int) -> list[str]:
    """Distribute `|`-phrases across audio chunks (approx. time alignment)."""
    phrases = [p.strip() for p in pipe_text.split("|") if p.strip()]
    if n_chunks <= 1:
        return ["|".join(phrases) if phrases else pipe_text]
    if not phrases:
        return [""] * n_chunks

    out: list[str] = []
    for i in range(n_chunks):
        start = int(round(i * len(phrases) / n_chunks))
        end = int(round((i + 1) * len(phrases) / n_chunks))
        if end <= start:
            end = min(start + 1, len(phrases))
        chunk_phrases = phrases[start:end] or [phrases[min(start, len(phrases) - 1)]]
        out.append("|".join(chunk_phrases))
    return out


def crossfade_concat(parts: list[np.ndarray], sample_rate: int, fade_ms: int = 40) -> np.ndarray:
    if not parts:
        return np.zeros(0, dtype=np.float32)
    fade = max(1, int(sample_rate * fade_ms / 1000))
    out = parts[0].astype(np.float32)
    for nxt in parts[1:]:
        nxt = nxt.astype(np.float32)
        if len(out) == 0:
            out = nxt
            continue
        n = min(fade, len(out), len(nxt))
        if n <= 1:
            out = np.concatenate([out, nxt])
            continue
        ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
        mixed = out[-n:] * (1.0 - ramp) + nxt[:n] * ramp
        out = np.concatenate([out[:-n], mixed, nxt[n:]])
    return out


class YingMusicCoverEngine:
    """Wrapper around YingMusic-Singer-Plus for melody-preserving lyric edits."""

    name = "yingmusic"

    def __init__(self, home: Path | None = None) -> None:
        env = os.environ.get("YINGMUSIC_HOME")
        self.home = Path(home or env or default_yingmusic_home()).resolve()

    def available(self) -> bool:
        return (self.home / "infer_api.py").is_file() or (self.home / "infer.py").is_file()

    def python_bin(self) -> Path:
        for path in (
            self.home / ".venv" / "bin" / "python",
            self.home / ".venv" / "Scripts" / "python.exe",
        ):
            if path.is_file():
                return path
        return Path(sys.executable)

    def infer_entrypoint(self, project_root: Path) -> list[str]:
        wrapper = project_root / "scripts" / "yingmusic_infer.py"
        py = str(self.python_bin())
        if wrapper.is_file():
            return [py, str(wrapper)]
        api = self.home / "infer_api.py"
        if api.is_file():
            return [py, str(api)]
        return [py, str(self.home / "infer.py")]

    def cover(
        self,
        *,
        vocals: np.ndarray,
        sample_rate: int,
        original_lyrics: LyricsDocument,
        target_lyrics: LyricsDocument,
        voice: VoiceGender,
        work_dir: Path,
        apply_gender: bool = False,
        source_mix: Path | None = None,
        chunk_seconds: float = DEFAULT_CHUNK_SECONDS,
        max_seconds: float | None = None,
        nfe_step: int = DEFAULT_NFE_STEP,
    ) -> CoverResult:
        del source_mix
        if not self.available():
            raise RuntimeError(
                "YingMusic not found. Run: ./scripts/generate.sh setup-yingmusic"
            )

        work_dir.mkdir(parents=True, exist_ok=True)
        project_root = find_project_root_from(self.home.parent.parent)
        mono = to_mono(vocals).astype(np.float32)

        if max_seconds is not None and max_seconds > 0:
            mono = mono[: int(max_seconds * sample_rate)]
            console.print(f"[yellow]YingMusic[/yellow] begrenzt auf {max_seconds:.0f}s (settings)")

        duration = len(mono) / float(sample_rate)
        chunk_seconds = float(chunk_seconds) if chunk_seconds and chunk_seconds > 0 else 0.0

        if chunk_seconds <= 0 or duration <= chunk_seconds * 1.25:
            chunks = [mono]
        else:
            width = int(chunk_seconds * sample_rate)
            chunks = [mono[i : i + width] for i in range(0, len(mono), width)]
            # merge tiny trailing chunk into previous
            if len(chunks) > 1 and len(chunks[-1]) < width * 0.35:
                chunks[-2] = np.concatenate([chunks[-2], chunks[-1]])
                chunks.pop()

        n = len(chunks)
        ref_parts = split_phrases_for_chunks(original_lyrics.phrase_pipe, n)
        tgt_parts = split_phrases_for_chunks(target_lyrics.phrase_pipe, n)

        console.print(
            f"[bold]YingMusic[/bold] {duration:.0f}s Audio → {n} Chunk(s) "
            f"à ~{chunk_seconds or duration:.0f}s · nfe={nfe_step} · live log"
        )
        if platform.system() == "Darwin":
            console.print(
                "[dim]macOS: niedrige Priorität + Chunks, damit das System nicht einfriert. "
                "Kann trotzdem lange dauern.[/dim]"
            )

        rendered: list[np.ndarray] = []
        out_sr = sample_rate
        for idx, chunk in enumerate(chunks, start=1):
            console.print(f"[cyan]Chunk {idx}/{n}[/cyan] ({len(chunk) / sample_rate:.1f}s) …")
            part_dir = work_dir / f"chunk_{idx:02d}"
            part_dir.mkdir(parents=True, exist_ok=True)
            melody_path = part_dir / "melody.wav"
            ref_path = part_dir / "ref.wav"
            out_path = part_dir / "out.wav"
            save_audio(melody_path, chunk, sample_rate)
            save_audio(ref_path, chunk[: min(len(chunk), sample_rate * 8)], sample_rate)

            self._run_infer(
                project_root=project_root,
                ref=str(ref_path.resolve()),
                melody=str(melody_path.resolve()),
                ref_text=ref_parts[idx - 1],
                target_text=tgt_parts[idx - 1],
                output=str(out_path.resolve()),
                nfe_step=nfe_step,
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                audio, out_sr = sf.read(str(out_path), always_2d=False)
            rendered.append(to_mono(np.asarray(audio, dtype=np.float32)))

        audio = crossfade_concat(rendered, out_sr)
        # Match original duration roughly
        target_len = len(mono)
        if len(audio) > target_len:
            audio = audio[:target_len]
        elif len(audio) < target_len:
            audio = np.pad(audio, (0, target_len - len(audio)))

        if apply_gender:
            audio = apply_voice_gender(audio, out_sr, voice, strength=0.35)

        notes = (
            f"YingMusic chunked lyric edit ({n}×~{chunk_seconds or duration:.0f}s, nfe={nfe_step})"
        )
        return CoverResult(
            vocals=audio.astype(np.float32),
            sample_rate=out_sr,
            engine=self.name,
            notes=notes,
            already_mixed=False,
        )

    def _run_infer(
        self,
        *,
        project_root: Path,
        ref: str,
        melody: str,
        ref_text: str,
        target_text: str,
        output: str,
        nfe_step: int,
    ) -> None:
        cmd = [
            *self.infer_entrypoint(project_root),
            "--ref_audio",
            ref,
            "--melody_audio",
            melody,
            "--ref_text",
            ref_text,
            "--target_text",
            target_text,
            "--output",
            output,
            "--nfe_step",
            str(nfe_step),
        ]
        env = os.environ.copy()
        env.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        # Leave headroom so macOS UI stays alive (unified memory).
        env.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.55")

        def _nice() -> None:
            try:
                os.nice(15)
            except OSError:
                pass

        log_path = Path(output).with_suffix(".log")
        with log_path.open("w", encoding="utf-8") as log:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.home),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                bufsize=1,
                preexec_fn=_nice if os.name == "posix" else None,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                log.write(line)
                # Show progress lines live so it doesn't look "frozen"
                stripped = line.rstrip()
                if stripped:
                    console.print(f"  [dim]{stripped}[/dim]")
            code = proc.wait()
        if code != 0 or not Path(output).exists():
            tail = log_path.read_text(encoding="utf-8")[-4000:]
            raise RuntimeError(
                "YingMusic inference failed.\n"
                f"cmd: {' '.join(cmd)}\n"
                f"log:\n{tail}"
            )


def setup_yingmusic(vendor_dir: Path, *, repo_url: str = DEFAULT_REPO) -> Path:
    """Clone YingMusic + create Python 3.10 venv + install mac-friendly deps."""
    vendor_dir = vendor_dir.resolve()
    vendor_dir.parent.mkdir(parents=True, exist_ok=True)

    if shutil.which("espeak-ng") is None and shutil.which("espeak") is None:
        raise RuntimeError(
            "espeak-ng fehlt (Phoneme). Auf macOS: brew install espeak-ng"
        )

    if not (
        (vendor_dir / "infer_api.py").is_file() or (vendor_dir / "infer.py").is_file()
    ):
        if vendor_dir.exists():
            shutil.rmtree(vendor_dir)
        if shutil.which("git") is None:
            raise RuntimeError("git is required to clone YingMusic-Singer-Plus")
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(vendor_dir)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git clone failed:\n{proc.stderr}")

    py310 = shutil.which("python3.10")
    if not py310:
        raise RuntimeError("Python 3.10 fehlt. Auf macOS: brew install python@3.10")

    venv_py = vendor_dir / ".venv" / "bin" / "python"
    if not venv_py.is_file():
        subprocess.run([py310, "-m", "venv", str(vendor_dir / ".venv")], check=True)

    req = vendor_dir / "requirements.txt"
    filtered = vendor_dir / "requirements.mac.txt"
    skip = {"bitsandbytes", "triton", "xformers", "flash-attn"}
    lines: list[str] = []
    for line in req.read_text(encoding="utf-8").splitlines():
        name = line.split("==")[0].split(">=")[0].strip().lower()
        if name in skip or name.startswith("nvidia-"):
            continue
        lines.append(line)
    filtered.write_text("\n".join(lines) + "\n", encoding="utf-8")

    subprocess.run(
        [str(venv_py), "-m", "pip", "install", "-U", "pip", "uv", "huggingface_hub"],
        check=True,
    )
    uv = vendor_dir / ".venv" / "bin" / "uv"
    install = subprocess.run(
        [str(uv), "pip", "install", "-r", str(filtered)],
        cwd=str(vendor_dir),
        capture_output=True,
        text=True,
    )
    if install.returncode != 0:
        pip_install = subprocess.run(
            [str(venv_py), "-m", "pip", "install", "-r", str(filtered)],
            capture_output=True,
            text=True,
        )
        if pip_install.returncode != 0:
            raise RuntimeError(
                "YingMusic deps install failed:\n"
                f"{install.stderr[-2000:]}\n{pip_install.stderr[-2000:]}"
            )

    subprocess.run(
        [str(venv_py), str(vendor_dir / "initialization.py"), "--task", "infer"],
        cwd=str(vendor_dir),
        check=False,
    )
    subprocess.run(
        [
            str(venv_py),
            "-c",
            "from huggingface_hub import snapshot_download; "
            f"print(snapshot_download('{HF_MODEL}'))",
        ],
        check=False,
    )
    return vendor_dir
