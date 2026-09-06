from __future__ import annotations

import difflib
import json
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
_PAREN = re.compile(r"\([^)]*\)")


@dataclass
class TimedHit:
    start: float
    end: float
    edit: PhraseEdit
    ref_text: str
    target_text: str


def _norm_words(text: str) -> list[str]:
    text = _NON_ALNUM.sub(" ", text.lower())
    return [w for w in text.split() if w]


def _strip_parens(text: str) -> str:
    return _WS_COLLAPSE.sub(" ", _PAREN.sub(" ", text)).strip()


_WS_COLLAPSE = re.compile(r"\s+")


def _token_close(a: str, b: str, *, fuzzy: bool = True) -> bool:
    """Exact or near match so ASR slips like 'mess'/'miss' still hit."""
    if a == b:
        return True
    if not fuzzy:
        return False
    # Common lyric ASR slips for this project
    aliases = {
        "mess": {"miss", "mass", "mes", "mas"},
        "hot": {"hut", "hod"},
    }
    if b in aliases and a in aliases[b]:
        return True
    if a in aliases and b in aliases[a]:
        return True
    if len(a) < 3 or len(b) < 3:
        return False
    if abs(len(a) - len(b)) > 2:
        return False
    return difflib.SequenceMatcher(a=a, b=b).ratio() >= 0.78


def synthesis_pair(edit: PhraseEdit) -> tuple[str, str]:
    """Lyric texts for YingMusic — no ad-libs; keep light left context."""
    o = _norm_words(_strip_parens(edit.original))
    t = _norm_words(_strip_parens(edit.target))
    if not o or not t:
        return _strip_parens(edit.original), _strip_parens(edit.target)

    sm = difflib.SequenceMatcher(a=o, b=t)
    o_start = o_end = None
    t_start = t_end = None
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if o_start is None:
            o_start, t_start = i1, j1
        o_end, t_end = i2, j2

    if o_start is None or o_end is None or t_start is None or t_end is None:
        return " ".join(o), " ".join(t)

    # Prefer including up to 3 leading shared words ("I'm a hot mess")
    lead = min(3, o_start, t_start)
    o_slice = o[o_start - lead : o_end]
    t_slice = t[t_start - lead : t_end]
    if not o_slice or not t_slice:
        return " ".join(o), " ".join(t)
    return " ".join(o_slice), " ".join(t_slice)


def search_needle(edit: PhraseEdit) -> list[str]:
    """Short distinctive span to find in ASR words (e.g. hot mess)."""
    o = _norm_words(_strip_parens(edit.original))
    t = _norm_words(_strip_parens(edit.target))
    sm = difflib.SequenceMatcher(a=o, b=t)
    for tag, i1, i2, _j1, _j2 in sm.get_opcodes():
        if tag == "replace" and i2 > i1:
            span = o[i1:i2]
            # Prefer 2-word window when possible
            if len(span) == 1 and i1 > 0:
                return o[i1 - 1 : i2]
            return span
    if 1 <= len(o) <= 4:
        return o
    return o[:3] if o else []


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
    # small + no VAD: intro/chorus words are less often dropped
    model = WhisperModel("small", device="cpu", compute_type="int8")
    # Build a short prompt from edit cores so late choruses stay on-vocab
    prompt_bits: list[str] = []
    for edit in edits[:6]:
        ref_t, _tgt = synthesis_pair(edit)
        if ref_t and ref_t not in prompt_bits:
            prompt_bits.append(ref_t)
    initial_prompt = ". ".join(prompt_bits[:4]) if prompt_bits else None

    segments, _info = model.transcribe(
        str(vocals_wav),
        word_timestamps=True,
        language="en",
        vad_filter=False,
        condition_on_previous_text=True,
        initial_prompt=initial_prompt,
        beam_size=5,
        best_of=5,
    )

    words: list[tuple[str, float, float]] = []
    for seg in segments:
        if not seg.words:
            continue
        for w in seg.words:
            token = _NON_ALNUM.sub("", (w.word or "").lower()).strip()
            if token:
                words.append((token, float(w.start), float(w.end)))

    # Unique needles (many chorus lines share the same core edit)
    unique: list[tuple[list[str], PhraseEdit, str, str]] = []
    seen: set[tuple[str, ...]] = set()
    for edit in edits:
        needle = search_needle(edit)
        if not needle:
            continue
        key = tuple(needle)
        if key in seen:
            continue
        seen.add(key)
        ref_text, target_text = synthesis_pair(edit)
        unique.append((needle, edit, ref_text, target_text))

    hits: list[TimedHit] = []
    for needle, edit, ref_text, target_text in unique:
        exact = _find_needle(
            words,
            needle,
            edit,
            ref_text=ref_text,
            target_text=target_text,
            fuzzy=False,
        )
        fuzzy = _find_needle(
            words,
            needle,
            edit,
            ref_text=ref_text,
            target_text=target_text,
            fuzzy=True,
        )
        hits.extend(exact)
        # Only add fuzzy hits that don't overlap an exact hit
        for fh in fuzzy:
            if any(abs(fh.start - eh.start) < 0.35 for eh in exact):
                continue
            hits.extend([fh])

    hits.sort(key=lambda h: h.start)
    merged: list[TimedHit] = []
    for hit in hits:
        # Drop ASR ghosts (too short) and runaway windows (ad-lib false positives)
        dur = hit.end - hit.start
        if dur < 0.28 or dur > 3.5:
            continue
        # Any overlapping window = one splice (avoid double foreign voice)
        if merged and hit.start <= merged[-1].end + 0.2:
            prev = merged[-1]
            merged_end = max(prev.end, hit.end)
            if merged_end - prev.start > 3.5:
                merged.append(hit)
                continue
            merged[-1] = TimedHit(
                prev.start,
                merged_end,
                prev.edit,
                prev.ref_text,
                prev.target_text,
            )
        else:
            merged.append(hit)
    return merged


