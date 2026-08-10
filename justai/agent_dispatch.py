"""
JustAi - Agent Dispatch (current concrete impl)
===============================================
Today this module IS the dispatch implementation: it calls escalate_plan/
escalate_task with the existing mini-swe-agent flow.

POST-SAFE-MINI MIGRATION: this module's role narrows to "JustAi's
specific configuration + adaptation layer" between JustAi's Plan/Task
types and safe-mini's Chunk/Budget. The actual run loop will move to
safe-mini's SafeMiniRunner. See justai/runner_protocol.py for the
forward-looking dispatch contract.

Current workflow routes task execution through a small-model-first dispatch
ladder:

  1. PSEUDOCODE — Capable model (codex) generates pseudocode from spec
  2. WRITE_TESTS — Mini writes tests per function (with IDs)
  3. WRITE_CODE — Mini writes code to pass tests
  4. ITERATE — Mini runs tests → fixes failures → runs tests (up to N iterations)
  5. ESCALATE — If mini is stuck after N iterations, a capable model takes over

This tests whether front-loading lower-cost agents increases speed, quality,
and success rate compared to the standard single-agent pipeline.

Usage:
    from justai.agent_dispatch import AgentDispatchPipeline, AgentDispatchConfig
    cfg = AgentDispatchConfig(max_mini_iterations=3)
    pipeline = AgentDispatchPipeline(cfg)
    result = pipeline.run("implement feature X", spec="detailed spec...")
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import subprocess
import tempfile

from justai.sandbox import _RO_SYSTEM_PATHS, SandboxUnavailable, run_sandboxed
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from justai.results import DelegationResult
from justai.runner_protocol import (
    AgentRunner,  # noqa: F401  # stub; full integration post-safe-mini
)
from justai.scope_planner import Task

PHASES = ["pseudocode", "write_tests", "write_code", "iterate", "escalate"]

LITELLM_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000/v1")
MINI_MODEL = os.environ.get("JUSTAI_MINI_MODEL", "gpt-5.3-codex")
ESCALATION_MODEL = os.environ.get("JUSTAI_ESCALATION_MODEL", "claude-opus-4-6")


@dataclass
class AgentDispatchConfig:
    max_mini_iterations: int = 3
    mini_model: str = MINI_MODEL
    escalation_model: str = "claude-opus-4-6"
    pseudocode_model: str = "gpt-5.3-codex"
    test_command: str = "python3 -m pytest tests/ -v --tb=short"
    work_dir: str = ""


@dataclass
class PhaseResult:
    phase: str
    status: str  # "done" | "failed" | "skipped"
    output: str
    iterations: int = 1
    model: str = ""
    duration_seconds: float = 0.0


@dataclass
class PipelineResult:
    goal: str
    spec: str
    phases: list[PhaseResult]
    escalated: bool
    total_iterations: int
    model_calls: int
    mini_calls: int
    escalation_calls: int
    duration_seconds: float
    final_output: str = ""


def _is_loopback_url(url: str) -> bool:
    """True only for loopback hosts (127.0.0.0/8, localhost, ::1)."""
    try:
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname or ""
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _execution_endpoint() -> str:
    """Endpoint for model-driven LOCAL EXECUTION. Always loopback: the
    executor override if set (already loopback-validated), else the configured
    LITELLM_URL only when it is loopback, else a loopback default. Never
    follows an off-box ambient LITELLM_BASE_URL."""
    ex = _executor_base_url()
    if ex:
        return ex
    if _is_loopback_url(LITELLM_URL):
        return LITELLM_URL
    return "http://127.0.0.1:4000/v1"


def _executor_base_url() -> str | None:
    """Executor endpoint override — default-OFF.

    When JUSTAI_EXECUTOR_BASE_URL is set, mini/executor calls route here so a
    dedicated coder (e.g. a local Qwen3-Coder-Next server) can run the executor
    while planner/reviewer/pseudocode/escalation stay on LITELLM_BASE_URL.
    Unset/empty -> None -> primary endpoint (byte-for-byte equivalent).
    Endpoint is selected by call site, never inferred from model text.
    """
    url = os.environ.get("JUSTAI_EXECUTOR_BASE_URL", "").strip().rstrip("/").removesuffix("/v1")
    if not url:
        return None
    # Execution endpoints are unconditionally loopback. An off-box executor URL
    # is refused (fail-closed) — a remote executor is a separately configured,
    # separately accepted feature, never an ambient environment escape hatch.
    if not _is_loopback_url(url):
        return None
    return url


def _llm_call(model: str, prompt: str, system: str = "", base_url: str | None = None) -> str:
    """Call LLM via the OpenAI-compatible endpoint. Returns response text.

    base_url overrides the endpoint for this call only (executor routing);
    None uses the primary LITELLM_URL.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4096,
        }
    ).encode()

    headers = {"Content-Type": "application/json"}
    _key = os.environ.get("JUSTAI_LLM_KEY") or os.environ.get("LITELLM_KEY", "")
    if _key:
        headers["Authorization"] = f"Bearer {_key}"
    req = urllib.request.Request(
        f"{base_url or LITELLM_URL}/chat/completions",
        data=payload,
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def _run_tests(test_cmd: str, work_dir: str = "") -> tuple[bool, str]:
    """Run test command and return (passed, output)."""
    try:
        result = subprocess.run(
            ["bash", "-c", test_cmd],
            capture_output=True,
            text=True,
            cwd=work_dir or None,
            timeout=60,
        )
        output = result.stdout[-500:] + result.stderr[-500:]
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "test command timed out"
    except Exception as e:
        return False, str(e)[:200]


class AgentDispatchPipeline:
    """Run the small-model-first agent dispatch workflow."""

    def __init__(self, config: AgentDispatchConfig | None = None):
        self.config = config or AgentDispatchConfig()
        self._model_calls = 0
        self._mini_calls = 0
        self._escalation_calls = 0

    def _call_mini(self, prompt: str, system: str = "") -> str:
        self._model_calls += 1
        self._mini_calls += 1
        return _llm_call(self.config.mini_model, prompt, system, base_url=_executor_base_url())

    def _call_escalation(self, prompt: str, system: str = "") -> str:
        self._model_calls += 1
        self._escalation_calls += 1
        return _llm_call(self.config.escalation_model, prompt, system)

    def _phase_pseudocode(self, goal: str, spec: str) -> PhaseResult:
        """Phase 1: Generate pseudocode from spec using capable model."""
        start = time.time()
        prompt = (
            f"Generate pseudocode for the following goal and specification.\n\n"
            f"Goal: {goal}\n\nSpec:\n{spec}\n\n"
            f"Output clean pseudocode with function signatures, data structures, "
            f"and control flow. No implementation yet — just the skeleton."
        )
        output = _llm_call(
            self.config.pseudocode_model,
            prompt,
            system="You are a code architect. Output pseudocode only.",
        )
        self._model_calls += 1
        self._mini_calls += 1
        return PhaseResult(
            phase="pseudocode",
            status="done",
            output=output,
            model=self.config.pseudocode_model,
            duration_seconds=time.time() - start,
        )

    def _phase_write_tests(self, pseudocode: str, spec: str) -> PhaseResult:
        """Phase 2: Mini writes tests per function."""
        start = time.time()
        prompt = (
            f"Given this pseudocode and spec, write pytest tests for each function.\n\n"
            f"Pseudocode:\n{pseudocode}\n\nSpec:\n{spec}\n\n"
            f"Each test function should have a unique ID in its name. "
            f"Cover happy path and edge cases."
        )
        output = self._call_mini(
            prompt, system="You write Python pytest tests. Output test code only."
        )
        return PhaseResult(
            phase="write_tests",
            status="done",
            output=output,
            model=self.config.mini_model,
            duration_seconds=time.time() - start,
        )

    def _phase_write_code(self, pseudocode: str, tests: str) -> PhaseResult:
        """Phase 3: Mini writes code to pass tests."""
        start = time.time()
        prompt = (
            f"Given this pseudocode and these tests, write the implementation "
            f"code that passes all tests.\n\n"
            f"Pseudocode:\n{pseudocode}\n\nTests:\n{tests}\n\n"
            f"Output implementation code only."
        )
        output = self._call_mini(
            prompt, system="You write Python code. Output implementation only."
        )
        return PhaseResult(
            phase="write_code",
            status="done",
            output=output,
            model=self.config.mini_model,
            duration_seconds=time.time() - start,
        )

    def _phase_iterate(self, code: str, tests: str, test_output: str) -> PhaseResult:
        """Phase 4: Mini fixes failures."""
        start = time.time()
        prompt = (
            f"The following tests are failing. Fix the code.\n\n"
            f"Code:\n{code}\n\nTests:\n{tests}\n\n"
            f"Test output:\n{test_output}\n\n"
            f"Output the fixed code only."
        )
        output = self._call_mini(
            prompt, system="You fix Python code to pass tests. Output fixed code only."
        )
        return PhaseResult(
            phase="iterate",
            status="done",
            output=output,
            model=self.config.mini_model,
            duration_seconds=time.time() - start,
        )

    def _phase_escalate(
        self, goal: str, spec: str, code: str, tests: str, test_output: str
    ) -> PhaseResult:
        """Phase 5: Capable model takes over."""
        start = time.time()
        prompt = (
            f"A junior agent attempted this task but couldn't get tests passing.\n\n"
            f"Goal: {goal}\nSpec:\n{spec}\n\n"
            f"Their code:\n{code}\n\nTests:\n{tests}\n\n"
            f"Last test output:\n{test_output}\n\n"
            f"Fix the code completely. Output the corrected implementation."
        )
        output = self._call_escalation(
            prompt, system="You are a senior engineer fixing code that a junior couldn't get right."
        )
        return PhaseResult(
            phase="escalate",
            status="done",
            output=output,
            model=self.config.escalation_model,
            duration_seconds=time.time() - start,
        )

    def run(self, goal: str, spec: str) -> PipelineResult:
        """Execute the full mini-first pipeline."""
        start = time.time()
        phases: list[PhaseResult] = []

        # Phase 1: Pseudocode
        pseudo_result = self._phase_pseudocode(goal, spec)
        phases.append(pseudo_result)
        pseudocode = pseudo_result.output

        # Phase 2: Write tests
        test_result = self._phase_write_tests(pseudocode, spec)
        phases.append(test_result)
        tests = test_result.output

        # Phase 3: Write code
        code_result = self._phase_write_code(pseudocode, tests)
        phases.append(code_result)
        code = code_result.output

        # Phase 4: Iterate — run tests, fix, repeat
        iteration = 0
        escalated = False
        test_output = ""

        for iteration in range(1, self.config.max_mini_iterations + 1):
            passed, test_output = _run_tests(self.config.test_command, self.config.work_dir)

            if passed:
                phases.append(
                    PhaseResult(
                        phase="iterate",
                        status="done",
                        output=f"Tests pass on iteration {iteration}",
                        iterations=iteration,
                    )
                )
                break

            # Mini attempts fix
            fix_result = self._phase_iterate(code, tests, test_output)
            phases.append(fix_result)
            code = fix_result.output
        else:
            # Mini exhausted iterations — escalate
            escalated = True
            esc_result = self._phase_escalate(goal, spec, code, tests, test_output)
            phases.append(esc_result)
            code = esc_result.output

        return PipelineResult(
            goal=goal,
            spec=spec,
            phases=phases,
            escalated=escalated,
            total_iterations=iteration,
            model_calls=self._model_calls,
            mini_calls=self._mini_calls,
            escalation_calls=self._escalation_calls,
            duration_seconds=time.time() - start,
            final_output=code,
        )


# ── Escalation Strategy ──────────────────────────────────────────────────────
# Wraps task runners with try-cheap-then-escalate logic.
# The AgentDispatchPipeline above is preserved as a standalone LLM pipeline utility.


def _restore_env(name: str, had: bool, value: str) -> None:
    """Restore an env var to its EXACT prior state: delete if it was absent,
    restore its value if it was present. Prevents leaking present-but-empty
    variables into later code that treats presence as meaningful."""
    if had:
        os.environ[name] = value
    else:
        os.environ.pop(name, None)


def _failure_class(result: DelegationResult) -> str:
    """Coarse, nonsecret failure class for cloud escalation context.

    NEVER returns command bytes, stdout/stderr, or a verify-output tail — only
    an opaque class enum derived from the local status string.
    """
    text = (result.result or "").lower()
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "not executed" in text:
        return "not-executed"
    if "verify failed" in text:
        return "verification-failed"
    if "exit" in text:
        return "nonzero-exit"
    return "failed"


def escalate_task(
    task: Task,
    session_ref: str,
    runner: Callable[..., DelegationResult],
) -> DelegationResult:
    """Execute a task with cheap model first, escalate on failure.

    Args:
        task: The task to execute.
        session_ref: Session identifier for tracing.
        runner: A callable(task, session_ref) -> DelegationResult.

    Returns:
        DelegationResult — from first attempt if successful, from escalation otherwise.
    """
    had_model = "JUSTAI_ACTIVE_MODEL" in os.environ
    had_role = "JUSTAI_EXEC_ROLE" in os.environ
    original_model = os.environ.get("JUSTAI_ACTIVE_MODEL", "")
    original_role = os.environ.get("JUSTAI_EXEC_ROLE", "")

    # First attempt: cheap model on the executor endpoint (when configured).
    try:
        os.environ["JUSTAI_ACTIVE_MODEL"] = MINI_MODEL
        os.environ["JUSTAI_EXEC_ROLE"] = "mini"
        result = runner(task, session_ref=session_ref)
    finally:
        _restore_env("JUSTAI_ACTIVE_MODEL", had_model, original_model)
        _restore_env("JUSTAI_EXEC_ROLE", had_role, original_role)

    if result.status == "done":
        return result

    # Escalate: expensive model with failure context
    print(
        f"[escalation] task '{task.title}' failed on {MINI_MODEL}, escalating to {ESCALATION_MODEL}"
    )
    escalated_task = Task(
        title=task.title,
        description=(
            f"{task.description}\n\n"
            f"NOTE: A previous attempt did not succeed "
            f"(status={result.status}, class={_failure_class(result)}). "
            f"Take a different approach."
        ),
        agent=task.agent,
        risk=task.risk,
        success_criteria=task.success_criteria,
        depends_on=task.depends_on,
        session_ref=task.session_ref,
    )

    try:
        os.environ["JUSTAI_ACTIVE_MODEL"] = ESCALATION_MODEL
        os.environ["JUSTAI_EXEC_ROLE"] = "primary"
        escalation_result = runner(escalated_task, session_ref=session_ref)
    finally:
        _restore_env("JUSTAI_ACTIVE_MODEL", had_model, original_model)
        _restore_env("JUSTAI_EXEC_ROLE", had_role, original_role)

    return escalation_result


def _validated_workdir(path: str, source: str) -> str:
    """Accept a task workdir only if binding it read-write is defensible.

    The sandbox binds this directory rw, so a home directory (or anything above
    it) would expose ~/.ssh, credential files and shell rc files to every
    model-produced command. Refuse loudly rather than silently substituting a
    scratch directory: a silent substitute is the exact failure this replaced --
    writes vanish and the operator debugs a phantom missing file.
    """
    resolved = os.path.realpath(os.path.abspath(os.path.expanduser(path)))
    home = os.path.realpath(os.path.expanduser("~"))
    too_broad = (
        resolved == os.sep
        or resolved == home
        or home.startswith(resolved.rstrip(os.sep) + os.sep)
    )
    if too_broad:
        raise SandboxUnavailable(
            f"refusing to use {resolved!r} ({source}) as the task workdir: it is "
            "the filesystem root, your home directory, or a parent of it, and the "
            "sandbox would bind it read-write. Set JUSTAI_TASK_WORKDIR to a "
            "specific project directory."
        )
    if not os.path.isdir(resolved):
        raise SandboxUnavailable(
            f"task workdir {resolved!r} ({source}) does not exist or is not a directory"
        )
    return resolved


def _task_workdir() -> str:
    """The ONLY writable window the sandboxed executor gets (Atom C).

    ``JUSTAI_TASK_WORKDIR`` when configured, otherwise the process working
    directory -- which is where the executor ran before the sandbox landed.
    Defaulting to a private scratch directory instead silently relocated every
    run away from the workspace the operator was standing in, so goals writing
    to real paths failed against a path that exists on the host. Both sources
    go through the same validation.
    """
    configured = os.environ.get("JUSTAI_TASK_WORKDIR", "").strip()
    if configured:
        return _validated_workdir(configured, "JUSTAI_TASK_WORKDIR")
    try:
        cwd = os.getcwd()
    except OSError as exc:
        # The working directory can be deleted out from under a long-lived run.
        raise SandboxUnavailable(
            f"cannot determine the working directory ({exc.__class__.__name__}); "
            "set JUSTAI_TASK_WORKDIR"
        ) from exc
    return _validated_workdir(cwd, "working directory")


def _outside_workdir_paths(command: str, workdir: str) -> list[str]:
    """Absolute paths in the command that are not reachable inside the sandbox.

    Only the workdir (read-write) and a few system roots (read-only) are bound,
    so anything else is invisible in there -- which surfaces as "No such file or
    directory" for a path that exists on the host. The read-only roots are
    excluded because they ARE reachable; reporting /usr/bin/python3 as missing
    would blame the boundary for an ordinary command failure. Regex noise
    ("s/a/b/", "https://x/y", "24/7", "~/notes.txt") is dropped by requiring at
    least two components whose first component is a real directory.
    """
    root = os.path.realpath(workdir)  # run_sandboxed resolves the bind the same way
    reachable = [root] + [os.path.realpath(p) for p in _RO_SYSTEM_PATHS if os.path.exists(p)]
    out: list[str] = []
    seen: set[str] = set()
    for cand in re.findall(r"/[\w./~-]+", command):
        parts = [p for p in cand.split("/") if p]
        if len(parts) < 2 or not os.path.isdir(os.sep + parts[0]):
            continue
        rp = os.path.realpath(cand)
        if rp in seen:
            continue
        if any(rp == r or rp.startswith(r.rstrip(os.sep) + os.sep) for r in reachable):
            continue
        seen.add(rp)
        out.append(cand)
    return out


def _verify_task(task: Task) -> tuple[bool, str]:
    """Run the task's success criteria and return (passed, output)."""
    criteria = task.success_criteria
    if not criteria or criteria.strip() in (
        "echo 'verify manually'",
        "echo 'task completed -- verify manually'",
    ):
        return None, "no automated verification (task not confirmed done)"

    try:
        # Inside the try: _task_workdir() can raise SandboxUnavailable, which
        # must become a (False, reason) verification failure, not an exception
        # escaping to a caller that only understands (bool, str).
        workdir = _task_workdir()
        result = run_sandboxed(
            ["bash", "-o", "pipefail", "-c", criteria],
            workdir,
            timeout=30,
        )
    except SandboxUnavailable as exc:
        # Fail closed: verification did not run, so the task cannot pass.
        return False, f"verification not run, sandbox unavailable: {str(exc)[:200]}"
    except Exception as exc:
        return False, str(exc)[:200]
    if result.timed_out:
        return False, "verification command timed out"
    if result.returncode == 0:
        return True, result.stdout[:500]
    output = (result.stderr or "").strip() or (result.stdout or "").strip()
    # A criterion naming a path the sandbox cannot reach can never pass, even
    # though the path exists on the host. Lead with that: callers truncate this
    # detail, and a note appended after the output is the first thing dropped.
    outside = _outside_workdir_paths(criteria, workdir)
    note = ""
    if outside:
        note = (
            f"[sandbox: verification only sees {workdir}; not visible: "
            + ", ".join(outside[:3])
            + (f" (+{len(outside) - 3} more)" if len(outside) > 3 else "")
            + "] "
        )
    return False, f"{note}exit {result.returncode}: {output}".rstrip()


LOCAL_EXEC_TIMEOUT = int(os.environ.get("JUSTAI_LOCAL_EXEC_TIMEOUT", "60"))

_ACTION_SYSTEM = (
    "You execute ONE JustAi task on a Linux bash shell. Respond with JSON only, "
    "no prose and no markdown fences. Use one of these shapes (real JSON uses "
    "double quotes): {'command': '<one bash command; && and pipes allowed>'} "
    "or {'skip_reason': '<why no shell command should run>'} when the task needs "
    "no shell action or would be unsafe. The command runs under bash -o pipefail. "
    "When writing to a path whose parent directory may not exist yet, create it "
    "first in the same command (mkdir -p \"$(dirname <path>)\" && ...); a plain "
    "redirect into a missing directory fails."
)

# A floor, not a sandbox: refuse a few unambiguously catastrophic commands so a
# bad model action cannot wipe the machine. Real isolation belongs in safe-mini.
_CATASTROPHIC_TARGETS = {
    "/", "/*", "~", "$home", "/etc", "/bin", "/sbin", "/usr", "/var", "/boot",
    "/lib", "/lib64", "/home", "/root", "/sys", "/proc", "/dev",
}


def _is_catastrophic(command: str) -> bool:
    low = " ".join(command.lower().split())
    if ":(){:|:&};:" in low.replace(" ", ""):
        return True
    hard = ("mkfs", " of=/dev/sd", "> /dev/sd", "reboot", "poweroff", "halt")
    if any(h in low for h in hard):
        return True
    toks = low.split()
    if toks and toks[0] == "sudo":
        toks = toks[1:]
    if toks and toks[0] in ("shutdown",):
        return True
    if toks and toks[0] == "rm":
        flags = "".join(t.replace("-", "") for t in toks[1:] if t.startswith("-"))
        args = [t for t in toks[1:] if not t.startswith("-")]
        if "r" in flags and "f" in flags:
            for arg in args:
                if arg in _CATASTROPHIC_TARGETS or arg.rstrip("/") in _CATASTROPHIC_TARGETS:
                    return True
    # Destructive permission/ownership strips against a protected root are
    # catastrophic with OR WITHOUT a recursive flag (`chmod 000 /` locks the
    # system just as `chmod -R 000 /` does). Match on the command verb + a
    # protected-root argument, not on the presence of -R.
    if toks and toks[0] in ("chmod", "chown", "chgrp"):
        args = [t for t in toks[1:] if not t.startswith("-")]
        # drop the mode/owner operand (first non-flag token) — targets follow
        for arg in args[1:]:
            if arg in _CATASTROPHIC_TARGETS or arg.rstrip("/") in _CATASTROPHIC_TARGETS:
                return True
    return False


def _parse_action(raw: str) -> dict:
    """Extract the action dict from a model response.

    The executor contract is JSON-ONLY. The model must return a JSON object
    (optionally inside a ```json fence). Fenced shell and bare prose lines are
    NEVER executed as commands: 8B output variability is not authority to run
    raw text, and a bash fence embedded in output must not become a shell
    action. Anything that is not a JSON object is refused with a skip reason.
    """
    text = (raw or "").strip()

    # 1. Whole response is JSON. This also correctly handles a fence that
    #    appears INSIDE a JSON string value (the object still parses).
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # 2. One exact ```json fenced object. The fence must cover the complete
    #    response; bash/sh/shell fences and prose-wrapped objects are refused.
    lines = text.splitlines()
    if (
        len(lines) >= 3
        and lines[0].strip().lower() == "```json"
        and lines[-1].strip() == "```"
    ):
        try:
            obj = json.loads("\n".join(lines[1:-1]).strip())
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    # No JSON object -> refuse. Never execute fenced shell or a bare line.
    return {"skip_reason": "executor contract violated: response was not a JSON action object"}


def _run_local_command(command: str, timeout: int = LOCAL_EXEC_TIMEOUT) -> tuple[bool, str]:
    """Run one bash command INSIDE the bwrap boundary; return (ok, receipts).

    Raises ``SandboxUnavailable`` when the boundary cannot be constructed: the
    command did not and will not run (fail closed). Callers surface that as a
    pre-execution error, never as an executed failure.
    """
    workdir = _task_workdir()
    try:
        result = run_sandboxed(
            ["bash", "-o", "pipefail", "-c", command],
            workdir,
            timeout=timeout,
        )
    except SandboxUnavailable:
        raise
    except Exception as exc:
        return False, str(exc)[:200]
    if result.timed_out:
        return False, "execution timed out (exit: timeout)"
    out = (result.stdout[-800:] + result.stderr[-400:]).strip()
    ok = result.returncode == 0
    if not ok:
        out = (out + f" (exit {result.returncode})").strip()
        # A path outside the writable window reports "No such file or
        # directory" even though it exists on the host. Say so, or the operator
        # debugs a phantom missing file.
        outside = _outside_workdir_paths(command, workdir)
        if outside:
            out = (
                out
                + f" [sandbox: only {workdir} is available inside the sandbox; "
                + f"outside it: {', '.join(outside[:3])}"
                + (f" (+{len(outside) - 3} more)" if len(outside) > 3 else "")
                + "]"
            )
    return ok, out or f"(exit {result.returncode})"


def _perform_task_action(task: Task) -> tuple[str, str]:
    """Execute the task via the active model's shell action.

    Returns (outcome, detail); outcome is one of
    executed | executed_failed | no_backend | refused | blocked | error.
    ``executed_failed`` means the command RAN and exited nonzero (or timed
    out) — an executed failure with the exit class retained, distinct from
    ``error`` (a pre-execution framework failure).
    """
    model = os.environ.get("JUSTAI_ACTIVE_MODEL") or MINI_MODEL
    # Endpoint role is set explicitly by escalate_task per attempt and never
    # inferred from model text: the escalation attempt uses the primary
    # endpoint; the mini/first/direct-local attempt uses the executor endpoint
    # when JUSTAI_EXECUTOR_BASE_URL is configured (else primary, fail-closed).
    role = os.environ.get("JUSTAI_EXEC_ROLE") or "mini"
    if role == "primary":
        # Escalation attempt uses the configured primary router (may route to a
        # cloud escalation model — an accepted feature, not the executor path).
        action_base_url = None
    else:
        # Mini/first/direct LOCAL EXECUTION path is pinned loopback and never
        # follows an off-box ambient LITELLM_BASE_URL (fail-closed).
        action_base_url = _execution_endpoint()
    prompt = (
        "Task: " + task.title + chr(10) + chr(10) + task.description
        + chr(10) + chr(10) + "Produce the shell command."
    )
    try:
        raw = _llm_call(model, prompt, system=_ACTION_SYSTEM, base_url=action_base_url)
    except Exception as exc:
        return "no_backend", f"execution model unavailable: {str(exc)[:160]}"
    action = _parse_action(raw)
    if action.get("skip_reason"):
        return "refused", str(action["skip_reason"])[:200]
    command = str(action.get("command", "")).strip()
    if not command:
        return "error", "model returned no command"
    if _is_catastrophic(command):
        return "blocked", f"refused catastrophic command: {command[:120]}"
    try:
        ok, out = _run_local_command(command)
    except SandboxUnavailable as exc:
        # Fail closed at the operator surface: the command was never executed.
        return "error", f"sandbox unavailable, command not executed: {str(exc)[:200]}"
    outcome = "executed" if ok else "executed_failed"
    return outcome, "$ " + command[:160] + chr(10) + out[:400]


def _execute_single_local(task: Task, session_ref: str = "") -> DelegationResult:
    """Execute a task's action locally (model-driven), then verify it.

    Honest 3-state: a task is ``done`` only when it BOTH executed and its
    success check passed. Execution without an automated check is
    ``unverified``; anything else (no backend, refusal, blocked command,
    non-zero exit, or a failed check) is ``failed`` -- never a silent success.
    """
    start = time.time()
    outcome, exec_detail = _perform_task_action(task)
    executed = outcome == "executed"
    passed, verify_output = _verify_task(task)

    if executed and passed is True:
        status = "done"
        detail = verify_output[:200]
    elif executed and passed is None:
        status = "unverified"
        detail = f"executed but no automated success check ran: {exec_detail[:150]}"
    elif executed and passed is False:
        status = "failed"
        detail = f"executed, but verify failed: {verify_output[:150]}"
    elif outcome == "executed_failed":
        # The command RAN and exited nonzero/timed out — an executed failure,
        # not a pre-execution ("not executed") failure.
        status = "failed"
        detail = f"executed, but the command failed: {exec_detail[:170]}"
    else:
        status = "failed"
        detail = f"not executed ({outcome}): {exec_detail[:170]}"

    return DelegationResult(
        task_id=f"local-{session_ref or 'task'}",
        title=task.title,
        status=status,
        result=detail,
        duration_seconds=time.time() - start,
    )


def _execute_removed_backend(task: Task, session_ref: str = "") -> DelegationResult:
    """Return an explicit error for backend modes removed in Phase 4 cleanup."""
    return DelegationResult(
        task_id=f"removed-{session_ref or 'task'}",
        title=task.title,
        status="error",
        result="External delegation backend was removed; use local mode.",
        duration_seconds=0.0,
    )


_EXECUTORS = {
    "delegated": _execute_removed_backend,
    "local": _execute_single_local,
    "swarm": _execute_removed_backend,
}


def _normalize_blocked_indices(blocked_indices, n: int) -> dict[int, str]:
    """Validate caller-supplied blocked task indices; return {index: reason}.

    Raises ValueError if any index does not name a task position in [0, n). A
    stray index means the caller (checkpoint) and the plan disagree, and
    silently dropping it would dispatch a task the checkpoint refused — the
    exact false success this guard prevents. Accepts a set or an
    {index: reason} dict. bool is rejected explicitly (it is an int subclass).
    """
    if blocked_indices is None:
        return {}
    # Only None means "omitted". A falsy malformed value (False, 0, "", [], ())
    # must NOT be read as "nothing blocked", and an unsupported iterable must not
    # be silently accepted — require the declared set/dict type before validating.
    if not isinstance(blocked_indices, (set, frozenset, dict)):
        raise ValueError(
            f"blocked_indices must be a set or {{index: reason}} dict, "
            f"got {type(blocked_indices).__name__}"
        )
    normalized: dict[int, str] = {}
    for idx in blocked_indices:
        if isinstance(idx, bool) or not isinstance(idx, int):
            raise ValueError(f"blocked index {idx!r} is not a task position")
        if idx < 0 or idx >= n:
            raise ValueError(f"blocked index {idx} does not name a task (0..{n - 1})")
        reason = blocked_indices[idx] if isinstance(blocked_indices, dict) else "vetoed"
        normalized[idx] = str(reason)
    return normalized


def _dependency_error(depends_on, position: int, n: int) -> str | None:
    """Return an error message if depends_on cannot name already-decided tasks.

    depends_on comes from model-authored JSON, so it is untyped. A dependency
    must be a plain int naming a task BEFORE this one; anything else (wrong type,
    negative, out of range, self, or forward) can never be satisfied and must
    fail the task closed rather than be silently ignored (a negative index would
    even wrap and read a later task's slot).
    """
    if not isinstance(depends_on, list):
        return f"dependency list must be a list, got {type(depends_on).__name__}"
    for dep in depends_on:
        if isinstance(dep, bool) or not isinstance(dep, int):
            return f"dependency index {dep!r} is not an integer"
        if dep < 0 or dep >= n:
            return f"dependency index {dep} is out of range (0..{n - 1})"
        if dep >= position:
            return f"dependency index {dep} does not name an earlier task"
    return None


def escalate_plan(
    tasks: list[Task],
    session_ref: str = "",
    mode: str = "delegated",
    blocked_indices=None,
) -> list[DelegationResult]:
    """Execute a task plan with per-task escalation, PRESERVING task positions.

    Positions are preserved (no compaction): ``depends_on`` indices address the
    ORIGINAL plan, so a dependent of a blocked/failed task is correctly skipped
    rather than silently promoted into a freed slot. ``blocked_indices`` (a set
    or {index: reason} dict of tasks a checkpoint refused) is validated up front;
    a stray index raises ValueError. An unsatisfiable dependency fails its task
    closed with status ``error``.

    Args:
        tasks: Ordered list of tasks from the planner.
        session_ref: Session identifier.
        mode: Execution mode — "delegated", "local", or "swarm".
        blocked_indices: Indices of tasks the checkpoint blocked.
    """
    runner = _EXECUTORS.get(mode, _execute_removed_backend)
    n = len(tasks)
    blocked = _normalize_blocked_indices(blocked_indices, n)
    results: list[DelegationResult | None] = [None] * n

    for i, task in enumerate(tasks):
        if i in blocked:
            results[i] = DelegationResult(
                task_id=f"blocked-{i}",
                title=task.title,
                status="blocked",
                result=f"blocked at checkpoint: {blocked[i]}",
                duration_seconds=0.0,
            )
            print(f"[escalation] task [{i}] '{task.title}' blocked: {blocked[i]}")
            continue

        dep_error = _dependency_error(task.depends_on, i, n)
        if dep_error is not None:
            results[i] = DelegationResult(
                task_id=f"error-{i}",
                title=task.title,
                status="error",
                result=f"dependency error: {dep_error}",
                duration_seconds=0.0,
            )
            print(f"[escalation] task [{i}] '{task.title}' dependency error: {dep_error}")
            continue

        unmet = next(
            (d for d in task.depends_on if results[d] is None or results[d].status != "done"),
            None,
        )
        if unmet is not None:
            results[i] = DelegationResult(
                task_id=f"skipped-{i}",
                title=task.title,
                status="skipped",
                result=f"skipped: dependency [{unmet}] did not complete",
                duration_seconds=0.0,
            )
            print(f"[escalation] task [{i}] '{task.title}' skipped — dependency [{unmet}] not done")
            continue

        results[i] = escalate_task(task, session_ref=session_ref, runner=runner)
        print(f"[escalation] task [{i}] {results[i].status}: {results[i].result[:80]}")

    return [r for r in results if r is not None]
