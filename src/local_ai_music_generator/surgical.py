from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from rich.console import Console

from local_ai_music_generator.audio_io import save_audio, to_mono
from local_ai_music_generator.engines.yingmusic import YingMusicCoverEngine
from local_ai_music_generator.lyrics import LyricsDocument
from local_ai_music_generator.lyrics_diff import PhraseEdit, phrase_edits

console = Console()

_NON_ALNUM = re.compile(r"[^a-z0-9\s']+")


@dataclass
class TimedHit:
    start: float
    end: float
    edit: PhraseEdit


def _norm_words(text: str) -> list[str]:
    text = _NON_ALNUM.sub(" ", text.lower())
    return [w for w in text.split() if w]


def find_hits_with_whisper(
    vocals_wav: Path,
    edits: list[PhraseEdit],
) -> list[TimedHit]:
    """Locate edited phrases in the original vocals via faster-whisper."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper fehlt für surgical mode. "
            "pip install faster-whisper"
        ) from exc

    console.print("[bold]ASR[/bold] faster-whisper (sucht geänderte Stellen im Original)…")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _info = model.transcribe(
        str(vocals_wav),
        word_timestamps=True,
        language="en",
        vad_filter=True,
    )

    words: list[tuple[str, float, float]] = []
    for seg in segments:
        if not seg.words:
            continue
        for w in seg.words:
            token = _NON_ALNUM.sub("", (w.word or "").lower()).strip()
            if token:
                words.append((token, float(w.start), float(w.end)))

    hits: list[TimedHit] = []
    for edit in edits:
        needle = _norm_words(edit.search_hint)
        if not needle:
            continue
        # Prefer the distinctive changed span (e.g. "hot mess")
        short = _shortest_unique_needle(edit)
        needles = [short] if short else [needle]
        for nwords in needles:
            hits.extend(_find_needle(words, nwords, edit))

    # Deduplicate overlapping hits (same edit close in time)
    hits.sort(key=lambda h: h.start)
    merged: list[TimedHit] = []
    for hit in hits:
        if merged and hit.start <= merged[-1].end + 0.15 and hit.edit == merged[-1].edit:
            prev = merged[-1]
            merged[-1] = TimedHit(prev.start, max(prev.end, hit.end), prev.edit)
        else:
            merged.append(hit)
    return merged


def _shortest_unique_needle(edit: PhraseEdit) -> list[str] | None:
    """Extract the replaced core words, e.g. hot mess → search 'hot mess'."""
    import difflib

    o = _norm_words(edit.original)
    t = _norm_words(edit.target)
    sm = difflib.SequenceMatcher(a=o, b=t)
    for tag, i1, i2, _j1, _j2 in sm.get_opcodes():
        if tag == "replace" and i2 > i1:
            return o[i1:i2]
    if len(o) <= 4:
        return o
    return None


def _find_needle(
    words: list[tuple[str, float, float]],
    needle: list[str],
    edit: PhraseEdit,
) -> list[TimedHit]:
    hits: list[TimedHit] = []
    n = len(needle)
    if n == 0 or len(words) < n:
        return hits
    for i in range(len(words) - n + 1):
        window = [words[i + k][0] for k in range(n)]
        if window == needle:
            start = words[i][1]
            end = words[i + n - 1][2]
            hits.append(TimedHit(start=start, end=end, edit=edit))
    return hits


def surgical_cover(
    *,
    engine: YingMusicCoverEngine,
    vocals: np.ndarray,
    sample_rate: int,
    original_lyrics: LyricsDocument,
    target_lyrics: LyricsDocument,
    work_dir: Path,
    nfe_step: int = 24,
    pad_seconds: float = 0.45,
) -> tuple[np.ndarray, str]:
    """Keep original vocals; only re-sing the changed phrases and splice them back."""
    work_dir.mkdir(parents=True, exist_ok=True)
    mono = to_mono(np.asarray(vocals, dtype=np.float32))
    vocals_path = work_dir / "vocals_for_asr.wav"
    save_audio(vocals_path, mono, sample_rate)

    edits = phrase_edits(original_lyrics, target_lyrics)
    if not edits:
        console.print("[yellow]Keine Lyric-Differenzen — Original-Vocals bleiben.[/yellow]")
        return mono, "surgical: no edits"

    console.print(f"[bold]Surgical[/bold] {len(edits)} geänderte Phrase(n) — Rest = Originalstimme")
    for e in edits[:8]:
        console.print(f"  • {e.original!r} → {e.target!r}")

    hits = find_hits_with_whisper(vocals_path, edits)
    if not hits:
        raise RuntimeError(
            "ASR hat die geänderten Stellen nicht gefunden. "
            "Prüfe lyrics original/new oder nutze mode=full."
        )

    console.print(f"[bold]Treffer[/bold] {len(hits)} Zeitstellen zum Ersetzen")
    out = mono.copy()
    project_root = engine.home.parent.parent
    # Timbre ref: longer stretch of original voice (keeps identity)
    timbre = mono[: min(len(mono), int(sample_rate * 15))]
    timbre_path = work_dir / "timbre_ref.wav"
    save_audio(timbre_path, timbre, sample_rate)

    for idx, hit in enumerate(hits, start=1):
        start = max(0.0, hit.start - pad_seconds)
        end = min(len(mono) / sample_rate, hit.end + pad_seconds)
        # Ensure minimum window for the model
        if end - start < 1.2:
            mid = 0.5 * (start + end)
            start = max(0.0, mid - 0.7)
            end = min(len(mono) / sample_rate, mid + 0.7)

        i0 = int(start * sample_rate)
        i1 = int(end * sample_rate)
        clip = mono[i0:i1]
        part = work_dir / f"hit_{idx:02d}"
        part.mkdir(parents=True, exist_ok=True)
        melody_path = part / "melody.wav"
        out_path = part / "sung.wav"
        save_audio(melody_path, clip, sample_rate)

        console.print(
            f"[cyan]Hit {idx}/{len(hits)}[/cyan] "
            f"{start:.2f}–{end:.2f}s · {hit.edit.original!r} → {hit.edit.target!r}"
        )
        engine._run_infer(
            project_root=project_root,
            ref=str(timbre_path.resolve()),
            melody=str(melody_path.resolve()),
            ref_text=hit.edit.original,
            target_text=hit.edit.target,
            output=str(out_path.resolve()),
            nfe_step=nfe_step,
        )
        import soundfile as sf

        sung, sung_sr = sf.read(str(out_path), always_2d=False)
        sung = to_mono(np.asarray(sung, dtype=np.float32))
        if sung_sr != sample_rate:
            import librosa

            sung = librosa.resample(sung, orig_sr=sung_sr, target_sr=sample_rate)

        # Fit into original slot with short crossfade
        slot = i1 - i0
        if len(sung) > slot:
            sung = sung[:slot]
        elif len(sung) < slot:
            sung = np.pad(sung, (0, slot - len(sung)))

        fade = min(int(0.04 * sample_rate), slot // 4, len(sung) // 4)
        if fade > 1:
            ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
            sung[:fade] = sung[:fade] * ramp + out[i0 : i0 + fade] * (1.0 - ramp)
            sung[-fade:] = sung[-fade:] * (1.0 - ramp) + out[i1 - fade : i1] * ramp
        out[i0:i1] = sung

    note = f"surgical: {len(hits)} splices, original voice elsewhere"
    return out.astype(np.float32), note
