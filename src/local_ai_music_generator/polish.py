"""Cover-style vocal glue + mix — local, no RVC/cloud.

Bridges surgical lyric edits with AICoverGen-like finish:
spectral envelope match (timbre glue), soft compression, presence,
light plate reverb, balanced stem mix, soft limiter.
"""

from __future__ import annotations

import numpy as np

from local_ai_music_generator.audio_io import ensure_stereo, to_mono


def match_spectral_envelope(
    source: np.ndarray,
    reference: np.ndarray,
    *,
    sample_rate: int,
    n_fft: int = 2048,
    hop: int = 512,
    strength: float = 0.85,
) -> np.ndarray:
    """Pull source timbre toward reference via smoothed STFT magnitude envelopes."""
    import librosa

    src = to_mono(np.asarray(source, dtype=np.float32))
    ref = to_mono(np.asarray(reference, dtype=np.float32))
    n = min(len(src), len(ref))
    if n < n_fft:
        return src.astype(np.float32)
    src, ref = src[:n], ref[:n]

    S = librosa.stft(src, n_fft=n_fft, hop_length=hop)
    R = librosa.stft(ref, n_fft=n_fft, hop_length=hop)
    mag_s = np.abs(S)
    mag_r = np.abs(R)
    # Time-average envelopes (per bin)
    env_s = np.maximum(np.mean(mag_s, axis=1, keepdims=True), 1e-6)
    env_r = np.maximum(np.mean(mag_r, axis=1, keepdims=True), 1e-6)
    transfer = (env_r / env_s) ** float(strength)
    # Cap extreme boosts so splices don't scream
    transfer = np.clip(transfer, 0.35, 2.8)
    S_out = S * transfer
    out = librosa.istft(S_out, hop_length=hop, length=n)
    return out.astype(np.float32)


def soft_compress(
    audio: np.ndarray,
    *,
    threshold: float = 0.32,
    ratio: float = 2.4,
    makeup: float = 1.08,
) -> np.ndarray:
    """Simple peak compressor (sample-wise soft knee)."""
    x = np.asarray(audio, dtype=np.float32)
    ax = np.abs(x)
    over = ax > threshold
    if not np.any(over):
        return (x * makeup).astype(np.float32)
    # gain = threshold + (ax - threshold) / ratio  → scale = gain / ax
    compressed = np.where(
        over,
        np.sign(x) * (threshold + (ax - threshold) / ratio),
        x,
    )
    return (compressed * makeup).astype(np.float32)


def presence_eq(audio: np.ndarray, *, sample_rate: int, amount: float = 0.12) -> np.ndarray:
    """Gentle high-shelf (~4 kHz) for vocal clarity."""
    import librosa

    mono = to_mono(np.asarray(audio, dtype=np.float32))
    if amount <= 0:
        return mono
    # Pre-emphasis-ish: y[n] = x[n] - a*x[n-1] blended
    a = float(np.clip(0.85 - amount * 0.4, 0.55, 0.92))
    emph = np.empty_like(mono)
    emph[0] = mono[0]
    emph[1:] = mono[1:] - a * mono[:-1]
    # Blend + mild low-cut via HPSS harmonic emphasis is overkill; mix dry/wet
    out = (1.0 - amount) * mono + amount * emph
    # Soften harsh band with a tiny spectral dip around 3.5k if too bright
    S = librosa.stft(out, n_fft=1024, hop_length=256)
    freqs = librosa.fft_frequencies(sr=sample_rate, n_fft=1024)
    harsh = (freqs >= 2800) & (freqs <= 5200)
    S[harsh, :] *= 0.92
    out = librosa.istft(S, hop_length=256, length=len(mono))
    return out.astype(np.float32)