def _find_needle(
    words: list[tuple[str, float, float]],
    needle: list[str],
    edit: PhraseEdit,
    *,
    ref_text: str,
    target_text: str,
    fuzzy: bool = True,
) -> list[TimedHit]:
    hits: list[TimedHit] = []
    n = len(needle)
    if n == 0 or len(words) < n:
        return hits
    for i in range(len(words) - n + 1):
        window = [words[i + k][0] for k in range(n)]
        if all(_token_close(window[k], needle[k], fuzzy=fuzzy) for k in range(n)):
            start = words[i][1]
            end = words[i + n - 1][2]
            # Pull in leading context words that belong to the synth phrase
            lead = _norm_words(ref_text)
            if len(lead) > n:
                extra = len(lead) - n
                j = max(0, i - extra)
                # only extend if those ASR words roughly match lead prefix
                prefix = [words[j + k][0] for k in range(i - j)]
                want = lead[: i - j]
                if prefix and all(
                    _token_close(prefix[k], want[k], fuzzy=fuzzy) for k in range(len(prefix))
                ):
                    start = words[j][1]
            hits.append(
                TimedHit(
                    start=start,
                    end=end,
                    edit=edit,
                    ref_text=ref_text,
                    target_text=target_text,
                )
            )
    return hits


def _match_rms(sung: np.ndarray, reference: np.ndarray) -> np.ndarray:
    ref_rms = float(np.sqrt(np.mean(np.square(reference)) + 1e-12))
    sung_rms = float(np.sqrt(np.mean(np.square(sung)) + 1e-12))
    if sung_rms < 1e-8 or ref_rms < 1e-8:
        return sung
    return sung * np.float32(ref_rms / sung_rms)


def _fit_length(audio: np.ndarray, n: int) -> np.ndarray:
    if len(audio) == n:
        return audio
    if len(audio) > n:
        return audio[:n]
    return np.pad(audio, (0, n - len(audio)))


