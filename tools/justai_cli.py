#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Add project root to path so justai package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from justai_runtime import repo_root, runtime_env


def run(cmd: list[str]) -> int:
    return subprocess.call(cmd, env=runtime_env())


def run_cmd(args: argparse.Namespace) -> int:
    """Main entrypoint: justai run "goal" → orchestrator pipeline."""
    from justai.exit_codes import for_run_status
    from justai.orchestrator import run as orchestrate

    result = orchestrate(args.goal, session_ref=args.session_ref)
    # Same table as `justai run`; an ambiguous goal must not exit 0 here either.
    return for_run_status(result.status)


def start_cmd(args: argparse.Namespace) -> int:
    cmd = ["bash", str(repo_root() / "scripts" / "start_justai.sh")]
    return run(cmd)


def check_cmd(args: argparse.Namespace) -> int:
    cmd = ["bash", str(repo_root() / "scripts" / "check_justai.sh")]
    if args.mode == "status":
        cmd.append("--status-only")
    elif args.mode == "health":
        cmd.append("--health-only")
    return run(cmd)


def status_cmd(args: argparse.Namespace) -> int:
    return check_cmd(argparse.Namespace(mode="status"))


def health_cmd(args: argparse.Namespace) -> int:
    return check_cmd(argparse.Namespace(mode="health"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="justai",
        description="JustAi — orchestration, memory, and control for mini-swe-agent",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── justai run ────────────────────────────────────────────────────────────
    p = sub.add_parser("run", help="Run a goal through the full orchestrator pipeline")
    p.add_argument("goal", help="Goal description in plain English")
    p.add_argument("--session-ref", default="phase4", help="Session reference tag for run memory")
    p.set_defaults(func=run_cmd)

    # ── justai start ──────────────────────────────────────────────────────────
    p = sub.add_parser("start", help="Start the combined JustAi stack")
    p.set_defaults(func=start_cmd)

    # ── justai status / health / check ────────────────────────────────────────
    p = sub.add_parser("status", help="Check JustAi status")
    p.set_defaults(mode="status", func=status_cmd)

    p = sub.add_parser("health", help="Check JustAi health")
    p.set_defaults(mode="health", func=health_cmd)

    p = sub.add_parser("check", help="Run the combined JustAi check")
    p.set_defaults(mode="all", func=check_cmd)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
