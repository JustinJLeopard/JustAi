#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(os.environ.get("JUSTAI_ROOT", Path(__file__).resolve().parents[1]))


def localmanus_root() -> Path:
    return Path(os.environ.get("JUSTAI_LOCALMANUS_ROOT", repo_root() / "LocalManus"))


def relay_root() -> Path:
    return Path(os.environ.get("JUSTAI_RELAY_ROOT", repo_root() / "relay-room"))


def base_env() -> dict[str, str]:
    env = os.environ.copy()
    env["JUSTAI_ROOT"] = str(repo_root())
    env["JUSTAI_LOCALMANUS_ROOT"] = str(localmanus_root())
    env["JUSTAI_RELAY_ROOT"] = str(relay_root())
    env["LOCALMANUS_ROOT"] = env["JUSTAI_LOCALMANUS_ROOT"]
    env["RELAY_ROOT"] = env["JUSTAI_RELAY_ROOT"]
    env.setdefault("JUSTAI_RELAY_SERVER", "local-server")
    env.setdefault("JUSTAI_SPACETIME_SESSION", "spacetime")
    return env


def run(cmd: list[str]) -> int:
    return subprocess.call(cmd, env=base_env())


def start_cmd(_: argparse.Namespace) -> int:
    return run(["bash", str(repo_root() / "scripts" / "start_justai.sh")])


def status_cmd(_: argparse.Namespace) -> int:
    return run(["bash", str(repo_root() / "scripts" / "check_justai.sh")])


def health_cmd(_: argparse.Namespace) -> int:
    return status_cmd(_)


def task_cmd(args: argparse.Namespace) -> int:
    ml = localmanus_root() / "tools" / "ml_cli.py"
    if not ml.exists():
        print(f"missing LocalManus CLI: {ml}", file=sys.stderr)
        return 1
    return run(["python3", str(ml), "task", args.description])


def mini_cmd(args: argparse.Namespace) -> int:
    ml = localmanus_root() / "tools" / "ml_cli.py"
    if not ml.exists():
        print(f"missing LocalManus CLI: {ml}", file=sys.stderr)
        return 1
    return run(["python3", str(ml), "mini", args.description])


def relay_cmd(args: argparse.Namespace) -> int:
    relay = relay_root() / "scripts" / "daemon_ctl.sh"
    if not relay.exists():
        print(f"missing relay daemon controller: {relay}", file=sys.stderr)
        return 1
    return run(["bash", str(relay), args.action])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="justai")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start", help="Start the combined JustAi stack")
    p.set_defaults(func=start_cmd)

    p = sub.add_parser("status", help="Check JustAi status")
    p.set_defaults(func=status_cmd)

    p = sub.add_parser("health", help="Check JustAi health")
    p.set_defaults(func=health_cmd)

    p = sub.add_parser("task", help="Run a LocalManus task")
    p.add_argument("description")
    p.set_defaults(func=task_cmd)

    p = sub.add_parser("mini", help="Run a mini task")
    p.add_argument("description")
    p.set_defaults(func=mini_cmd)

    p = sub.add_parser("relay", help="Relay-room command passthrough")
    p.add_argument("action", choices=["status", "health", "start", "restart"])
    p.set_defaults(func=relay_cmd)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
