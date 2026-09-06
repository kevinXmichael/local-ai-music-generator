from __future__ import annotations

import numpy as np

from local_ai_music_generator.audio_io import to_mono
from local_ai_music_generator.config import VoiceGender


def apply_voice_gender(
    audio: np.ndarray,
    sample_rate: int,
    voice: VoiceGender,
    *,
    strength: float = 1.0,
) -> np.ndarray:
    """Lightweight male/female formant+pitch shift without a trained RVC model.

    For highest fidelity, prefer YingMusic timbre reference + optional RVC later.
    This keeps a free, dependency-light gender control that always works offline.
    """
    import librosa

    mono = to_mono(np.asarray(audio, dtype=np.float32))
    strength = float(np.clip(strength, 0.0, 2.0))
    if strength == 0.0:
        return mono

    if voice == "female":
        n_steps = 2.0 * strength
        formant = 1.08 ** strength
    else:
        n_steps = -2.0 * strength
        formant = (1 / 1.08) ** strength

    pitched = librosa.effects.pitch_shift(mono, sr=sample_rate, n_steps=n_steps)
    # Crude formant move via resample stretch round-trip
    stretched = librosa.effects.time_stretch(pitched, rate=formant)
    # Match original duration
    if len(stretched) > len(mono):
        stretched = stretched[: len(mono)]
    elif len(stretched) < len(mono):
        stretched = np.pad(stretched, (0, len(mono) - len(stretched)))
    return stretched.astype(np.float32)
