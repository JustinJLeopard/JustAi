#!/usr/bin/env python3
# =============================================================================
# ManusLocal — Honcho Memory Setup
# Initializes workspaces and peer representations for ManusLocal.
# =============================================================================

import os

# Auto-load .env from project root (added by Manus patch)
try:
    from dotenv import load_dotenv as _load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    _load_dotenv(_env_path, override=False)
except ImportError:
    pass
import sys
import argparse
from honcho import Honcho
from honcho.api_types import PeerConfig

def get_honcho(workspace="dev"):
    api_key = os.environ.get("HONCHO_API_KEY")
    if not api_key:
        print("Error: HONCHO_API_KEY not set in environment.")
        sys.exit(1)
    return Honcho(api_key=api_key, workspace_id=workspace)

def init_workspaces():
    print("Initializing Honcho workspaces for ManusLocal...")
    
    # 1. Dev Workspace
    print("Setting up 'dev' workspace...")
    h_dev = get_honcho("dev")
    
    # Create ManusLocal peer (not observed, it's the agent)
    ml_peer = h_dev.peer("manus-local", configuration=PeerConfig(observe_me=False))
    
    # Set initial instructions for ManusLocal
    with open(os.path.join(os.path.dirname(__file__), "../persona/system_prompt.txt"), "r") as f:
        prompt = f.read()
    
    ml_peer.set_card([f"IDENTITY:\n{prompt}"])
    print("  - Created 'manus-local' peer and set identity card.")
    
    # Ensure developer peer exists (observed)
    dev_peer = h_dev.peer("developer")
    print("  - Verified 'developer' peer.")

    # 2. Biz Workspace
    print("Setting up 'biz' workspace...")
    h_biz = get_honcho("biz")
    
    # Create ManusLocal orchestrator peer for biz
    biz_peer = h_biz.peer("manus-local-biz", configuration=PeerConfig(observe_me=False))
    biz_peer.set_card(["Role: Business Orchestrator for 'Delegate and Orchestrate'."])
    print("  - Created 'manus-local-biz' peer.")

    print("Honcho initialization complete.")

def check_health():
    try:
        h = get_honcho("dev")
        peers = h.peers()
        print(f"Honcho connection successful. Found {len(list(peers))} peers in 'dev' workspace.")
        return True
    except Exception as e:
        print(f"Honcho health check failed: {e}")
        return False

def resume_session():
    print("Resuming session state from Honcho...")
    h = get_honcho("dev")
    state_peer = h.peer("session-state")
    try:
        response = state_peer.chat("What is the current active plan and next step for ManusLocal?")
        print(f"Session State:\n{response}")
    except Exception as e:
        print(f"Could not retrieve session state (might be empty): {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ManusLocal Honcho Setup")
    parser.add_argument("--init", action="store_true", help="Initialize workspaces and peers")
    parser.add_argument("--check", action="store_true", help="Check Honcho connection health")
    parser.add_argument("--resume", action="store_true", help="Resume session state")
    
    args = parser.parse_args()
    
    if args.init:
        init_workspaces()
    elif args.check:
        if not check_health():
            sys.exit(1)
    elif args.resume:
        resume_session()
    else:
        parser.print_help()
