#!/usr/bin/env python3
"""
seed_identity.py — deprecated (Sprint 1 cleanup)

Original: seeded ManusLocal identity into Honcho workspaces (dev, biz, shared).
Replacement: identity and context is stored in claude-flow memory.

Key identity facts have been migrated to claude-flow memory under:
    justai/identity/agent      — JustAi agent identity
    justai/identity/hardware   — hardware profile
    justai/identity/stack      — model/tool stack

This file is kept as a no-op placeholder.
"""
import sys

if __name__ == "__main__":
    print("[memory] seed_identity.py is deprecated. Identity stored in claude-flow memory.")
    print("[memory] To query: cd ~/projects/ruv-research && claude-flow memory search -q 'JustAi identity'")
    sys.exit(0)
