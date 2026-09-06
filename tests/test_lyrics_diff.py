from __future__ import annotations

from local_ai_music_generator.lyrics import LyricsDocument
from local_ai_music_generator.lyrics_diff import PhraseEdit, phrase_edits, should_use_surgical
from local_ai_music_generator.surgical import search_needle, synthesis_pair


def test_synthesis_pair_strips_adlibs() -> None:
    edit = PhraseEdit(
        original="I'm a hot mess (Whoa-oh-oh, whoa-oh-oh-oh)",
        target="I'm a hot gangster (Whoa-oh-oh, whoa-oh-oh-oh)",
    )
    ref, tgt = synthesis_pair(edit)
    assert "whoa" not in ref.lower()
    assert "whoa" not in tgt.lower()
    assert "mess" in ref
    assert "gangster" in tgt
    assert search_needle(edit) == ["hot", "mess"]


def test_phrase_edits_hot_mess() -> None:
    original = LyricsDocument(
        "I'm a hot mess (Whoa)\nI am powerful\nI'm a hot mess\n"
    )
    target = LyricsDocument(
        "I'm a hot gangster (Whoa)\nI am powerful\nI'm a hot gangster\n"
    )
    edits = phrase_edits(original, target)
    assert len(edits) == 2
    assert "mess" in edits[0].original.lower()
    assert "gangster" in edits[0].target.lower()
    assert should_use_surgical(original, target)


def test_should_not_surgical_full_rewrite() -> None:
    original = LyricsDocument("aaa|bbb|ccc|ddd")
    target = LyricsDocument("xxx|yyy|zzz|www")
    assert not should_use_surgical(original, target)
