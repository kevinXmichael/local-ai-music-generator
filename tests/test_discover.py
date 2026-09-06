from __future__ import annotations

from pathlib import Path

import pytest

from local_ai_music_generator.discover import InputDiscoveryError, discover_jobs


def _touch_audio(path: Path) -> None:
    path.write_bytes(b"not-real-audio")


def test_discover_job_folder(tmp_path: Path) -> None:
    job_dir = tmp_path / "hot-mess"
    job_dir.mkdir()
    _touch_audio(job_dir / "song.m4a")
    (job_dir / "lyrics new.txt").write_text("I'm a hot gangster\n", encoding="utf-8")
    (job_dir / "lyrics original.txt").write_text("I'm a hot mess\n", encoding="utf-8")
    (job_dir / "voice.txt").write_text("male\n", encoding="utf-8")
    (job_dir / "output name.txt").write_text("hot-gangster-cover\n", encoding="utf-8")

    jobs = discover_jobs(tmp_path)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.audio.name == "song.m4a"
    assert job.lyrics_new.name == "lyrics new.txt"
    assert job.lyrics_original is not None
    assert job.voice == "male"
    assert job.output_name == "hot-gangster-cover"


def test_discover_underscored_names(tmp_path: Path) -> None:
    job_dir = tmp_path / "track"
    job_dir.mkdir()
    _touch_audio(job_dir / "audio.mp3")
    (job_dir / "lyrics_new.txt").write_text("new\n", encoding="utf-8")
    (job_dir / "lyrics_original.txt").write_text("old\n", encoding="utf-8")

    jobs = discover_jobs(tmp_path)
    assert len(jobs) == 1
    assert jobs[0].voice == "female"
    assert jobs[0].output_name == "audio"


def test_discover_root_level(tmp_path: Path) -> None:
    _touch_audio(tmp_path / "song.wav")
    (tmp_path / "lyrics new.txt").write_text("x\n", encoding="utf-8")
    jobs = discover_jobs(tmp_path)
    assert len(jobs) == 1
    assert jobs[0].folder == tmp_path.resolve()


def test_discover_missing_raises(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    with pytest.raises(InputDiscoveryError):
        discover_jobs(tmp_path)
