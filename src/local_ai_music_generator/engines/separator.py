from __future__ import annotations

from pathlib import Path

import numpy as np

from local_ai_music_generator.audio_io import to_mono
from local_ai_music_generator.engines.base import SeparationResult


def _torch_device():
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class SimpleHpssSeparator:
    """Rough fallback when demucs is not installed. Do not use for real covers."""

    name = "hpss"

    def separate(self, audio: np.ndarray, sample_rate: int, work_dir: Path) -> SeparationResult:
        import librosa

        work_dir.mkdir(parents=True, exist_ok=True)
        mono = to_mono(audio)
        harmonic, _percussive = librosa.effects.hpss(mono)
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
        target_sr = int(getattr(model, "samplerate", 44100))

        wav = audio
        if wav.ndim == 1:
            wav = np.stack([wav, wav], axis=0)
        else:
            wav = wav.T
        if wav.shape[0] == 1:
            wav = np.repeat(wav, 2, axis=0)

        if sample_rate != target_sr:
            import librosa

            resampled = [
                librosa.resample(wav[c], orig_sr=sample_rate, target_sr=target_sr)
                for c in range(wav.shape[0])
            ]
            wav = np.stack(resampled, axis=0)

        device = _torch_device()
        # demucs on MPS can be flaky; prefer mps then fall back to cpu
        tensor = torch.tensor(wav, dtype=torch.float32).unsqueeze(0)
        try:
            with torch.no_grad():
                sources = apply_model(
                    model, tensor, device=device, split=True, overlap=0.25, progress=True
                )[0]
        except Exception:
            with torch.no_grad():
                sources = apply_model(
                    model, tensor, device="cpu", split=True, overlap=0.25, progress=True
                )[0]

        names = list(model.sources)
        stems = {name: sources[i].detach().cpu().numpy() for i, name in enumerate(names)}
        vocals = stems["vocals"].T
        instrumental = sum(stems[n] for n in names if n != "vocals").T
        return SeparationResult(
            vocals=vocals.astype(np.float32),
            instrumental=instrumental.astype(np.float32),
            sample_rate=target_sr,
        )


def get_separator(prefer_demucs: bool = True):
    if prefer_demucs:
        try:
            import demucs  # noqa: F401

            return DemucsSeparator()
        except ImportError:
            pass
    return SimpleHpssSeparator()
