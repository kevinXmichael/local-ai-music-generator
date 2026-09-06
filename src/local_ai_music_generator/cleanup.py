from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

# infer_api loads ASLP-lab/YingMusic-Singer — Plus-Cache ist Duplikat/Altlast
HF_HUB = Path.home() / ".cache" / "huggingface" / "hub"
UNUSED_HF_REPOS = (
    "models--ASLP-lab--YingMusic-Singer-Plus",
)
KEEP_HF_REPOS = (
    "models--ASLP-lab--YingMusic-Singer",
)


@dataclass
class CleanupResult:
    freed_bytes: int
    removed: list[str]
    kept: list[str]
    notes: list[str]


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    if path.is_file():
        return path.stat().st_size
    for p in path.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return total


def format_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(n)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


def cleanup_caches(
    project_root: Path,
    *,
    keep_work: int = 2,
    delete_unused_hf: bool = True,
    dry_run: bool = False,
) -> CleanupResult:
    """Remove duplicate HF model caches and old .work job folders."""
    removed: list[str] = []
    kept: list[str] = []
    notes: list[str] = []
    freed = 0

    # 1) Unused Hugging Face repos
    for name in UNUSED_HF_REPOS:
        path = HF_HUB / name
        size = _dir_size(path)
        if not path.exists():
            notes.append(f"HF {name}: nicht vorhanden")
            continue
        if delete_unused_hf:
            label = f"HF unused {name} ({format_bytes(size)})"
            if dry_run:
                notes.append(f"würde löschen: {label}")
            else:
                shutil.rmtree(path, ignore_errors=True)
                removed.append(label)
                freed += size
        else:
            kept.append(f"HF {name} ({format_bytes(size)})")

    for name in KEEP_HF_REPOS:
        path = HF_HUB / name
        if path.exists():
            kept.append(f"HF keep {name} ({format_bytes(_dir_size(path))})")

    # 2) Old .work directories (keep newest N)
    work = project_root / ".work"
    if work.is_dir():
        jobs = sorted(
            [p for p in work.iterdir() if p.is_dir() and not p.name.startswith(".")],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for path in jobs[:keep_work]:
            kept.append(f".work/{path.name} ({format_bytes(_dir_size(path))})")
        for path in jobs[keep_work:]:
            size = _dir_size(path)
            label = f".work/{path.name} ({format_bytes(size)})"
            if dry_run:
                notes.append(f"würde löschen: {label}")
            else:
                shutil.rmtree(path, ignore_errors=True)
                removed.append(label)
                freed += size
    else:
        notes.append(".work: leer / fehlt")

    return CleanupResult(freed_bytes=freed, removed=removed, kept=kept, notes=notes)
