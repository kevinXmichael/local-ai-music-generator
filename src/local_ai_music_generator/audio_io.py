from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf


def load_audio(path: Path, sample_rate: int = 44100) -> tuple[np.ndarray, int]:
    """Load any common audio file as float32 mono (or stereo preserved if already wav-readable)."""
    path = path.resolve()
    if path.suffix.lower() in {".wav", ".flac", ".ogg"}:
        audio, sr = sf.read(str(path), always_2d=True)
        if sr != sample_rate:
            audio = _resample(audio, sr, sample_rate)
            sr = sample_rate
        return audio.astype(np.float32), sr

    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg is required to read mp3/m4a/aac. Install it (e.g. `brew install ffmpeg`)."
        )

    with tempfile.TemporaryDirectory(prefix="laim-audio-") as tmp:
        wav = Path(tmp) / "converted.wav"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(path),
            "-acodec",
            "pcm_f32le",
            "-ar",
            str(sample_rate),
            str(wav),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed:\n{proc.stderr[-2000:]}")
        audio, sr = sf.read(str(wav), always_2d=True)
    return audio.astype(np.float32), sr


def save_audio(path: Path, audio: np.ndarray, sample_rate: int) -> Path:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.asarray(audio, dtype=np.float32)
    if data.ndim == 1:
        data = data[:, None]
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    if peak > 1.0:
        data = data / peak

    suffix = path.suffix.lower()
    if suffix in {".wav", ".flac", ".ogg", ""}:
        out = path if suffix else path.with_suffix(".wav")
        sf.write(str(out), data, sample_rate)
        return out

    # Encode via ffmpeg for mp3/m4a
    if shutil.which("ffmpeg") is None:
        fallback = path.with_suffix(".wav")
        sf.write(str(fallback), data, sample_rate)
        return fallback

    with tempfile.TemporaryDirectory(prefix="laim-out-") as tmp:
        wav = Path(tmp) / "out.wav"
        sf.write(str(wav), data, sample_rate)
        cmd = ["ffmpeg", "-y", "-i", str(wav), str(path)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg encode failed:\n{proc.stderr[-2000:]}")
    return path


def to_mono(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return audio
    return np.mean(audio, axis=1)


def ensure_stereo(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return np.stack([audio, audio], axis=1)
    if audio.shape[1] == 1:
        return np.repeat(audio, 2, axis=1)
    return audio[:, :2]


def mix_tracks(
    vocals: np.ndarray,
    instrumental: np.ndarray,
    *,
    vocal_gain: float = 1.0,
    instrumental_gain: float = 1.0,
) -> np.ndarray:
    v = ensure_stereo(vocals) * vocal_gain
    i = ensure_stereo(instrumental) * instrumental_gain
    n = max(len(v), len(i))
    if len(v) < n:
        v = np.pad(v, ((0, n - len(v)), (0, 0)))
    if len(i) < n:
        i = np.pad(i, ((0, n - len(i)), (0, 0)))
    mixed = v + i
    peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0
    if peak > 0.99:
        mixed = mixed * (0.99 / peak)
    return mixed.astype(np.float32)


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    import librosa

    channels = []
    for c in range(audio.shape[1]):
        channels.append(librosa.resample(audio[:, c], orig_sr=orig_sr, target_sr=target_sr))
    return np.stack(channels, axis=1).astype(np.float32)
