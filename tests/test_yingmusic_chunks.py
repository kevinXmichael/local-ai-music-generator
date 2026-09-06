from __future__ import annotations

import numpy as np

from local_ai_music_generator.engines.yingmusic import crossfade_concat, split_phrases_for_chunks


def test_split_phrases_for_chunks() -> None:
    text = "a|b|c|d"
    parts = split_phrases_for_chunks(text, 2)
    assert len(parts) == 2
    assert "a" in parts[0]
    assert "d" in parts[1]


def test_crossfade_concat() -> None:
    sr = 1000
    a = np.ones(500, dtype=np.float32)
    b = np.ones(500, dtype=np.float32) * 0.5
    out = crossfade_concat([a, b], sr, fade_ms=50)
    assert len(out) < 1000
    assert len(out) > 900
