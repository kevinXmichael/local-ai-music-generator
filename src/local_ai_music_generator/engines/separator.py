from __future__ import annotations

from pathlib import Path

import numpy as np

from local_ai_music_generator.audio_io import to_mono
from local_ai_music_generator.engines.base import SeparationResult


class SimpleHpssSeparator:
    """CPU-friendly harmonic/percussive split used when demucs is not installed.

    Not studio-quality — good enough for dry-runs and CI. Prefer demucs for real covers.
    """

    name = "hpss"

    def separate(self, audio: np.ndarray, sample_rate: int, work_dir: Path) -> SeparationResult:
        import librosa

        work_dir.mkdir(parents=True, exist_ok=True)
        mono = to_mono(audio)
        harmonic, percussive = librosa.effects.hpss(mono)
        # Treat harmonic as "vocals-ish", residual as accompaniment proxy
        vocals = harmonic.astype(np.float32)
        instrumental = (mono - harmonic * 0.85).astype(np.float32)
        return SeparationResult(vocals=vocals, instrumental=instrumental, sample_rate=sample_rate)


class DemucsSeparator:
    name = "demucs"

    def __init__(self, model: str = "htdemucs") -> None:
        self.model = model

    def separate(self, audio: np.ndarray, sample_rate: int, work_dir: Path) -> SeparationResult:
        try:
            import torch
            from demucs.apply import apply_model
            from demucs.pretrained import get_model
        except ImportError as exc:
            raise RuntimeError(
                "demucs/torch not installed. Run: pip install 'local-ai-music-generator[separate]'"
            ) from exc

        work_dir.mkdir(parents=True, exist_ok=True)
        model = get_model(self.model)
        model.eval()
        # demucs expects (batch, channels, time)
        wav = audio
        if wav.ndim == 1:
            wav = np.stack([wav, wav], axis=0)
        else:
            wav = wav.T  # (ch, time)
        if wav.shape[0] == 1:
            wav = np.repeat(wav, 2, axis=0)
        tensor = torch.tensor(wav).unsqueeze(0)
        with torch.no_grad():
            sources = apply_model(model, tensor, device="cpu", split=True, overlap=0.25)[0]
        # order depends on model; htdemucs: drums, bass, other, vocals
        names = list(model.sources)
        stems = {name: sources[i].cpu().numpy() for i, name in enumerate(names)}
        vocals = stems["vocals"].T  # (time, ch)
        instrumental = sum(stems[n] for n in names if n != "vocals").T
        return SeparationResult(
            vocals=vocals.astype(np.float32),
            instrumental=instrumental.astype(np.float32),
            sample_rate=model.samplerate if hasattr(model, "samplerate") else sample_rate,
        )


def get_separator(prefer_demucs: bool = True):
    if prefer_demucs:
        try:
            import demucs  # noqa: F401

            return DemucsSeparator()
        except ImportError:
            pass
    return SimpleHpssSeparator()
