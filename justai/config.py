#!/usr/bin/env python3
"""
JustAi — Configuration
=======================
Centralized configuration with defaults and env var overrides.
Single source of truth for all module settings.
"""
from __future__ import annotations

import os
from pathlib import Path

# ── Version ───────────────────────────────────────────────────────────────────
VERSION = "1.0.0"

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = Path(os.environ.get("JUSTAI_RUNTIME_ROOT", "/tmp/justai"))

# ── Services ──────────────────────────────────────────────────────────────────
LITELLM_BASE_URL = os.environ.get(
    "LITELLM_BASE_URL", "http://localhost:4000"
).rstrip("/").removesuffix("/v1")

LITELLM_KEY = os.environ.get("LITELLM_KEY", "")

SPACETIMEDB_URL = os.environ.get("SPACETIMEDB_URL", "http://127.0.0.1:3000")

CLAUDE_FLOW_MCP_URL = os.environ.get("CLAUDE_FLOW_MCP_URL", "http://127.0.0.1:3100")

# ── Models ────────────────────────────────────────────────────────────────────
PLANNER_MODEL = os.environ.get("JUSTAI_PLANNER_MODEL", "openai/claude-opus-4-6")
INTENT_MODEL = os.environ.get("JUSTAI_INTENT_MODEL", "openai/claude-opus-4-6")
REVIEWER_MODEL = os.environ.get("JUSTAI_REVIEWER_MODEL", "openai/claude-opus-4-6")

# ── Orchestrator ──────────────────────────────────────────────────────────────
SESSION_REF = os.environ.get("JUSTAI_SESSION_REF", "")
AUTO_MODE = os.environ.get("JUSTAI_AUTO_MODE", "").lower() in ("1", "true", "yes")
LOCAL_EXEC = os.environ.get("JUSTAI_LOCAL_EXEC", "").lower() in ("1", "true", "yes")
MAX_REPLAN_ATTEMPTS = int(os.environ.get("JUSTAI_MAX_REPLAN", "2"))

# ── Checkpoint ────────────────────────────────────────────────────────────────
R1_TIMEOUT_SECONDS = int(os.environ.get("JUSTAI_R1_TIMEOUT", "60"))

# ── Delegator ─────────────────────────────────────────────────────────────────
RELAY_BIN = os.environ.get("RELAY_BIN", str(Path.home() / ".local" / "bin" / "relay"))
CLAIM_TIMEOUT = int(os.environ.get("JUSTAI_CLAIM_TIMEOUT", "120"))
EXEC_TIMEOUT = int(os.environ.get("JUSTAI_EXEC_TIMEOUT", "1800"))

# ── Executor ──────────────────────────────────────────────────────────────────
WORK_DIR = Path(os.environ.get("JUSTAI_WORK_DIR", str(PROJECT_ROOT)))
LOCAL_EXEC_TIMEOUT = int(os.environ.get("JUSTAI_LOCAL_EXEC_TIMEOUT", "300"))

# ── API Server ────────────────────────────────────────────────────────────────
API_PORT = int(os.environ.get("JUSTAI_API_PORT", "3002"))

# ── Tracing ───────────────────────────────────────────────────────────────────
LANGFUSE_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "")
LANGFUSE_ENABLED = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)
