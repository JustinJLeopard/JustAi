from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    return Path(os.environ.get("JUSTAI_ROOT", Path(__file__).resolve().parents[1]))


def localmanus_root() -> Path:
    return Path(os.environ.get("JUSTAI_LOCALMANUS_ROOT", repo_root() / "LocalManus"))


def relay_root() -> Path:
    return Path(os.environ.get("JUSTAI_RELAY_ROOT", repo_root() / "relay-room"))


def runtime_root() -> Path:
    default_root = Path("/tmp") / "justai"
    return Path(os.environ.get("JUSTAI_RUNTIME_ROOT", default_root))


def runtime_paths() -> dict[str, Path]:
    root = runtime_root()
    return {
        "root": root,
        "dispatch_pid": Path(os.environ.get("JUSTAI_RELAY_DISPATCH_PID_FILE", root / "relay_dispatch.pid")),
        "dispatch_log": Path(os.environ.get("JUSTAI_RELAY_DISPATCH_LOG_FILE", root / "relay_dispatch.log")),
        "health_pid": Path(os.environ.get("JUSTAI_RELAY_HEALTH_PID_FILE", root / "relay_health_server.pid")),
        "health_log": Path(os.environ.get("JUSTAI_RELAY_HEALTH_LOG_FILE", root / "relay_health_server.log")),
        "web_pid": Path(os.environ.get("JUSTAI_RELAY_WEB_PID_FILE", root / "relay_web.pid")),
        "web_log": Path(os.environ.get("JUSTAI_RELAY_WEB_LOG_FILE", root / "relay_web.log")),
        "bot_pid_dir": Path(os.environ.get("JUSTAI_RELAY_BOT_PID_DIR", root / "bots")),
        "bot_log_dir": Path(os.environ.get("JUSTAI_RELAY_BOT_LOG_DIR", root / "bots")),
    }


def runtime_env() -> dict[str, str]:
    paths = runtime_paths()
    env = os.environ.copy()
    env["JUSTAI_ROOT"] = str(repo_root())
    env["JUSTAI_LOCALMANUS_ROOT"] = str(localmanus_root())
    env["JUSTAI_RELAY_ROOT"] = str(relay_root())
    env["JUSTAI_RUNTIME_ROOT"] = str(paths["root"])
    env["LOCALMANUS_ROOT"] = env["JUSTAI_LOCALMANUS_ROOT"]
    env["RELAY_ROOT"] = env["JUSTAI_RELAY_ROOT"]
    env.setdefault("JUSTAI_RELAY_SERVER", "local-server")
    env.setdefault("JUSTAI_SPACETIME_SESSION", "spacetime")
    env.setdefault("JUSTAI_RELAY_DISPATCH_PID_FILE", str(paths["dispatch_pid"]))
    env.setdefault("JUSTAI_RELAY_DISPATCH_LOG_FILE", str(paths["dispatch_log"]))
    env.setdefault("JUSTAI_RELAY_HEALTH_PID_FILE", str(paths["health_pid"]))
    env.setdefault("JUSTAI_RELAY_HEALTH_LOG_FILE", str(paths["health_log"]))
    env.setdefault("JUSTAI_RELAY_WEB_PID_FILE", str(paths["web_pid"]))
    env.setdefault("JUSTAI_RELAY_WEB_LOG_FILE", str(paths["web_log"]))
    env.setdefault("JUSTAI_RELAY_BOT_PID_DIR", str(paths["bot_pid_dir"]))
    env.setdefault("JUSTAI_RELAY_BOT_LOG_DIR", str(paths["bot_log_dir"]))
    return env
