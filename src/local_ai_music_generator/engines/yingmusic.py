from __future__ import annotations

import os
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import soundfile as sf

from local_ai_music_generator.audio_io import save_audio, to_mono
from local_ai_music_generator.config import VoiceGender
from local_ai_music_generator.engines.base import CoverResult
from local_ai_music_generator.engines.voice_gender import apply_voice_gender
from local_ai_music_generator.lyrics import LyricsDocument

DEFAULT_REPO = "https://github.com/ASLP-lab/YingMusic-Singer-Plus.git"
HF_MODEL = "ASLP-lab/YingMusic-Singer"


def default_yingmusic_home(project_root: Path | None = None) -> Path:
    root = project_root or Path.cwd()
    return (root / "vendor" / "YingMusic-Singer-Plus").resolve()


def find_project_root_from(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "MUSIC_INPUT").is_dir() and (candidate / "pyproject.toml").is_file():
            return candidate
    return start


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
    ) -> CoverResult:
        if not self.available():
            raise RuntimeError(
                "YingMusic not found. Run: ./scripts/generate.sh setup-yingmusic"
            )

        work_dir.mkdir(parents=True, exist_ok=True)
        out = work_dir / "yingmusic_output.wav"
        project_root = find_project_root_from(self.home.parent.parent)

        ref_text = original_lyrics.phrase_pipe
        target_text = target_lyrics.phrase_pipe

        # Prefer full-mix path with YingMusic's own separation+mix when available.
        if source_mix and source_mix.is_file():
            melody = str(source_mix.resolve())
            ref = melody
            extra = ["--separate_vocals", "--mix_accompaniment"]
            notes = "YingMusic lyric edit with built-in vocal separation + mix"
        else:
            melody_path = work_dir / "melody_vocals.wav"
            ref_path = work_dir / "timbre_ref.wav"
            mono = to_mono(vocals)
            save_audio(melody_path, mono, sample_rate)
            save_audio(ref_path, mono[: min(len(mono), sample_rate * 12)], sample_rate)
            melody = str(melody_path)
            ref = str(ref_path)
            extra = []
            notes = "YingMusic lyric edit on pre-separated vocals"

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
            str(out),
            *extra,
        ]
        env = os.environ.copy()
        env.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        proc = subprocess.run(
            cmd, cwd=str(self.home), capture_output=True, text=True, env=env
        )
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError(
                "YingMusic inference failed.\n"
                f"cmd: {' '.join(cmd)}\n"
                f"stdout:\n{proc.stdout[-5000:]}\n"
                f"stderr:\n{proc.stderr[-5000:]}"
            )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            audio, sr = sf.read(str(out), always_2d=False)
        audio = np.asarray(audio, dtype=np.float32)
        # If YingMusic already mixed accompaniment, return full mix as "vocals"
        # channel for pipeline (pipeline will skip double-mix when flagged).
        if apply_gender:
            audio = apply_voice_gender(to_mono(audio), sr, voice, strength=0.35)
        return CoverResult(
            vocals=audio,
            sample_rate=sr,
            engine=self.name,
            notes=notes,
            already_mixed=bool(source_mix and source_mix.is_file()),
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

    # Separation checkpoints used by infer_api
    subprocess.run(
        [str(venv_py), str(vendor_dir / "initialization.py"), "--task", "infer"],
        cwd=str(vendor_dir),
        check=False,
    )
    # Prefetch main model package
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
