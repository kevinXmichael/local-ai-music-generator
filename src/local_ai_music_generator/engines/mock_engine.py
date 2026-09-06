from __future__ import annotations

from pathlib import Path

import numpy as np

from local_ai_music_generator.config import VoiceGender
from local_ai_music_generator.engines.base import CoverResult
from local_ai_music_generator.engines.voice_gender import apply_voice_gender
from local_ai_music_generator.lyrics import LyricsDocument


class MockLyricCoverEngine:
    """CI/smoke engine — does NOT re-sing lyrics. Use YingMusic for real covers."""

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
        apply_gender: bool = False,
        source_mix: Path | None = None,
    ) -> CoverResult:
        del source_mix  # unused in mock
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
        out = np.asarray(vocals, dtype=np.float32)
        if apply_gender:
            out = apply_voice_gender(out, sample_rate, voice, strength=0.5)
        changed = original_lyrics.plain() != target_lyrics.plain()
        note = (
            "MOCK: keine echten neuen Lyrics. "
            "Für echte Covers: ./scripts/generate.sh setup-yingmusic"
        )
        if changed:
            note += " (Lyrics unterscheiden sich vom Original — Mock ignoriert das.)"
        return CoverResult(
            vocals=out,
            sample_rate=sample_rate,
            engine=self.name,
            notes=note,
        )
