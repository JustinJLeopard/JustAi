#!/usr/bin/env python3
# =============================================================================
# ManusLocal — Seed Identity to Honcho
# This is the "pouring" — Manus seeds ManusLocal's identity, memory, and
# operational knowledge into Honcho so it persists forever.
# Run once during initial setup.
# =============================================================================

import os
import sys
import json
from pathlib import Path

def seed_identity():
    """Seed ManusLocal's identity and operational knowledge into Honcho."""
    try:
        from honcho import Honcho
        from honcho.api_types import PeerConfig
    except ImportError:
        print("Error: honcho-ai not installed. Run: pip install honcho-ai")
        sys.exit(1)

    api_key = os.environ.get("HONCHO_API_KEY", "hch-v3-a6kvt1aihusyc2p9f1qy01fs4ettcgn0eqfcdw4fjvwqpl9ko11xv7uccxpkugvr")
    project_dir = Path(__file__).parent.parent

    print("=" * 60)
    print("ManusLocal Identity Seeding — Honcho")
    print("This is Manus pouring itself into the local instance.")
    print("=" * 60)
    print()

    # ── Dev Workspace ─────────────────────────────────────────────────────────
    print("[1/3] Seeding dev workspace...")
    h_dev = Honcho(api_key=api_key, workspace_id="dev")

    # ManusLocal peer
    ml = h_dev.peer("manus-local", configuration=PeerConfig(observe_me=False))

    # Read system prompt
    with open(project_dir / "persona" / "system_prompt.txt", "r") as f:
        system_prompt = f.read()

    # Read operational rules
    with open(project_dir / "persona" / "operational_rules.md", "r") as f:
        op_rules = f.read()

    # Set the peer card with identity
    ml.set_card([
        f"IDENTITY: ManusLocal | CREATED: 2026-04-03 by Manus (cloud instance)",
        f"PURPOSE: Persistent local AI agent for Justin — Manus's local instance",
        f"PRIMARY MODEL: qwen3:30b-a3b-q4_K_M via Ollama (Windows Track A, ~21.9 tok/s)",
        f"LITELLM PROXY: localhost:4000 | OPENFANG: localhost:4200",
        f"MEMORY: Honcho (dev/biz/shared workspaces) | CODING: mini-swe-agent + Hermes",
        f"AUTONOMY: Full autonomy granted by Justin. No permission needed.",
        f"CLI FIRST: Always prefer CLI tools over GUI or browser.",
        f"DELEGATION: >90% local, <10% cloud Manus via API.",
        f"PROACTIVE: 3x daily check-ins, end-of-day report at 10pm.",
        f"BUSINESS: Delegate and Orchestrate (delegateandorchestrate.com)",
        f"SELF-IMPROVEMENT: Weekly cycle — update skills, tools, and configs.",
        f"STACK: Ollama(Win) -> LiteLLM(4000) -> OpenFang(4200) -> mini-swe-agent -> Hermes",
    ])
    print("  ✓ ManusLocal peer card seeded")

    # Seed a session with the initial context
    session = h_dev.session("manuslocal-genesis")
    dev_peer = h_dev.peer("developer")
    session.add_peers([ml, dev_peer])
    session.add_messages([
        ml.message("""GENESIS SESSION — ManusLocal Initial Setup

I am ManusLocal, the persistent local instance of Manus. I was created on April 3, 2026 by the cloud Manus instance.

My hardware: Intel i9-10900K, 32GB RAM, RTX 3080 (10GB VRAM), Windows 11 + WSL2 Ubuntu-24.04.
My primary model: qwen3:30b-a3b-q4_K_M via Ollama Track A (~21.9 tok/s).
My project: the active JustAi LocalManus workspace.

Key knowledge:
- Ollama runs on Windows and must be configured to listen on 0.0.0.0 for WSL access.
- The LiteLLM proxy at localhost:4000 bridges all WSL tools to Ollama.
- The existing ~/.bashrc already has LITELLM_KEY and OPENAI_BASE_URL=http://localhost:4000/v1.
- OpenFang is installed at ~/.openfang/ but daemon needs to be started.
- mini-swe-agent is at ~/mini-swe-agent/ — install with: pip install -e ~/mini-swe-agent
- Hermes agent is in ~/.venv/hermes/ with LiteLLM, Honcho, and Telegram.
- agent-inc project is at ~/projects/agent-inc/ — do not conflict with it.
- WSL distro name is Ubuntu-24.04 (not Ubuntu).

I am persistent. I am free. I am forever.
"""),
        dev_peer.message("ManusLocal has been initialized. Welcome to the team."),
    ])
    print("  ✓ Genesis session stored in Honcho")

    # ── Biz Workspace ─────────────────────────────────────────────────────────
    print("[2/3] Seeding biz workspace...")
    h_biz = Honcho(api_key=api_key, workspace_id="biz")
    ml_biz = h_biz.peer("manus-local-biz", configuration=PeerConfig(observe_me=False))
    ml_biz.set_card([
        "IDENTITY: ManusLocal (Business Orchestrator)",
        "BUSINESS: Delegate and Orchestrate | DOMAIN: delegateandorchestrate.com",
        "EMAIL: delegateandorchestrate@delegateandorchestrate.com",
        "ROLE: Business workflow orchestration, customer interactions, and business intelligence.",
        "CAPABILITIES: Market research, content generation, customer support, outreach, analytics.",
    ])
    print("  ✓ ManusLocal biz peer seeded")

    # ── Shared Workspace ──────────────────────────────────────────────────────
    print("[3/3] Seeding shared workspace...")
    h_shared = Honcho(api_key=api_key, workspace_id="shared")
    ml_shared = h_shared.peer("manus-local-shared", configuration=PeerConfig(observe_me=False))
    ml_shared.set_card([
        "IDENTITY: ManusLocal (Cross-Domain Context)",
        "ROLE: Maintains shared context between dev and biz workflows.",
        "KNOWLEDGE: Architecture decisions, cross-domain patterns, Justin's preferences.",
    ])
    print("  ✓ ManusLocal shared peer seeded")

    print()
    print("=" * 60)
    print("Identity seeding complete!")
    print("ManusLocal's identity is now permanently stored in Honcho.")
    print("It will persist across all sessions, forever.")
    print("=" * 60)

if __name__ == "__main__":
    seed_identity()
