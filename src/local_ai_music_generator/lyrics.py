from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_TIMESTAMP_RE = re.compile(
    r"^\d{1,2}:\d{2}(?::\d{2})?[.,]\d{1,3}\s*-->\s*\d{1,2}:\d{2}(?::\d{2})?[.,]\d{1,3}"
)
_INDEX_RE = re.compile(r"^\d+$")
_LRC_RE = re.compile(r"^\[\d{1,2}:\d{2}(?:\.\d{1,3})?\]\s*(.*)$")
_SECTION_RE = re.compile(r"^\[.+\]\s*$")


@dataclass(frozen=True)
class LyricsDocument:
    """Normalized singing lyrics for model input."""

    text: str
    source: Path | None = None

    @property
    def phrase_pipe(self) -> str:
        """YingMusic-style phrase separators using `|` between lines/phrases."""
        phrases = [p.strip() for p in self.lines if p.strip() and not _SECTION_RE.match(p.strip())]
        return "|".join(phrases)

    @property
    def lines(self) -> list[str]:
        return [ln.rstrip() for ln in self.text.splitlines()]

    def plain(self) -> str:
        parts: list[str] = []
        for line in self.lines:
            s = line.strip()
            if not s or _SECTION_RE.match(s):
                continue
            parts.append(s)
        return "\n".join(parts)


def load_lyrics(path: Path) -> LyricsDocument:
    raw = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".srt":
        text = _parse_srt(raw)
    elif suffix == ".lrc":
        text = _parse_lrc(raw)
    else:
        text = _normalize_plain(raw)
    return LyricsDocument(text=text.strip() + "\n", source=path)


def _normalize_plain(raw: str) -> str:
    lines: list[str] = []
    for line in raw.splitlines():
        # Skip common Genius / ASR junk
        if line.strip().startswith("You might also like"):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def _parse_srt(raw: str) -> str:
    """Accept real timed SRT or lyric sheets wrongly named .srt."""
    if "-->" not in raw:
        return _normalize_plain(raw)

    phrases: list[str] = []
    block: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            if block:
                phrases.append(" ".join(block))
                block = []
            continue
        if _INDEX_RE.match(s) or _TIMESTAMP_RE.match(s):
            continue
        block.append(s)
    if block:
        phrases.append(" ".join(block))
    return "\n".join(phrases)


def _parse_lrc(raw: str) -> str:
    phrases: list[str] = []
    for line in raw.splitlines():
        m = _LRC_RE.match(line.strip())
        if m:
            text = m.group(1).strip()
            if text:
                phrases.append(text)
        elif line.strip() and not line.strip().startswith("["):
            phrases.append(line.strip())
    return "\n".join(phrases)


def apply_replacements(text: str, replacements: dict[str, str]) -> str:
    """Case-insensitive whole-phrase replacements (longest keys first)."""
    result = text
    for old, new in sorted(replacements.items(), key=lambda kv: len(kv[0]), reverse=True):
        pattern = re.compile(re.escape(old), re.IGNORECASE)

        def _sub(match: re.Match[str], replacement: str = new) -> str:
            src = match.group(0)
            if src.isupper():
                return replacement.upper()
            if src[0].isupper():
                return replacement[:1].upper() + replacement[1:]
            return replacement

        result = pattern.sub(_sub, result)
    return result
