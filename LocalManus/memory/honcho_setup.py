#!/usr/bin/env python3
"""
honcho_setup.py — deprecated (Sprint 1 cleanup)

Original: set up Honcho workspace, peers, and initial memory seeds.
Replacement: claude-flow memory is the canonical store.

To initialize claude-flow memory for JustAi:
    cd ~/projects/ruv-research && claude-flow memory init

This file is kept as a no-op placeholder.
"""
import sys

if __name__ == "__main__":
    print("[memory] honcho_setup.py is deprecated. claude-flow memory is now used.")
    print("[memory] To init: cd ~/projects/ruv-research && claude-flow memory init")
    sys.exit(0)
