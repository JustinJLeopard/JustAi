#!/usr/bin/env python3
"""
JustAi Orchestrator package

Auto-loads environment variables from the repo .env on import so components
have LITELLM_KEY, GAMERON_API_KEY, and related settings available even when
the caller did not source a shell profile first.
"""

from __future__ import annotations

__version__ = "1.0.0"

import os
from pathlib import Path


def _load_env() -> None:
    """Load .env into os.environ if key vars are missing."""
    if os.environ.get("LITELLM_KEY"):
        return  # already loaded

    candidates = [
        Path(__file__).resolve().parents[1] / ".env",
        Path.home() / "projects" / "JustAi" / ".env",
    ]
    for env_path in candidates:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                os.environ.setdefault(key, val)
            break


_load_env()
