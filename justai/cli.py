#!/usr/bin/env python3
"""
JustAi — CLI
=============
Unified command-line interface.

Usage:
    justai run "your goal"              # run the full orchestrator pipeline
    justai run --auto "your goal"       # skip R1 checkpoint wait
    justai plan "your goal"             # decompose into tasks (no execution)
    justai status                       # check service health
    justai history                      # show recent runs from memory
    justai version                      # print version

Can also be invoked as:
    python3 -m justai run "your goal"
"""

from __future__ import annotations

import argparse
import sys

from justai import __version__


def cmd_run(args: argparse.Namespace) -> int:
    """Run the full orchestrator pipeline."""
    from justai.orchestrator import run

    goal = " ".join(args.goal)
    if not goal:
        print("Error: no goal provided.")
        print('Usage: justai run "your goal here"')
        return 1

    result = run(
        goal, session_ref=args.session, auto=args.auto, local=getattr(args, "local", False)
    )
    # Exit 0 is reserved for verified completion. An ambiguous goal is a
    # legitimate result but NOT completion -> CLARIFICATION_REQUIRED, not 0.
    from justai.exit_codes import for_run_status

    return for_run_status(result.status)


def cmd_plan(args: argparse.Namespace) -> int:
    """Decompose a goal into tasks without executing."""
    from justai.scope_planner import decompose, format_plan

    goal = " ".join(args.goal)
    if not goal:
        print("Error: no goal provided.")
        return 1

    print(f"Planning: {goal}")
    print()
    plan = decompose(goal, session_ref=args.session)
    print(format_plan(plan))
    print(f"{len(plan.tasks)} task(s) ready for execution.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Check service health."""
    from justai.exit_codes import NOT_READY, OK
    from justai.health import preflight, print_preflight, readiness

    print("JustAi Service Status")
    print("=" * 60)
    statuses = preflight()
    print_preflight(statuses)
    # Exit reflects full readiness (every probe), not just the planning bit —
    # so `justai status` cannot exit 0 while the API's own all_ok is false.
    r = readiness(statuses)

    # Also check if memory has data
    from justai.memory import Memory

    mem = Memory()
    try:
        stats = mem.stats()
        if stats:
            print(f"  Memory: {stats}")
    except Exception:
        print("  Memory: unavailable")

    return OK if r.all_ok else NOT_READY


def cmd_history(args: argparse.Namespace) -> int:
    """Show recent runs from memory."""
    from justai.memory import Memory

    mem = Memory()
    try:
        keys = mem.list_keys()
    except Exception:
        print("Memory service unavailable. Start claude-flow MCP first.")
        return 1

    run_keys = sorted([k for k in keys if k.startswith("justai/runs/")], reverse=True)

    if not run_keys:
        print("No run history found.")
        return 0

    limit = args.limit
    print(f"Recent runs (showing {min(limit, len(run_keys))} of {len(run_keys)}):")
    print("-" * 70)
    for key in run_keys[:limit]:
        try:
            value = mem.retrieve(key)
            if value:
                print(f"  {key.split('/')[-1]}: {value}")
        except Exception:
            print(f"  {key}: <read error>")
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """Print version."""
    print(f"justai {__version__}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="justai",
        description="JustAi — AI Development Orchestrator",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command")

    # run
    p_run = sub.add_parser("run", help="Run the orchestrator pipeline")
    p_run.add_argument("goal", nargs="*", help="The goal to accomplish")
    p_run.add_argument(
        "--auto", action="store_true", help="Auto-approve R1 checkpoints (no 60s wait)"
    )
    p_run.add_argument(
        "--local", action="store_true", help="Execute tasks locally instead of delegating to agent"
    )
    p_run.add_argument("--session", default="", help="Session reference for tracing")
    p_run.set_defaults(func=cmd_run)

    # plan
    p_plan = sub.add_parser("plan", help="Plan tasks without executing")
    p_plan.add_argument("goal", nargs="*", help="The goal to plan")
    p_plan.add_argument("--session", default="", help="Session reference")
    p_plan.set_defaults(func=cmd_plan)

    # status
    p_status = sub.add_parser("status", help="Check service health")
    p_status.set_defaults(func=cmd_status)

    # history
    p_hist = sub.add_parser("history", help="Show recent runs")
    p_hist.add_argument(
        "--limit", type=int, default=10, help="Number of runs to show (default: 10)"
    )
    p_hist.set_defaults(func=cmd_history)

    # version
    p_ver = sub.add_parser("version", help="Print version")
    p_ver.set_defaults(func=cmd_version)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