def plate_reverb(
    audio: np.ndarray,
    *,
    sample_rate: int,
    mix: float = 0.1,
    decay: float = 0.38,
) -> np.ndarray:
    """Lightweight multi-tap feedback reverb (no scipy)."""
    mono = to_mono(np.asarray(audio, dtype=np.float32))
    mix = float(np.clip(mix, 0.0, 0.45))
    if mix <= 1e-4:
        return mono

    delays_ms = (29.0, 37.0, 53.0, 67.0)
    wet = np.zeros_like(mono)
    fb = float(np.clip(decay, 0.05, 0.7))
    for ms in delays_ms:
        d = max(1, int(sample_rate * ms / 1000.0))
        # Vectorized multi-echo (avoids slow Python sample loop)
        for k in range(1, 7):
            delay = d * k
            if delay >= len(mono):
                break
            gain = (fb ** k) * 0.55
            wet[delay:] += mono[:-delay] * gain
    wet *= 1.0 / max(1, len(delays_ms))
    # Match wet RMS roughly to dry so mix is predictable
    dry_rms = float(np.sqrt(np.mean(mono**2) + 1e-12))
    wet_rms = float(np.sqrt(np.mean(wet**2) + 1e-12))
    if wet_rms > 1e-8:
        wet *= dry_rms / wet_rms
    out = (1.0 - mix) * mono + mix * wet
    return out.astype(np.float32)


def estimate_wetness(audio: np.ndarray, *, sample_rate: int) -> float:
    """Rough 0–1 wetness from late energy vs early energy (for auto reverb)."""
    mono = to_mono(np.asarray(audio, dtype=np.float32))
    if len(mono) < sample_rate:
        return 0.08
    # Compare energy in 40–80ms “room” lags vs dry — use autocorrelation peak
    max_lag = int(0.08 * sample_rate)
    min_lag = int(0.025 * sample_rate)
    chunk = mono[: min(len(mono), sample_rate * 8)]
    chunk = chunk - float(np.mean(chunk))
    denom = float(np.dot(chunk, chunk) + 1e-12)
    best = 0.0
    for lag in range(min_lag, max_lag, max(1, sample_rate // 500)):
        corr = float(np.dot(chunk[lag:], chunk[:-lag]) / denom)
        best = max(best, abs(corr))
    return float(np.clip(best * 0.55, 0.04, 0.22))


def polish_vocals(
    vocals: np.ndarray,
    *,
    sample_rate: int,
    reference: np.ndarray | None = None,
    reverb_mix: float | None = None,
    compress: bool = True,
) -> np.ndarray:
    """Full vocal finish after lyric cover / surgical splices."""
    v = to_mono(np.asarray(vocals, dtype=np.float32))
    if reference is not None:
        ref = to_mono(np.asarray(reference, dtype=np.float32))
        n = min(len(v), len(ref))
        # Match overall song-level envelope (glue splices to original singer)
        matched = match_spectral_envelope(v[:n], ref[:n], sample_rate=sample_rate, strength=0.55)
        if len(v) > n:
            v = np.concatenate([matched, v[n:]])
        else:
            v = matched

    if compress:
        v = soft_compress(v)
    v = presence_eq(v, sample_rate=sample_rate, amount=0.1)

    if reverb_mix is None:
        src = reference if reference is not None else v
        reverb_mix = estimate_wetness(src, sample_rate=sample_rate)
    v = plate_reverb(v, sample_rate=sample_rate, mix=float(reverb_mix))

    peak = float(np.max(np.abs(v))) if v.size else 0.0
    if peak > 0.98:
        v = v * (0.98 / peak)
    return v.astype(np.float32)


def soft_limit(audio: np.ndarray, ceiling: float = 0.97) -> np.ndarray:
    """Tanh soft clip toward ceiling (master bus)."""
    x = np.asarray(audio, dtype=np.float32)
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    if peak < 1e-8:
        return x
    # Drive so peaks approach ceiling smoothly
    drive = 1.15
    y = np.tanh(x * drive) / np.tanh(drive)
    p2 = float(np.max(np.abs(y)))
    if p2 > ceiling:
        y = y * (ceiling / p2)
    return y.astype(np.float32)


def studio_mix(
    vocals: np.ndarray,
    instrumental: np.ndarray,
    *,
    vocal_gain: float = 1.06,
    instrumental_gain: float = 0.9,
) -> np.ndarray:
    """AICoverGen-style stem balance + soft limit (local, automated)."""
    v = ensure_stereo(to_mono(np.asarray(vocals, dtype=np.float32))) * float(vocal_gain)
    i = ensure_stereo(np.asarray(instrumental, dtype=np.float32)) * float(instrumental_gain)
    n = max(len(v), len(i))
    if len(v) < n:
        v = np.pad(v, ((0, n - len(v)), (0, 0)))
    if len(i) < n:
        i = np.pad(i, ((0, n - len(i)), (0, 0)))
    mixed = v + i
    return soft_limit(mixed, ceiling=0.97)
