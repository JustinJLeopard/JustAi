#!/usr/bin/env python3
"""
JustAi — Trajectory Intelligence
==================================
AI-powered trajectory analysis for post-mortem debugging, learning
optimization, and audit compliance.

Data sources:
  - .traj.json files from mini-swe-agent runs
  - LangFuse traces for token/cost data (via justai.tracing)
  - Claude API via LiteLLM for AI analysis

Usage:
    from justai.trajectory import analyze_trajectory, get_patterns

    analysis = analyze_trajectory(traj_data)
    patterns = get_patterns(limit=20)
"""

from __future__ import annotations

import json
import os
import stat
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LITELLM_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000")
ANALYSIS_MODEL = os.environ.get("JUSTAI_ANALYSIS_MODEL", "openai/claude-opus-4-6")
TRAJ_DIR = Path(os.environ["JUSTAI_TRAJ_DIR"]) if os.environ.get("JUSTAI_TRAJ_DIR") else None

# In-memory cache for AI analysis results (keyed by trajectory filename)
_analysis_cache: dict[str, dict] = {}
_patterns_cache: dict[str, Any] = {}
_patterns_cache_ts: float = 0.0
_PATTERNS_TTL = 300.0  # 5 minutes


# ── Data Types ──────────────────────────────────────────────────────────────


@dataclass
class TrajStep:
    index: int
    action_type: str  # bash, edit, read, think, write
    command: str
    reasoning: str
    result: str
    returncode: int | None
    file_touched: str
    timestamp: str = ""
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass
class TrajAnalysis:
    filename: str
    summary: str
    root_cause: str
    divergence_step: int | None
    recommendation: str
    status: str  # "success" | "failure" | "partial"
    step_count: int
    failed_steps: list[int]
    files_changed: list[str]
    total_cost: float
    total_tokens: int
    cached: bool = False


@dataclass
class LearningPattern:
    pattern: str
    frequency: int
    success_rate: float
    suggestion: str


@dataclass
class PatternReport:
    total_trajectories: int
    avg_steps: float
    avg_cost: float
    success_rate: float
    common_failures: list[dict]
    suggestions: list[str]
    efficiency_trend: list[dict]


# ── Trajectory Loading ──────────────────────────────────────────────────────


def _traj_dir() -> Path:
    if TRAJ_DIR is not None:
        return TRAJ_DIR

    val = os.environ.get("JUSTAI_TRAJ_DIR")
    if not val:
        raise RuntimeError(
            "JUSTAI_TRAJ_DIR environment variable is required for trajectory data. "
            "Set it to the directory containing .traj.json files."
        )
    return Path(val)


def _safe_trajectory_parts(filename: str) -> tuple[str, ...]:
    """Validate a relative trajectory path before opening it by descriptor."""
    if not isinstance(filename, str) or "\x00" in filename:
        raise FileNotFoundError(f"Trajectory not found: {filename}")
    path = Path(filename)
    parts = path.parts
    if (
        path.is_absolute()
        or not parts
        or any(part in (os.curdir, os.pardir) for part in parts)
        or not parts[-1].endswith(".traj.json")
    ):
        raise FileNotFoundError(f"Trajectory not found: {filename}")
    return parts


def _secure_open_flags(*, directory: bool = False) -> int:
    """Return fail-closed descriptor flags for attacker-writable trajectory trees."""
    if (
        os.open not in os.supports_dir_fd
        or not hasattr(os, "O_NOFOLLOW")
        or not hasattr(os, "O_NONBLOCK")
    ):
        raise RuntimeError("Secure trajectory file access is unavailable on this platform")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    if directory:
        flags |= getattr(os, "O_DIRECTORY", 0)
    return flags


def _open_directory(name: str | Path, *, dir_fd: int | None = None) -> int:
    """Open a real directory without following a final symlink."""
    try:
        fd = os.open(name, _secure_open_flags(directory=True), dir_fd=dir_fd)
    except OSError as exc:
        raise FileNotFoundError(f"Trajectory directory not found: {name}") from exc
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise FileNotFoundError(f"Trajectory directory not found: {name}")
    except BaseException:
        os.close(fd)
        raise
    return fd