def surgical_cover(
    *,
    engine: YingMusicCoverEngine,
    vocals: np.ndarray,
    sample_rate: int,
    original_lyrics: LyricsDocument,
    target_lyrics: LyricsDocument,
    work_dir: Path,
    nfe_step: int = 24,
    context_before: float = 0.9,
    context_after: float = 0.25,
    splice_pad: float = 0.06,
) -> tuple[np.ndarray, str]:
    """Keep original vocals; re-sing only the changed core and splice it back.

    Melody context is wider for the model, but only the core word span is
    written back — ad-libs (whoa/hey) stay the original singer.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    mono = to_mono(np.asarray(vocals, dtype=np.float32))
    vocals_path = work_dir / "vocals_for_asr.wav"
    save_audio(vocals_path, mono, sample_rate)
    duration = len(mono) / sample_rate

    edits = phrase_edits(original_lyrics, target_lyrics)
    if not edits:
        console.print("[yellow]Keine Lyric-Differenzen — Original-Vocals bleiben.[/yellow]")
        return mono, "surgical: no edits"

    console.print(f"[bold]Surgical[/bold] {len(edits)} geänderte Phrase(n) — Rest = Originalstimme")
    for e in edits[:8]:
        ref_t, tgt_t = synthesis_pair(e)
        console.print(f"  • {ref_t!r} → {tgt_t!r}")

    hits = find_hits_with_whisper(vocals_path, edits)
    if not hits:
        raise RuntimeError(
            "ASR hat die geänderten Stellen nicht gefunden. "
            "Prüfe lyrics original/new oder nutze mode=full."
        )

    (work_dir / "hits.json").write_text(
        json.dumps(
            [
                {
                    "start": h.start,
                    "end": h.end,
                    "ref": h.ref_text,
                    "target": h.target_text,
                }
                for h in hits
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    console.print(
        f"[bold]Treffer[/bold] {len(hits)} Zeitstellen "
        f"(nur Kernwort, Ad-libs bleiben original)"
    )
    out = mono.copy()
    project_root = engine.home.parent.parent

    for idx, hit in enumerate(hits, start=1):
        # Wide window for model melody/timbre; narrow window for splice
        model_start = max(0.0, hit.start - context_before)
        model_end = min(duration, hit.end + context_after)
        if model_end - model_start < 1.2:
            mid = 0.5 * (hit.start + hit.end)
            model_start = max(0.0, mid - 0.7)
            model_end = min(duration, mid + 0.7)

        splice_start = max(model_start, hit.start - splice_pad)
        splice_end = min(model_end, hit.end + splice_pad)

        m0 = int(model_start * sample_rate)
        m1 = int(model_end * sample_rate)
        s0 = int(splice_start * sample_rate)
        s1 = int(splice_end * sample_rate)
        clip = mono[m0:m1]
        if len(clip) < sample_rate // 4:
            continue

        part = work_dir / f"hit_{idx:02d}"
        part.mkdir(parents=True, exist_ok=True)
        melody_path = part / "melody.wav"
        # Local timbre = same clip (identity match; avoids "other singer" insert)
        timbre_path = part / "timbre.wav"
        out_path = part / "sung.wav"
        save_audio(melody_path, clip, sample_rate)
        save_audio(timbre_path, clip, sample_rate)

        console.print(
            f"[cyan]Hit {idx}/{len(hits)}[/cyan] "
            f"core {hit.start:.2f}–{hit.end:.2f}s · "
            f"{hit.ref_text!r} → {hit.target_text!r}"
        )
        engine._run_infer(
            project_root=project_root,
            ref=str(timbre_path.resolve()),
            melody=str(melody_path.resolve()),
            ref_text=hit.ref_text,
            target_text=hit.target_text,
            output=str(out_path.resolve()),
            nfe_step=nfe_step,
        )
        import soundfile as sf

        sung, sung_sr = sf.read(str(out_path), always_2d=False)
        sung = to_mono(np.asarray(sung, dtype=np.float32))
        if sung_sr != sample_rate:
            import librosa

            sung = librosa.resample(sung, orig_sr=sung_sr, target_sr=sample_rate)

        # Map core span from model window → sung (lengths may differ)
        clip_len = max(1, m1 - m0)
        ratio = len(sung) / clip_len
        rel0 = s0 - m0
        rel1 = s1 - m0
        sung_i0 = int(rel0 * ratio)
        sung_i1 = int(rel1 * ratio)
        sung_i0 = max(0, min(sung_i0, len(sung) - 1))
        sung_i1 = max(sung_i0 + 1, min(sung_i1, len(sung)))
        piece = sung[sung_i0:sung_i1]
        slot = s1 - s0
        piece = _fit_length(piece, slot)
        # Timbre glue: pull YingMusic insert toward original singer (RVC-lite)
        from local_ai_music_generator.polish import match_spectral_envelope

        piece = match_spectral_envelope(
            piece,
            mono[s0:s1],
            sample_rate=sample_rate,
            strength=0.8,
        )
        piece = _fit_length(piece, slot)
        piece = _match_rms(piece, mono[s0:s1])

        fade = min(int(0.09 * sample_rate), slot // 3, len(piece) // 3)
        if fade > 1:
            ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
            piece[:fade] = piece[:fade] * ramp + out[s0 : s0 + fade] * (1.0 - ramp)
            piece[-fade:] = piece[-fade:] * (1.0 - ramp) + out[s1 - fade : s1] * ramp
        out[s0:s1] = piece

    note = f"surgical: {len(hits)} core splices, original voice elsewhere"
    return out.astype(np.float32), note
