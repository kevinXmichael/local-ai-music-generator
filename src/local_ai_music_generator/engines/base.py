from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from local_ai_music_generator.config import VoiceGender
from local_ai_music_generator.lyrics import LyricsDocument


@dataclass
class SeparationResult:
    vocals: np.ndarray
    instrumental: np.ndarray
    sample_rate: int


@dataclass
class CoverResult:
    vocals: np.ndarray
    sample_rate: int
    engine: str
    notes: str = ""


class Separator(Protocol):
    name: str

    def separate(self, audio: np.ndarray, sample_rate: int, work_dir: Path) -> SeparationResult: ...


class LyricCoverEngine(Protocol):
    name: str

    def available(self) -> bool: ...

    def cover(
        self,
        *,
        vocals: np.ndarray,
        sample_rate: int,
        original_lyrics: LyricsDocument,
        target_lyrics: LyricsDocument,
        voice: VoiceGender,
        work_dir: Path,
    ) -> CoverResult: ...
