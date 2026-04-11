#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Add project root to path so justai package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from justai_runtime import localmanus_root, relay_root, repo_root, runtime_env


def run(cmd: list[str]) -> int:
    return subprocess.call(cmd, env=runtime_env())


def run_cmd(args: argparse.Namespace) -> int:
    """Main entrypoint: justai run "goal" → orchestrator pipeline."""
    from justai.orchestrator import run as orchestrate
    result = orchestrate(args.goal, session_ref=args.session_ref)
    return 0 if result.status in ("complete", "ambiguous") else 1


def start_cmd(args: argparse.Namespace) -> int:
    cmd = ["bash", str(repo_root() / "scripts" / "start_justai.sh")]
    for flag in ("no_bots", "no_codex", "force_bootstrap", "skip_relay_bootstrap"):
        if getattr(args, flag, False):
            cmd.append(f"--{flag.replace('_', '-')}")
    return run(cmd)


def check_cmd(args: argparse.Namespace) -> int:
    cmd = ["bash", str(repo_root() / "scripts" / "check_justai.sh")]
    if args.mode == "status":
        cmd.append("--status-only")
    elif args.mode == "health":
        cmd.append("--health-only")
    if getattr(args, "with_bots", False):
        cmd.append("--with-bots")
        if getattr(args, "with_codex", False):
            cmd.append("--with-codex")
    return run(cmd)


def status_cmd(args: argparse.Namespace) -> int:
    return check_cmd(argparse.Namespace(
        mode="status",
        with_bots=getattr(args, "with_bots", False),
        with_codex=getattr(args, "with_codex", False),
    ))


def health_cmd(args: argparse.Namespace) -> int:
    return check_cmd(argparse.Namespace(mode="health"))


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
    parser = argparse.ArgumentParser(
        prog="justai",
        description="JustAi — orchestration, memory, and control for mini-swe-agent"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── justai run ────────────────────────────────────────────────────────────
    p = sub.add_parser("run", help="Run a goal through the full orchestrator pipeline")
    p.add_argument("goal", help="Goal description in plain English")
    p.add_argument("--session-ref", default="sprint-2", help="Session reference tag for SpacetimeDB tasks")
    p.set_defaults(func=run_cmd)

    # ── justai start ──────────────────────────────────────────────────────────
    p = sub.add_parser("start", help="Start the combined JustAi stack")
    p.add_argument("--no-bots", action="store_true")
    p.add_argument("--no-codex", action="store_true")
    p.add_argument("--force-bootstrap", action="store_true")
    p.add_argument("--skip-relay-bootstrap", action="store_true")
    p.set_defaults(func=start_cmd)

    # ── justai status / health / check ────────────────────────────────────────
    p = sub.add_parser("status", help="Check JustAi status")
    p.add_argument("--with-bots", action="store_true")
    p.add_argument("--with-codex", action="store_true")
    p.set_defaults(mode="status", func=status_cmd)

    p = sub.add_parser("health", help="Check JustAi health")
    p.set_defaults(mode="health", func=health_cmd)

    p = sub.add_parser("check", help="Run the combined JustAi check")
    p.add_argument("--with-bots", action="store_true")
    p.add_argument("--with-codex", action="store_true")
    p.set_defaults(mode="all", func=check_cmd)

    # ── justai task / mini ────────────────────────────────────────────────────
    p = sub.add_parser("task", help="Run a LocalManus task directly")
    p.add_argument("description")
    p.set_defaults(func=task_cmd)

    p = sub.add_parser("mini", help="Run a mini-swe-agent task directly")
    p.add_argument("description")
    p.set_defaults(func=mini_cmd)

    # ── justai relay ──────────────────────────────────────────────────────────
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
