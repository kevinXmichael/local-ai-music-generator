from __future__ import annotations

import re
from dataclasses import dataclass

from local_ai_music_generator.lyrics import LyricsDocument

_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", s.strip().lower())


@dataclass(frozen=True)
class PhraseEdit:
    """One lyric line/phrase that differs between original and target."""

    original: str
    target: str

    @property
    def search_hint(self) -> str:
        """Shorter needle for ASR search (drop parenthetical ad-libs when possible)."""
        base = re.sub(r"\([^)]*\)", "", self.original).strip()
        return base or self.original


def phrase_edits(original: LyricsDocument, target: LyricsDocument) -> list[PhraseEdit]:
    """Pair differing phrases by index (same song structure assumed)."""
    o = [p.strip() for p in original.phrase_pipe.split("|") if p.strip()]
    t = [p.strip() for p in target.phrase_pipe.split("|") if p.strip()]
    if len(o) != len(t):
        # Fall back: unique replacements via simple substring scan on full plain text
        return _edits_from_plain(original.plain(), target.plain())
    out: list[PhraseEdit] = []
    for a, b in zip(o, t, strict=True):
        if _norm(a) != _norm(b):
            out.append(PhraseEdit(original=a, target=b))
    return out


def _edits_from_plain(original: str, target: str) -> list[PhraseEdit]:
    """Best-effort: find replaced short phrases when line counts diverge."""
    # Prefer multi-word diffs like "hot mess" → "hot gangster"
    o_words = original.lower().split()
    t_words = target.lower().split()
    # If target is original with substitutions, SequenceMatcher opcodes
    import difflib

    sm = difflib.SequenceMatcher(a=o_words, b=t_words)
    edits: list[PhraseEdit] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "replace":
            continue
        old = " ".join(o_words[i1:i2]).strip()
        new = " ".join(t_words[j1:j2]).strip()
        if old and new and old != new:
            edits.append(PhraseEdit(original=old, target=new))
    return edits


def should_use_surgical(original: LyricsDocument, target: LyricsDocument) -> bool:
    """True when most of the song stays the same (word/line edits only)."""
    o = [p.strip() for p in original.phrase_pipe.split("|") if p.strip()]
    t = [p.strip() for p in target.phrase_pipe.split("|") if p.strip()]
    if not o or not t:
        return False
    if abs(len(o) - len(t)) > max(2, len(o) // 5):
        return False
    n = min(len(o), len(t))
    same = sum(1 for i in range(n) if _norm(o[i]) == _norm(t[i]))
    changed = n - same
    return changed > 0 and (changed / n) <= 0.7 and bool(phrase_edits(original, target))
