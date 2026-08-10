"""Atom C: fail-closed Bubblewrap execution boundary (Codex 18:16 contract).

Contract: fail closed if bwrap is absent; no unsandboxed escape hatch;
injected/mocked runner tests in CI; --unshare-all --die-with-parent --clearenv;
no network; read-only loader roots; minimal /proc and /dev; tmpfs /tmp; exactly
the task workdir writable; explicit environment allowlist; timeout/process-group
cleanup; and live effect tests proving sibling/parent/network denial plus
workdir greeting.py creation (skipped where bwrap is absent).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

HAVE_BWRAP = shutil.which("bwrap") is not None
FAKE_BWRAP = sys.executable  # an executable file that satisfies the resolver


# ── argv contract (pure builder; no process launch) ──────────────────────────


def _argv(workdir: str, command=("echo", "hi")) -> list[str]:
    from justai.sandbox import build_bwrap_argv, build_guest_env

    env = build_guest_env(workdir)
    return build_bwrap_argv(command, workdir, bwrap_path="/usr/bin/bwrap", env=env)


def test_argv_has_required_isolation_flags(tmp_path):
    argv = _argv(str(tmp_path))
    for flag in (
        "--unshare-all",
        "--unshare-net",
        "--die-with-parent",
        "--new-session",
        "--clearenv",
    ):
        assert flag in argv, f"missing {flag}"
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert argv[argv.index("--proc") + 1] == "/proc"
    assert argv[argv.index("--dev") + 1] == "/dev"
    assert argv[argv.index("--tmpfs") + 1] == "/tmp"


def test_only_writable_bind_is_the_task_workdir(tmp_path):
    wd = str(tmp_path.resolve())
    argv = _argv(wd)
    bind_idxs = [i for i, tok in enumerate(argv) if tok == "--bind"]
    assert len(bind_idxs) == 1, "exactly one rw bind allowed (the task workdir)"
    i = bind_idxs[0]
    assert argv[i + 1] == wd and argv[i + 2] == wd
    assert "--ro-bind-try" in argv, "system roots must be read-only"
    assert argv[argv.index("--chdir") + 1] == wd


def test_command_is_isolated_after_double_dash(tmp_path):
    argv = _argv(str(tmp_path), command=("bash", "-o", "pipefail", "-c", "echo hi"))
    dd = argv.index("--")
    assert argv[dd + 1 :] == ["bash", "-o", "pipefail", "-c", "echo hi"]


def test_env_allowlist_drops_host_secrets(tmp_path):
    from justai.sandbox import build_guest_env

    wd = str(tmp_path.resolve())
    env = build_guest_env(
        wd,
        host_env={
            "SECRET_TOKEN": "nope",
            "JUSTAI_LLM_KEY": "nope",
            "LANG": "C.UTF-8",
            "PATH": "/evil",
        },
    )
    assert "SECRET_TOKEN" not in env
    assert "JUSTAI_LLM_KEY" not in env, "executor credentials must not enter the sandbox"
    assert env["PATH"] == "/usr/bin:/bin"
    assert env["HOME"] == wd
    assert env["LANG"] == "C.UTF-8"


# ── fail closed: no path runs a command without bwrap ────────────────────────


def test_fail_closed_when_bwrap_absent(tmp_path):
    import justai.sandbox as sb

    with mock.patch.object(sb.shutil, "which", return_value=None), mock.patch.object(
        sb.subprocess, "Popen"
    ) as popen:
        with pytest.raises(sb.SandboxUnavailable):
            sb.run_sandboxed(["echo", "hi"], str(tmp_path))
        popen.assert_not_called()


def test_fail_closed_when_workdir_missing(tmp_path):
    import justai.sandbox as sb

    with mock.patch.object(sb.subprocess, "Popen") as popen:
        with pytest.raises(sb.SandboxUnavailable):
            sb.run_sandboxed(
                ["echo", "hi"], str(tmp_path / "nope"), bwrap_path=FAKE_BWRAP
            )
        popen.assert_not_called()


def test_no_unsandboxed_escape_hatch_in_code():
    """No code path consults an env var to bypass the sandbox (AST; docstrings
    excluded so documentation of the rule does not false-positive)."""
    import ast

    import justai.sandbox as sb

    tree = ast.parse(Path(sb.__file__).read_text())
    docstrings = {
        ast.get_docstring(n, clean=False)
        for n in ast.walk(tree)
        if isinstance(
            n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        )
        and ast.get_docstring(n, clean=False) is not None
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in docstrings:
                continue
            assert "UNSANDBOXED" not in node.value
        if isinstance(node, ast.Name):
            assert "UNSANDBOXED" not in node.id


# ── timeout: whole process group is cleaned up ───────────────────────────────


def test_timeout_kills_the_process_group(tmp_path):
    import justai.sandbox as sb

    proc = mock.Mock()
    proc.pid = 4242
    proc.returncode = None
    proc.communicate.side_effect = [
        subprocess.TimeoutExpired(cmd="bwrap", timeout=1),
        ("", ""),
    ]
    with mock.patch.object(sb.subprocess, "Popen", return_value=proc) as popen, \
        mock.patch.object(sb, "_read_status_events", return_value=[{"child-pid": 4242}]), \
        mock.patch.object(sb.os, "getpgid", return_value=9999) as getpgid, \
        mock.patch.object(sb.os, "killpg") as killpg:
        res = sb.run_sandboxed(
            ["sleep", "99"], str(tmp_path), bwrap_path=FAKE_BWRAP, timeout=0.01
        )
    assert res.timed_out is True
    assert popen.call_args.kwargs["start_new_session"] is True
    getpgid.assert_called_once_with(4242)
    assert killpg.called


# ── P2 (Codex 0106): setup failure vs launched-command exit ──────────────────


def test_argv_includes_status_fd_when_given(tmp_path):
    from justai.sandbox import build_bwrap_argv, build_guest_env

    argv = build_bwrap_argv(
        ["echo", "hi"], str(tmp_path), bwrap_path="/usr/bin/bwrap",
        env=build_guest_env(str(tmp_path)), status_fd=42,
    )
    i = argv.index("--json-status-fd")
    assert argv[i + 1] == "42"
    assert i < argv.index("--"), "status fd must be a bwrap option, not command"


def test_setup_failure_before_child_launch_is_sandbox_unavailable(tmp_path):
    """bwrap started but died during namespace/mount setup: no child-pid event.
    That must be SandboxUnavailable (the command never ran), NOT a normal
    nonzero result that dispatch would mislabel executed_failed."""
    import justai.sandbox as sb

    proc = mock.Mock()
    proc.pid = 4242
    proc.returncode = 1
    proc.communicate.return_value = ("", "bwrap: setting up uid map: Permission denied")
    with mock.patch.object(sb.subprocess, "Popen", return_value=proc), \
        mock.patch.object(sb, "_read_status_events", return_value=[]):
        with pytest.raises(sb.SandboxUnavailable, match="before launching"):
            sb.run_sandboxed(["echo", "hi"], str(tmp_path), bwrap_path=FAKE_BWRAP)


def test_nonzero_exit_after_child_launch_stays_an_executed_result(tmp_path):
    """Contrast: the command really ran and exited 7 — a genuine executed
    failure, preserved as a normal SandboxResult."""
    import justai.sandbox as sb

    proc = mock.Mock()
    proc.pid = 4242
    proc.returncode = 7
    proc.communicate.return_value = ("out", "err")
    with mock.patch.object(sb.subprocess, "Popen", return_value=proc), \
        mock.patch.object(
            sb, "_read_status_events",
            return_value=[{"child-pid": 5}, {"exit-code": 7}],
        ):
        res = sb.run_sandboxed(["false"], str(tmp_path), bwrap_path=FAKE_BWRAP)
    assert res.returncode == 7 and res.timed_out is False


def test_popen_startup_oserror_is_sandbox_unavailable(tmp_path):
    import justai.sandbox as sb

    with mock.patch.object(
        sb.subprocess, "Popen", side_effect=OSError("cannot allocate memory")
    ):
        with pytest.raises(sb.SandboxUnavailable, match="failed to start bwrap"):
            sb.run_sandboxed(["echo", "hi"], str(tmp_path), bwrap_path=FAKE_BWRAP)


def test_timeout_before_child_launch_is_sandbox_unavailable(tmp_path):
    """Timeout with no child-pid event: sandbox construction stalled; the
    command never ran — fail closed, and still clean up the process group."""
    import justai.sandbox as sb

    proc = mock.Mock()
    proc.pid = 4242
    proc.returncode = None
    proc.communicate.side_effect = [
        subprocess.TimeoutExpired(cmd="bwrap", timeout=1),
        ("", ""),
    ]
    with mock.patch.object(sb.subprocess, "Popen", return_value=proc), \
        mock.patch.object(sb, "_read_status_events", return_value=[]), \
        mock.patch.object(sb.os, "getpgid", return_value=9999), \
        mock.patch.object(sb.os, "killpg") as killpg:
        with pytest.raises(sb.SandboxUnavailable, match="before the timeout"):
            sb.run_sandboxed(
                ["sleep", "99"], str(tmp_path), bwrap_path=FAKE_BWRAP, timeout=0.01
            )
    assert killpg.called


def test_live_executable_but_unusable_bwrap_is_sandbox_unavailable(tmp_path):
    """Live, no mocks: an executable that exits without ever launching the
    command (and never emits a child-pid event) must be SandboxUnavailable —
    both the nonzero and the zero-exit impostor."""
    import justai.sandbox as sb

    for impostor in ("/bin/false", "/bin/true"):
        with pytest.raises(sb.SandboxUnavailable):
            sb.run_sandboxed(["echo", "hi"], str(tmp_path), bwrap_path=impostor)


# ── dispatch wiring: the executor path goes THROUGH the boundary ─────────────


def test_run_local_command_routes_through_sandbox(tmp_path, monkeypatch):
    """_run_local_command must invoke the sandbox runner with the bash argv and
    the task workdir — and must NOT reach subprocess.run directly."""
    from justai import agent_dispatch as ad
    from justai.sandbox import SandboxResult

    monkeypatch.setenv("JUSTAI_TASK_WORKDIR", str(tmp_path))
    ran = {}

    def fake_run_sandboxed(command, workdir, *, timeout, **kwargs):
        ran["command"] = list(command)
        ran["workdir"] = workdir
        ran["timeout"] = timeout
        return SandboxResult(0, "ok-out", "", False)

    with mock.patch.object(ad, "run_sandboxed", side_effect=fake_run_sandboxed), \
        mock.patch.object(ad.subprocess, "run") as raw_run:
        ok, out = ad._run_local_command("echo hello")

    assert ok is True and "ok-out" in out
    assert ran["command"] == ["bash", "-o", "pipefail", "-c", "echo hello"]
    assert ran["workdir"] == str(tmp_path)
    assert ran["timeout"] == ad.LOCAL_EXEC_TIMEOUT
    raw_run.assert_not_called()


def test_run_local_command_timeout_message_preserved(tmp_path, monkeypatch):
    from justai import agent_dispatch as ad
    from justai.sandbox import SandboxResult

    monkeypatch.setenv("JUSTAI_TASK_WORKDIR", str(tmp_path))
    with mock.patch.object(
        ad, "run_sandboxed", return_value=SandboxResult(-9, "", "", True)
    ):
        ok, out = ad._run_local_command("sleep 99")
    assert ok is False
    assert "timed out" in out


def test_verify_task_routes_through_sandbox(tmp_path, monkeypatch):
    from justai import agent_dispatch as ad
    from justai.sandbox import SandboxResult
    from justai.scope_planner import AgentType, RiskLevel, Task

    monkeypatch.setenv("JUSTAI_TASK_WORKDIR", str(tmp_path))
    task = Task("t", "d", AgentType.MINI, RiskLevel.R0, "test -f greeting.py", [])
    ran = {}

    def fake_run_sandboxed(command, workdir, *, timeout, **kwargs):
        ran["command"] = list(command)
        ran["workdir"] = workdir
        return SandboxResult(0, "verified", "", False)

    with mock.patch.object(ad, "run_sandboxed", side_effect=fake_run_sandboxed), \
        mock.patch.object(ad.subprocess, "run") as raw_run:
        passed, out = ad._verify_task(task)

    assert passed is True and "verified" in out
    assert ran["command"] == ["bash", "-o", "pipefail", "-c", "test -f greeting.py"]
    assert ran["workdir"] == str(tmp_path)
    raw_run.assert_not_called()


def test_sandbox_unavailable_is_an_error_not_an_executed_failure(tmp_path, monkeypatch):
    """Fail-closed effect at the operator surface: when the sandbox cannot be
    constructed the task action is 'error' (did not run), never executed/
    executed_failed, and the reason reaches the operator detail."""
    from justai import agent_dispatch as ad
    from justai.sandbox import SandboxUnavailable
    from justai.scope_planner import AgentType, RiskLevel, Task

    monkeypatch.setenv("JUSTAI_TASK_WORKDIR", str(tmp_path))
    task = Task("t", "make greeting", AgentType.MINI, RiskLevel.R0, "", [])

    with mock.patch.object(
        ad, "_llm_call", return_value='{"command": "echo hi"}'
    ), mock.patch.object(
        ad,
        "run_sandboxed",
        side_effect=SandboxUnavailable("bwrap not found on PATH"),
    ), mock.patch.object(ad.subprocess, "run") as raw_run:
        outcome, detail = ad._perform_task_action(task)

    assert outcome == "error", "sandbox-unavailable must be a pre-execution error"
    assert "bwrap not found" in detail, "reason must reach the operator"
    raw_run.assert_not_called()


def test_verify_task_fails_closed_when_sandbox_unavailable(tmp_path, monkeypatch):
    from justai import agent_dispatch as ad
    from justai.sandbox import SandboxUnavailable
    from justai.scope_planner import AgentType, RiskLevel, Task

    monkeypatch.setenv("JUSTAI_TASK_WORKDIR", str(tmp_path))
    task = Task("t", "d", AgentType.MINI, RiskLevel.R0, "true", [])
    with mock.patch.object(
        ad, "run_sandboxed", side_effect=SandboxUnavailable("bwrap not found")
    ):
        passed, out = ad._verify_task(task)
    assert passed is False, "verification must fail closed, never pass unrun"
    assert "bwrap not found" in out


# ── live effect proofs (real bwrap; the contract's exact acceptance) ─────────


needs_bwrap = pytest.mark.skipif(not HAVE_BWRAP, reason="bwrap not installed")


@needs_bwrap
def test_live_greeting_py_creatable_in_workdir_only(tmp_path):
    from justai.sandbox import run_sandboxed

    root = tmp_path
    (root / "secret_parent.txt").write_text("PARENT-SECRET\n")
    sibling = root / "sibling"
    sibling.mkdir()
    (sibling / "secret_sibling.txt").write_text("SIBLING-SECRET\n")
    workdir = root / "work"
    workdir.mkdir()

    probe = (
        "import json, os, socket\n"
        "res = {}\n"
        "open('greeting.py', 'w').write(\"print('hello')\\n\")\n"
        "res['greeting'] = os.path.exists('greeting.py')\n"
        "def rd(p):\n"
        "    try:\n"
        "        open(p).read()\n"
        "        return 'LEAKED'\n"
        "    except OSError as e:\n"
        "        return 'blocked:' + e.__class__.__name__\n"
        f"res['sibling'] = rd({str(sibling / 'secret_sibling.txt')!r})\n"
        f"res['parent'] = rd({str(root / 'secret_parent.txt')!r})\n"
        "try:\n"
        "    s = socket.socket(); s.settimeout(3); s.connect(('1.1.1.1', 443))\n"
        "    res['net'] = 'REACHABLE'\n"
        "except OSError as e:\n"
        "    res['net'] = 'blocked:' + e.__class__.__name__\n"
        "res['env_keys'] = sorted(os.environ)\n"
        "open('result.json', 'w').write(json.dumps(res))\n"
    )
    (workdir / "probe.py").write_text(probe)

    result = run_sandboxed(
        ["python3", "probe.py"],
        str(workdir),
        timeout=60,
        host_env={"SECRET_TOKEN": "leak-me", "LANG": "C.UTF-8"},
    )
    assert result.returncode == 0, f"probe failed: {result.stderr[-400:]}"
    data = json.loads((workdir / "result.json").read_text())

    assert data["greeting"] is True and (workdir / "greeting.py").exists()
    assert data["sibling"].startswith("blocked:"), data["sibling"]
    assert data["parent"].startswith("blocked:"), data["parent"]
    assert data["net"].startswith("blocked:"), data["net"]
    assert "SECRET_TOKEN" not in data["env_keys"]
    # Host filesystem outside the workdir is untouched.
    assert (root / "secret_parent.txt").read_text() == "PARENT-SECRET\n"
    assert (sibling / "secret_sibling.txt").read_text() == "SIBLING-SECRET\n"


@needs_bwrap
def test_live_dispatch_end_to_end_greeting(tmp_path, monkeypatch):
    """The wired executor path, live: a real bash command through the real
    sandbox creates greeting.py in the task workdir and verify sees it."""
    from justai import agent_dispatch as ad
    from justai.scope_planner import AgentType, RiskLevel, Task

    monkeypatch.setenv("JUSTAI_TASK_WORKDIR", str(tmp_path))
    ok, out = ad._run_local_command("printf 'print(1)\\n' > greeting.py")
    assert ok is True, out
    assert (tmp_path / "greeting.py").exists(), "greeting.py must exist on host workdir"

    task = Task("t", "d", AgentType.MINI, RiskLevel.R0, "test -f greeting.py", [])
    passed, _ = ad._verify_task(task)
    assert passed is True