def _open_regular_file(name: str, *, dir_fd: int) -> int:
    """Open a real file without following a final symlink."""
    try:
        fd = os.open(name, _secure_open_flags(), dir_fd=dir_fd)
    except OSError as exc:
        raise FileNotFoundError(f"Trajectory not found: {name}") from exc
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise FileNotFoundError(f"Trajectory not found: {name}")
    except BaseException:
        os.close(fd)
        raise
    return fd


def _open_trajectory_file(filename: str) -> int:
    """Open a trajectory through no-follow directory descriptors."""
    parts = _safe_trajectory_parts(filename)
    root_fd = _open_directory(_traj_dir().resolve())
    current_fd = root_fd
    try:
        for part in parts[:-1]:
            next_fd = _open_directory(part, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return _open_regular_file(parts[-1], dir_fd=current_fd)
    finally:
        os.close(current_fd)


def _list_trajectory_files_in_directory(directory_fd: int, prefix: str = "") -> list[dict]:
    """Read metadata from real directory entries without following symlinks."""
    files = []
    for name in os.listdir(directory_fd):
        if not name.endswith(".traj.json"):
            continue
        try:
            fd = _open_regular_file(name, dir_fd=directory_fd)
        except FileNotFoundError:
            continue
        try:
            st = os.fstat(fd)
            files.append(
                {
                    "name": str(Path(prefix) / name) if prefix else name,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                }
            )
        finally:
            os.close(fd)
    return files

def list_trajectory_files() -> list[dict]:
    """List all .traj.json files with metadata."""
    try:
        root_fd = _open_directory(_traj_dir().resolve())
    except FileNotFoundError:
        return []
    try:
        files = _list_trajectory_files_in_directory(root_fd)
        try:
            relay_fd = _open_directory("relay_dispatch", dir_fd=root_fd)
        except FileNotFoundError:
            relay_fd = None
        if relay_fd is not None:
            try:
                files.extend(_list_trajectory_files_in_directory(relay_fd, "relay_dispatch"))
            finally:
                os.close(relay_fd)
    finally:
        os.close(root_fd)
    files.sort(key=lambda x: x["mtime"] if isinstance(x["mtime"], float) else 0.0, reverse=True)
    return files


def load_trajectory(filename: str) -> dict:
    """Load and parse a .traj.json file."""
    try:
        fd = _open_trajectory_file(filename)
    except (OSError, RuntimeError) as exc:
        raise FileNotFoundError(f"Trajectory not found: {filename}") from exc
    with os.fdopen(fd, encoding="utf-8") as fp:
        return json.load(fp)


def parse_steps(traj: dict) -> list[TrajStep]:
    """Parse trajectory messages into discrete steps."""
    steps: list[TrajStep] = []
    messages = traj.get("messages", [])
    idx = 0

    for i, msg in enumerate(messages):
        if msg.get("role") != "assistant":
            continue

        tool_calls = msg.get("tool_calls", [])
        content = msg.get("content") or ""
        if not tool_calls and not content:
            continue

        command = ""
        tool_name = ""
        file_touched = ""

        if tool_calls:
            fn = tool_calls[0].get("function", {})
            tool_name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments", "{}"))
                command = args.get("command", fn.get("arguments", ""))
                file_touched = args.get("path", args.get("file_path", ""))
            except (json.JSONDecodeError, TypeError):
                command = fn.get("arguments", "")

        # Determine action type from tool name
        action_type = _classify_action(tool_name, command)

        # Get result from next tool message
        result = ""
        returncode = None
        if i + 1 < len(messages) and messages[i + 1].get("role") == "tool":
            tool_content = messages[i + 1].get("content") or ""
            try:
                parsed = json.loads(tool_content)
                returncode = parsed.get("returncode")
                result = parsed.get("output") or parsed.get("output_head") or tool_content
                if parsed.get("output_tail") and parsed.get("output_head"):
                    result = parsed["output_head"] + "\n...\n" + parsed["output_tail"]
            except (json.JSONDecodeError, TypeError):
                result = tool_content

        steps.append(
            TrajStep(
                index=idx,
                action_type=action_type,
                command=command,
                reasoning=content,
                result=result,
                returncode=returncode,
                file_touched=file_touched,
            )
        )
        idx += 1

    return steps


def _classify_action(tool_name: str, command: str) -> str:
    """Classify a step's action type."""
    name = tool_name.lower()
    cmd = command.lower()
    if "bash" in name or "execute" in name:
        if any(k in cmd for k in ["cat ", "head ", "tail ", "less ", "grep "]):
            return "read"
        if any(k in cmd for k in ["sed ", "echo ", "mv ", "cp ", "mkdir "]):
            return "edit"
        return "bash"
    if "edit" in name or "write" in name or "str_replace" in name:
        return "edit"
    if "read" in name or "view" in name:
        return "read"
    if not tool_name:
        return "think"
    return "bash"


# ── AI Analysis ─────────────────────────────────────────────────────────────

_ANALYSIS_PROMPT = """You are analyzing an AI agent's execution trajectory. The agent was given a task and took a series of steps to complete it.

Analyze the trajectory and provide:
1. **summary**: A 1-2 sentence summary of what happened
2. **root_cause**: If the task failed, what was the root cause? If successful, what key decisions led to success?
3. **divergence_step**: The step number (0-indexed) where things started going wrong (null if successful)
4. **recommendation**: One specific, actionable recommendation for how to get a better result next time
5. **status**: "success" if the task completed correctly, "failure" if it failed, "partial" if partially done
6. **files_changed**: List of files that were created or modified

Respond in JSON format only."""


def analyze_trajectory(filename: str, force: bool = False) -> dict:
    """
    Run AI analysis on a trajectory file.

    Results are cached in memory. Pass force=True to bypass cache.
    Returns a dict matching TrajAnalysis fields.
    """
    if not force and filename in _analysis_cache:
        cached = _analysis_cache[filename].copy()
        cached["cached"] = True
        return cached

    try:
        traj = load_trajectory(filename)
    except FileNotFoundError:
        return {"error": f"Trajectory not found: {filename}", "status": "error"}

    steps = parse_steps(traj)
    info = traj.get("info", {})
    failed = [s.index for s in steps if s.returncode is not None and s.returncode != 0]

    # Build condensed trajectory for the AI prompt
    condensed = _condense_trajectory(traj, steps)

    # Try AI analysis
    ai_result = _call_analysis_llm(condensed)

    if ai_result:
        result = {
            "filename": filename,
            "summary": ai_result.get("summary", ""),
            "root_cause": ai_result.get("root_cause", ""),
            "divergence_step": ai_result.get("divergence_step"),
            "recommendation": ai_result.get("recommendation", ""),
            "status": ai_result.get("status", "unknown"),
            "step_count": len(steps),
            "failed_steps": failed,
            "files_changed": ai_result.get("files_changed", []),
            "total_cost": info.get("model_stats", {}).get("instance_cost", 0.0),
            "total_tokens": sum(s.tokens_in + s.tokens_out for s in steps),
            "cached": False,
        }
    else:
        # Heuristic fallback when LiteLLM is unavailable
        result = _heuristic_analysis(filename, steps, info)

    _analysis_cache[filename] = result
    return result


def _condense_trajectory(traj: dict, steps: list[TrajStep]) -> str:
    """Build a condensed representation of the trajectory for the AI prompt."""
    info = traj.get("info", {})
    lines = []

    # Task
    for msg in traj.get("messages", []):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            task_match = content[:500]
            lines.append(f"TASK: {task_match}")
            break

    lines.append(f"EXIT STATUS: {info.get('exit_status', 'unknown')}")
    lines.append(f"STEPS: {len(steps)}")
    lines.append("")

    # Steps (condensed — max 40 steps, truncated output)
    for step in steps[:40]:
        status = f"rc={step.returncode}" if step.returncode is not None else ""
        lines.append(f"[Step {step.index}] {step.action_type}: {step.command[:120]} {status}")
        if step.reasoning:
            lines.append(f"  Reasoning: {step.reasoning[:150]}")
        if step.returncode and step.returncode != 0:
            lines.append(f"  ERROR OUTPUT: {step.result[:200]}")

    return "\n".join(lines)


def _call_analysis_llm(condensed: str) -> dict | None:
    """Call LiteLLM for AI trajectory analysis. Returns None on failure."""
    try:
        payload = json.dumps(
            {
                "model": ANALYSIS_MODEL,
                "messages": [
                    {"role": "system", "content": _ANALYSIS_PROMPT},
                    {"role": "user", "content": condensed},
                ],
                "max_tokens": 800,
                "temperature": 0.0,
            }
        ).encode()

        req = urllib.request.Request(
            f"{LITELLM_URL}/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.environ.get('LITELLM_KEY', '')}",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)

        content = data["choices"][0]["message"]["content"].strip()
        # Strip markdown code fences
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except Exception:
        return None


def _heuristic_analysis(filename: str, steps: list[TrajStep], info: dict) -> dict:
    """Fallback analysis when LiteLLM is unavailable."""
    failed = [s.index for s in steps if s.returncode is not None and s.returncode != 0]
    exit_status = info.get("exit_status", "unknown")

    status = (
        "success"
        if exit_status == "Submitted" and not failed
        else "failure"
        if failed
        else "partial"
    )
    divergence = failed[0] if failed else None

    files_changed = list(
        {s.file_touched for s in steps if s.file_touched and s.action_type in ("edit", "write")}
    )

    summary = f"Agent completed {len(steps)} steps. "
    if failed:
        summary += f"{len(failed)} step(s) failed (first failure at step {failed[0]})."
    else:
        summary += f"Exit status: {exit_status}."

    root_cause = ""
    if failed:
        first_fail = next(s for s in steps if s.index == failed[0])
        root_cause = f"Step {failed[0]} ({first_fail.action_type}: {first_fail.command[:80]}) returned non-zero exit code."

    return {
        "filename": filename,
        "summary": summary,
        "root_cause": root_cause,
        "divergence_step": divergence,
        "recommendation": "Review failed steps and consider adding verification commands after each modification.",
        "status": status,
        "step_count": len(steps),
        "failed_steps": failed,
        "files_changed": files_changed,
        "total_cost": info.get("model_stats", {}).get("instance_cost", 0.0),
        "total_tokens": 0,
        "cached": False,
    }


# ── Pattern Analysis (Learning Mode) ────────────────────────────────────────


def get_patterns(limit: int = 50) -> dict:
    """
    Aggregate patterns across recent trajectories.

    Returns analysis useful for Learning mode:
    - Success/failure rates
    - Common failure patterns
    - Efficiency trends
    - AI suggestions
    """
    global _patterns_cache, _patterns_cache_ts

    now = time.time()
    if _patterns_cache and (now - _patterns_cache_ts) < _PATTERNS_TTL:
        return _patterns_cache

    files = list_trajectory_files()[:limit]
    if not files:
        return _empty_patterns()

    trajs = []
    for f in files:
        try:
            traj = load_trajectory(f["name"])
            steps = parse_steps(traj)
            info = traj.get("info", {})
            trajs.append(
                {
                    "name": f["name"],
                    "mtime": f["mtime"],
                    "steps": steps,
                    "info": info,
                    "exit_status": info.get("exit_status", "unknown"),
                    "cost": info.get("model_stats", {}).get("instance_cost", 0.0),
                    "step_count": len(steps),
                }
            )
        except Exception:
            continue

    if not trajs:
        return _empty_patterns()

    # ── Aggregate metrics
    total = len(trajs)
    successes = sum(1 for t in trajs if t["exit_status"] == "Submitted")
    avg_steps = sum(t["step_count"] for t in trajs) / total
    avg_cost = sum(t["cost"] for t in trajs) / total

    # ── Common failure patterns
    failure_reasons: dict[str, int] = {}
    for t in trajs:
        if t["exit_status"] != "Submitted":
            for step in t["steps"]:
                if step.returncode is not None and step.returncode != 0:
                    # Categorize by action type + abbreviated command
                    key = f"{step.action_type}: {step.command[:50]}"
                    failure_reasons[key] = failure_reasons.get(key, 0) + 1
                    break  # Only count first failure per trajectory

    common_failures = [
        {"pattern": k, "count": v} for k, v in sorted(failure_reasons.items(), key=lambda x: -x[1])
    ][:10]

    # ── Efficiency trend (grouped by date)
    from datetime import datetime

    daily: dict[str, dict] = {}
    for t in trajs:
        day = datetime.fromtimestamp(t["mtime"]).strftime("%Y-%m-%d")
        daily.setdefault(day, {"count": 0, "steps": 0, "cost": 0.0, "success": 0})
        daily[day]["count"] += 1
        daily[day]["steps"] += t["step_count"]
        daily[day]["cost"] += t["cost"]
        if t["exit_status"] == "Submitted":
            daily[day]["success"] += 1

    efficiency = []
    for day in sorted(daily):
        d = daily[day]
        efficiency.append(
            {
                "date": day,
                "runs": d["count"],
                "avg_steps": round(d["steps"] / d["count"], 1),
                "avg_cost": round(d["cost"] / d["count"], 4),
                "success_rate": round(d["success"] / d["count"], 3),
            }
        )

    # ── Heuristic suggestions
    suggestions = _generate_suggestions(trajs, successes, total, avg_steps)

    result = {
        "total_trajectories": total,
        "avg_steps": round(avg_steps, 1),
        "avg_cost": round(avg_cost, 4),
        "success_rate": round(successes / total, 3) if total > 0 else 0.0,
        "common_failures": common_failures,
        "suggestions": suggestions,
        "efficiency_trend": efficiency,
    }

    _patterns_cache = result
    _patterns_cache_ts = now
    return result


def _generate_suggestions(trajs: list, successes: int, total: int, avg_steps: float) -> list[str]:
    """Generate heuristic suggestions from trajectory patterns."""
    suggestions = []

    success_rate = successes / total if total > 0 else 0
    if success_rate < 0.5:
        suggestions.append(
            "Success rate is below 50%. Consider breaking goals into smaller, more specific tasks."
        )
    elif success_rate < 0.8:
        suggestions.append(
            "Success rate is improving but below 80%. Add explicit verification criteria to goals."
        )

    if avg_steps > 30:
        suggestions.append(
            f"Average step count is high ({avg_steps:.0f}). Complex tasks may benefit from decomposition."
        )

    # Check for high retry rates
    high_retry = sum(1 for t in trajs if t["step_count"] > 50)
    if high_retry > total * 0.2:
        suggestions.append(
            f"{high_retry} runs exceeded 50 steps. Consider adding early-exit conditions."
        )

    if not suggestions:
        suggestions.append("Pipeline is performing well. Continue monitoring efficiency trends.")

    return suggestions


def _empty_patterns() -> dict:
    return {
        "total_trajectories": 0,
        "avg_steps": 0.0,
        "avg_cost": 0.0,
        "success_rate": 0.0,
        "common_failures": [],
        "suggestions": ["No trajectory data available. Run a pipeline to generate data."],
        "efficiency_trend": [],
    }


# ── Audit Data ──────────────────────────────────────────────────────────────


def get_audit_data(filename: str) -> dict:
    """
    Build a complete audit record for a trajectory.

    Returns the full chronological event log, file change manifest,
    and chain of evidence suitable for compliance review.
    """
    try:
        traj = load_trajectory(filename)
    except FileNotFoundError:
        return {"error": f"Trajectory not found: {filename}"}

    steps = parse_steps(traj)
    info = traj.get("info", {})

    # Chronological event log
    events = []
    for step in steps:
        events.append(
            {
                "step": step.index,
                "action_type": step.action_type,
                "command": step.command,
                "target": step.file_touched,
                "returncode": step.returncode,
                "reasoning_length": len(step.reasoning),
                "result_length": len(step.result),
            }
        )

    # File change manifest
    files_modified: dict[str, dict[str, str | int]] = {}
    for step in steps:
        if step.file_touched and step.action_type in ("edit", "write"):
            if step.file_touched not in files_modified:
                files_modified[step.file_touched] = {
                    "file": step.file_touched,
                    "first_touch_step": step.index,
                    "modifications": 0,
                }
            modifications = files_modified[step.file_touched]["modifications"]
            files_modified[step.file_touched]["modifications"] = (
                modifications + 1 if isinstance(modifications, int) else 1
            )

    # Chain of evidence
    model_name = info.get("config", {}).get("model", {}).get("model_name", "unknown")

    return {
        "filename": filename,
        "model": model_name,
        "exit_status": info.get("exit_status", "unknown"),
        "step_count": len(steps),
        "total_cost": info.get("model_stats", {}).get("instance_cost", 0.0),
        "api_calls": info.get("model_stats", {}).get("api_calls", 0),
        "events": events,
        "files_changed": list(files_modified.values()),
        "version": info.get("mini_version", "unknown"),
    }


# ── Trajectory Learning Store ──────────────────────────────────────────────
# Stores trajectory outcomes in claude-flow memory (HNSW vector search)
# so future tasks can retrieve similar past trajectories as context.

MCP_URL = os.environ.get("JUSTAI_MCP_URL", "http://127.0.0.1:3100")
MCP_RPC = f"{MCP_URL}/rpc"
TRAJECTORY_NAMESPACE = "justai-trajectories"


@dataclass
class TrajectoryMatch:
    key: str
    goal: str
    steps: list[str]
    outcome: str
    similarity: float
    duration: float = 0.0
    tech_stack: list[str] = field(default_factory=list)


def _mcp_call(method: str, params: dict) -> dict:
    """Make a JSON-RPC 2.0 call to claude-flow MCP."""
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000),
            "method": "tools/call",
            "params": {"name": method, "arguments": params},
        }
    ).encode()
    req = urllib.request.Request(
        MCP_RPC, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    content = data.get("result", {}).get("content", [])
    for item in content:
        if item.get("type") == "text":
            return json.loads(item["text"])
    return {}


class TrajectoryStore:
    """Store and retrieve trajectory outcomes via claude-flow memory."""

    def store(
        self,
        goal: str,
        steps: list[str],
        outcome: str,
        duration: float = 0.0,
        tech_stack: list[str] | None = None,
    ) -> bool:
        """Store a trajectory outcome for future retrieval."""
        key = f"trajectory/{goal[:50].replace(' ', '-').lower()}-{int(time.time())}"
        value = json.dumps(
            {
                "goal": goal,
                "steps": steps,
                "outcome": outcome,
                "duration": duration,
                "tech_stack": tech_stack or [],
                "stored_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )
        result = _mcp_call(
            "memory_store",
            {
                "key": key,
                "value": value,
                "namespace": TRAJECTORY_NAMESPACE,
            },
        )
        return result.get("success", False) or result.get("stored", False)

    def search(self, query: str, limit: int = 5) -> list[TrajectoryMatch]:
        """Search for similar trajectories using HNSW vector search."""
        result = _mcp_call(
            "memory_search",
            {
                "query": query,
                "namespace": TRAJECTORY_NAMESPACE,
                "limit": limit,
            },
        )
        matches = []
        for r in result.get("results", []):
            key = r.get("key", "")
            similarity = r.get("similarity", 0.0)
            raw_value = r.get("value", "{}")

            # Search results may truncate long values — retrieve full value
            try:
                data = json.loads(raw_value)
            except (json.JSONDecodeError, TypeError):
                # Truncated — do a full retrieve
                try:
                    full = _mcp_call(
                        "memory_retrieve", {"key": key, "namespace": TRAJECTORY_NAMESPACE}
                    )
                    val = full.get("value", {})
                    data = val if isinstance(val, dict) else json.loads(str(val))
                except Exception:
                    continue

            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    continue

            matches.append(
                TrajectoryMatch(
                    key=key,
                    goal=data.get("goal", ""),
                    steps=data.get("steps", []),
                    outcome=data.get("outcome", ""),
                    similarity=similarity,
                    duration=data.get("duration", 0.0),
                    tech_stack=data.get("tech_stack", []),
                )
            )
        matches.sort(key=lambda m: m.similarity, reverse=True)
        return matches

    @staticmethod
    def format_as_context(matches: list[TrajectoryMatch]) -> str:
        """Format trajectory matches as context for an agent prompt."""
        if not matches:
            return ""
        lines = ["Similar past trajectories (use as reference):"]
        for i, m in enumerate(matches):
            lines.append(f"\n--- Trajectory {i + 1} (similarity: {m.similarity:.2f}) ---")
            lines.append(f"Goal: {m.goal}")
            lines.append(f"Outcome: {m.outcome}")
            lines.append(f"Steps: {' → '.join(m.steps)}")
            if m.tech_stack:
                lines.append(f"Tech: {', '.join(m.tech_stack)}")
            if m.duration:
                lines.append(f"Duration: {m.duration:.1f}s")
        return "\n".join(lines)
