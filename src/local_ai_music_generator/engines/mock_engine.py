from __future__ import annotations

from pathlib import Path

import numpy as np

from local_ai_music_generator.config import VoiceGender
from local_ai_music_generator.engines import CoverResult
from local_ai_music_generator.engines.voice_gender import apply_voice_gender
from local_ai_music_generator.lyrics import LyricsDocument


class MockLyricCoverEngine:
    """Deterministic offline engine for tests/CI.

    Does not invent new phonemes — it applies gender shaping and a tiny amplitude
    envelope so the pipeline can be exercised end-to-end without GPU models.
    """

    name = "mock"

    def available(self) -> bool:
        return True

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
        work_dir.mkdir(parents=True, exist_ok=True)
        meta = work_dir / "mock_cover_meta.txt"
        meta.write_text(
            "original:\n"
            + original_lyrics.plain()
            + "\n\ntarget:\n"
            + target_lyrics.plain()
            + f"\n\nvoice={voice}\n",
            encoding="utf-8",
        )
        shaped = apply_voice_gender(vocals, sample_rate, voice, strength=0.85)
        # Soft gate so silence stays silence
        env = np.clip(np.abs(shaped) * 8.0, 0.0, 1.0)
        out = (shaped * (0.85 + 0.15 * env)).astype(np.float32)
        changed = original_lyrics.plain() != target_lyrics.plain()
        note = "mock engine: gender-shaped template vocals (no neural lyric synthesis)."
        if changed:
            note += " Lyric text differs — install YingMusic for real re-singing."
        return CoverResult(
            vocals=out,
            sample_rate=sample_rate,
            engine=self.name,
            notes=note,
        )
