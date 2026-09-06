from __future__ import annotations

import numpy as np

from local_ai_music_generator.polish import (
    match_spectral_envelope,
    polish_vocals,
    soft_compress,
    soft_limit,
    studio_mix,
)


def test_match_spectral_envelope_preserves_length() -> None:
    sr = 16000
    t = np.linspace(0, 1.0, sr, dtype=np.float32)
    src = 0.2 * np.sin(2 * np.pi * 440 * t)
    ref = 0.2 * np.sin(2 * np.pi * 220 * t)
    out = match_spectral_envelope(src, ref, sample_rate=sr, strength=0.7)
    assert len(out) == len(src)
    assert float(np.max(np.abs(out))) > 0


def test_soft_compress_reduces_peaks() -> None:
    x = np.array([0.1, 0.9, -0.95, 0.2], dtype=np.float32)
    y = soft_compress(x, threshold=0.3, ratio=3.0, makeup=1.0)
    assert abs(y[1]) < abs(x[1])
    assert abs(y[2]) < abs(x[2])


def test_studio_mix_and_polish_smoke() -> None:
    sr = 22050
    n = sr * 2
    vocals = (0.15 * np.sin(2 * np.pi * 300 * np.linspace(0, 2, n))).astype(np.float32)
    inst = (0.1 * np.sin(2 * np.pi * 110 * np.linspace(0, 2, n))).astype(np.float32)
    polished = polish_vocals(vocals, sample_rate=sr, reference=vocals, reverb_mix=0.05)
    mixed = studio_mix(polished, inst)
    limited = soft_limit(mixed)
    assert mixed.ndim == 2
    assert float(np.max(np.abs(limited))) <= 0.98
