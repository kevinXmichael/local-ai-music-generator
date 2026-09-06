from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from local_ai_music_generator.audio_io import mix_tracks, save_audio, to_mono
from local_ai_music_generator.config import GenerateRequest, Paths
from local_ai_music_generator.engines.mock_engine import MockLyricCoverEngine
from local_ai_music_generator.engines.separator import SimpleHpssSeparator
from local_ai_music_generator.engines.voice_gender import apply_voice_gender
from local_ai_music_generator.lyrics import apply_replacements, load_lyrics
from local_ai_music_generator.pipeline import generate, sanitize_output_name


@pytest.fixture()
def project(tmp_path: Path) -> Paths:
    (tmp_path / "MUSIC_INPUT").mkdir()
    (tmp_path / "MUSIC_OUTPUT").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n", encoding="utf-8")
    return Paths(root=tmp_path)


def test_sanitize_output_name() -> None:
    assert sanitize_output_name("Hot Gangster Cover!") == "Hot-Gangster-Cover"
    assert sanitize_output_name("  ") == "cover"


def test_load_plain_and_srt(tmp_path: Path) -> None:
    plain = tmp_path / "a.txt"
    plain.write_text("[Chorus]\nI'm a hot gangster\n\nYeah\n", encoding="utf-8")
    doc = load_lyrics(plain)
    assert "hot gangster" in doc.plain()
    assert "Chorus" not in doc.phrase_pipe

    srt = tmp_path / "b.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello world\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\nHot mess\n",
        encoding="utf-8",
    )
    assert load_lyrics(srt).plain() == "Hello world\nHot mess"


def test_apply_replacements() -> None:
    text = "I'm a hot mess (Whoa)\nI'm a Hot Mess"
    out = apply_replacements(text, {"hot mess": "hot gangster"})
    assert "hot gangster" in out.lower()
    assert "hot mess" not in out.lower()


def test_mix_and_gender() -> None:
    sr = 22050
    t = np.linspace(0, 1, sr, endpoint=False)
    vocals = (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    inst = (0.1 * np.sin(2 * np.pi * 110 * t)).astype(np.float32)
    mixed = mix_tracks(vocals, inst)
    assert mixed.shape[1] == 2
    female = apply_voice_gender(vocals, sr, "female")
    male = apply_voice_gender(vocals, sr, "male")
    assert len(female) == len(vocals)
    assert len(male) == len(vocals)
    assert not np.allclose(female, male)


def test_hpss_separator(tmp_path: Path) -> None:
    sr = 22050
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sep = SimpleHpssSeparator().separate(audio, sr, tmp_path / "sep")
    assert len(sep.vocals) == len(audio)
    assert len(sep.instrumental) == len(audio)


def test_mock_engine_cover(tmp_path: Path) -> None:
    from local_ai_music_generator.lyrics import LyricsDocument

    sr = 16000
    vocals = (0.1 * np.random.randn(sr)).astype(np.float32)
    engine = MockLyricCoverEngine()
    result = engine.cover(
        vocals=vocals,
        sample_rate=sr,
        original_lyrics=LyricsDocument("I'm a hot mess\n"),
        target_lyrics=LyricsDocument("I'm a hot gangster\n"),
        voice="female",
        work_dir=tmp_path / "c",
    )
    assert result.engine == "mock"
    assert result.vocals.shape[0] == vocals.shape[0]
    assert (tmp_path / "c" / "mock_cover_meta.txt").is_file()


def test_end_to_end_generate(project: Paths, tmp_path: Path) -> None:
    sr = 22050
    t = np.linspace(0, 1.0, sr, endpoint=False)
    audio = (0.25 * np.sin(2 * np.pi * 330 * t)).astype(np.float32)
    audio_path = project.music_input / "tone.wav"
    save_audio(audio_path, audio, sr)

    original = project.music_input / "original.txt"
    target = project.music_input / "target.txt"
    original.write_text("I'm a hot mess\n", encoding="utf-8")
    target.write_text("I'm a hot gangster\n", encoding="utf-8")

    result = generate(
        project,
        GenerateRequest(
            audio=audio_path,
            lyrics=target,
            original_lyrics=original,
            output_name="hot-gangster-demo",
            voice="female",
            engine="mock",
            keep_work_files=True,
        ),
    )
    assert result.output_path.is_file()
    assert result.engine == "mock"
    data, out_sr = sf.read(str(result.output_path))
    assert out_sr > 0
    assert to_mono(np.asarray(data)).shape[0] > 0
    assert (project.music_output / "hot-gangster-demo.json").is_file()
