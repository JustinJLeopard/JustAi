#!/usr/bin/env python3
"""
honcho_writeback.py — replaced with claude-flow memory bridge (Sprint 1 cleanup)

Original: captured Discord state and wrote to Honcho API
Replacement: writes to local JSON fallback (already existed as backup)
claude-flow memory is the canonical cross-session store now.

To store session state in claude-flow:
    cd ~/projects/ruv-research && claude-flow memory store -k "session/notes" -v "..."

This file is kept as a placeholder to avoid breaking any scripts that call it.
It exits 0 without doing anything when HONCHO_API_KEY is not set (original behavior).
"""
import sys

def main():
    # If HONCHO_API_KEY is set someone is still trying to use old Honcho — warn
    import os
    if os.environ.get("HONCHO_API_KEY"):
        print("  ⚠ honcho_writeback.py: Honcho deprecated. Use claude-flow memory store.", file=sys.stderr)
    # Exit cleanly — session_capture.py has its own local JSON fallback
    sys.exit(0)

if __name__ == "__main__":
    main()
