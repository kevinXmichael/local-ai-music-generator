#!/usr/bin/env python3
"""Run YingMusic infer_api with macOS MPS/CPU device selection."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _sanitize_mps_env() -> None:
    """Drop invalid MPS watermark ratios (cause: invalid low watermark ratio 1.4)."""
    for key in ("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "PYTORCH_MPS_LOW_WATERMARK_RATIO"):
        val = os.environ.get(key)
        if val is None:
            continue
        try:
            ratio = float(val)
        except ValueError:
            os.environ.pop(key, None)
            print(f"[INFO] unset invalid {key}={val!r}")
            continue
        if not 0.0 <= ratio <= 1.0:
            os.environ.pop(key, None)
            print(f"[INFO] unset invalid {key}={val!r}")


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    home = project / "vendor" / "YingMusic-Singer-Plus"
    if not (home / "infer_api.py").is_file():
        raise SystemExit(f"YingMusic missing at {home}. Run setup-yingmusic first.")

    _sanitize_mps_env()
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    sys.path.insert(0, str(home))
    os.chdir(home)

    import torch

    import infer_api

    preferred = os.environ.get("YINGMUSIC_DEVICE", "auto").strip().lower()

    def get_device() -> str:
        if preferred in {"cuda", "cuda:0"} and torch.cuda.is_available():
            return "cuda:0"
        if preferred == "cpu":
            return "cpu"
        if preferred == "mps":
            if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                return "mps"
            print("[WARN] MPS requested but unavailable — using CPU")
            return "cpu"
        if torch.cuda.is_available():
            return "cuda:0"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    infer_api.get_device = get_device  # type: ignore[method-assign]
    print(f"[INFO] device={get_device()}")

    _orig_get_model = infer_api.get_model

    def get_model_safe():
        try:
            return _orig_get_model()
        except RuntimeError as exc:
            msg = str(exc).lower()
            if "watermark" not in msg and "mps" not in msg:
                raise
            print(f"[WARN] MPS load failed ({exc}) — staying on CPU")
            # from_pretrained may already have assigned CPU weights to _model
            model = getattr(infer_api, "_model", None)
            if model is not None:
                model.eval()
                return model
            os.environ["YINGMUSIC_DEVICE"] = "cpu"
            infer_api.get_device = lambda: "cpu"  # type: ignore[method-assign]
            infer_api._model = None  # type: ignore[attr-defined]
            return _orig_get_model()

    infer_api.get_model = get_model_safe  # type: ignore[assignment]
    args = infer_api.parse_args()
    infer_api.synthesize(args)


if __name__ == "__main__":
    main()
