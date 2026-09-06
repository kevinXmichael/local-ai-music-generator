#!/usr/bin/env python3
"""Run YingMusic infer_api with macOS MPS/CPU device selection."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    home = project / "vendor" / "YingMusic-Singer-Plus"
    if not (home / "infer_api.py").is_file():
        raise SystemExit(f"YingMusic missing at {home}. Run setup-yingmusic first.")

    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    sys.path.insert(0, str(home))
    os.chdir(home)

    import torch

    import infer_api

    def get_device() -> str:
        if torch.cuda.is_available():
            return "cuda:0"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    infer_api.get_device = get_device  # type: ignore[method-assign]
    print(f"[INFO] device={get_device()}")
    args = infer_api.parse_args()
    infer_api.synthesize(args)


if __name__ == "__main__":
    main()
