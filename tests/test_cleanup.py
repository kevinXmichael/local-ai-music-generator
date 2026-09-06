from __future__ import annotations

from pathlib import Path

from local_ai_music_generator.cleanup import cleanup_caches, format_bytes


def test_format_bytes() -> None:
    assert format_bytes(500) == "500.0 B"
    assert "KB" in format_bytes(2048)


def test_cleanup_work_and_unused_hf(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "proj"
    work = root / ".work"
    work.mkdir(parents=True)
    older = work / "old-job"
    newer = work / "new-job"
    older.mkdir()
    newer.mkdir()
    (older / "a.bin").write_bytes(b"x" * 1000)
    (newer / "b.bin").write_bytes(b"y" * 500)
    # force mtime order
    import os
    import time

    now = time.time()
    os.utime(older, (now - 100, now - 100))
    os.utime(newer, (now, now))

    fake_hub = tmp_path / "hub"
    unused = fake_hub / "models--ASLP-lab--YingMusic-Singer-Plus"
    keep = fake_hub / "models--ASLP-lab--YingMusic-Singer"
    unused.mkdir(parents=True)
    keep.mkdir(parents=True)
    (unused / "big.bin").write_bytes(b"z" * 2000)
    (keep / "small.bin").write_bytes(b"k" * 100)

    monkeypatch.setattr("local_ai_music_generator.cleanup.HF_HUB", fake_hub)

    result = cleanup_caches(root, keep_work=1, delete_unused_hf=True, dry_run=False)
    assert not older.exists()
    assert newer.exists()
    assert not unused.exists()
    assert keep.exists()
    assert result.freed_bytes >= 3000
