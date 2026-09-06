from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from local_ai_music_generator.audio_io import save_audio, to_mono
from local_ai_music_generator.config import VoiceGender
from local_ai_music_generator.engines import CoverResult
from local_ai_music_generator.engines.voice_gender import apply_voice_gender
from local_ai_music_generator.lyrics import LyricsDocument

DEFAULT_REPO = "https://github.com/ASLP-lab/YingMusic-Singer-Plus.git"


class YingMusicCoverEngine:
    """Wrapper around YingMusic-Singer-Plus CLI for melody-preserving lyric edits.

    Setup once:

        python -m local_ai_music_generator setup-yingmusic

    Or set ``YINGMUSIC_HOME`` to a local checkout that contains ``infer.py``.
    """

    name = "yingmusic"

    def __init__(self, home: Path | None = None) -> None:
        env = os.environ.get("YINGMUSIC_HOME")
        self.home = Path(home or env or Path.cwd() / "vendor" / "YingMusic-Singer-Plus").resolve()

    def available(self) -> bool:
        return (self.home / "infer.py").is_file()

    def cover(
        self,
        *,
        vocals: np.ndarray,
        sample_rate: int,
        original_lyrics: LyricsDocument,
        target_lyrics: LyricsDocument,
        voice: VoiceGender,
        work_dir: Path,
    ) -> CoverResult:
        if not self.available():
            raise RuntimeError(
                "YingMusic not found. Run `python -m local_ai_music_generator setup-yingmusic` "
                "or set YINGMUSIC_HOME."
            )

        work_dir.mkdir(parents=True, exist_ok=True)
        melody = work_dir / "melody_vocals.wav"
        ref = work_dir / "timbre_ref.wav"
        out = work_dir / "yingmusic_vocals.wav"

        mono = to_mono(vocals)
        save_audio(melody, mono, sample_rate)
        # Use a short slice as timbre reference; gender nudge applied after infer
        ref_audio = mono[: min(len(mono), sample_rate * 12)]
        save_audio(ref, ref_audio, sample_rate)

        ref_text = original_lyrics.phrase_pipe
        target_text = target_lyrics.phrase_pipe
        cmd = [
            sys.executable,
            str(self.home / "infer.py"),
            "--ref_audio",
            str(ref),
            "--melody_audio",
            str(melody),
            "--ref_text",
            ref_text,
            "--target_text",
            target_text,
            "--output",
            str(out),
        ]
        proc = subprocess.run(cmd, cwd=str(self.home), capture_output=True, text=True)
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError(
                "YingMusic infer.py failed.\n"
                f"cmd: {' '.join(cmd)}\n"
                f"stdout:\n{proc.stdout[-3000:]}\n"
                f"stderr:\n{proc.stderr[-3000:]}"
            )

        audio, sr = sf.read(str(out), always_2d=False)
        audio = np.asarray(audio, dtype=np.float32)
        audio = apply_voice_gender(audio, sr, voice, strength=0.6)
        return CoverResult(
            vocals=audio,
            sample_rate=sr,
            engine=self.name,
            notes="YingMusic-Singer-Plus lyric edit + light gender shaping",
        )


def setup_yingmusic(vendor_dir: Path, *, repo_url: str = DEFAULT_REPO) -> Path:
    """Clone YingMusic-Singer-Plus into vendor/ (weights downloaded by their tooling)."""
    vendor_dir = vendor_dir.resolve()
    vendor_dir.parent.mkdir(parents=True, exist_ok=True)
    if (vendor_dir / "infer.py").is_file():
        return vendor_dir

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

    req = vendor_dir / "requirements.txt"
    if req.is_file():
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req)],
            check=False,
        )
    return vendor_dir
