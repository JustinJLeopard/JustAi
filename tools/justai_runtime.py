from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    return Path(os.environ.get("JUSTAI_ROOT", Path(__file__).resolve().parents[1]))


def runtime_root() -> Path:
    default_root = Path("/tmp") / "justai"
    return Path(os.environ.get("JUSTAI_RUNTIME_ROOT", default_root))


def runtime_paths() -> dict[str, Path]:
    root = runtime_root()
    return {
        "root": root,
        "run_log": Path(os.environ.get("JUSTAI_RUN_LOG_FILE", root / "justai_run.log")),
        "api_pid": Path(os.environ.get("JUSTAI_API_PID_FILE", root / "api.pid")),
        "api_log": Path(os.environ.get("JUSTAI_API_LOG_FILE", root / "api.log")),
    }


def runtime_env() -> dict[str, str]:
    paths = runtime_paths()
    env = os.environ.copy()
    env["JUSTAI_ROOT"] = str(repo_root())
    env["JUSTAI_RUNTIME_ROOT"] = str(paths["root"])
    env.setdefault("JUSTAI_SAFE_MINI_MODE", "stub")
    env.setdefault("JUSTAI_RUN_LOG_FILE", str(paths["run_log"]))
    env.setdefault("JUSTAI_API_PID_FILE", str(paths["api_pid"]))
    env.setdefault("JUSTAI_API_LOG_FILE", str(paths["api_log"]))
    return env
