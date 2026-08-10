"""Fail-closed Bubblewrap execution boundary (Atom C).

Every arbitrary shell command the executor path runs — the model-produced task
action and the task's success-criteria check — goes through this boundary.
There is NO escape hatch: no environment variable or flag runs a command
outside the sandbox. If the boundary cannot be constructed (bwrap missing,
workdir invalid), ``SandboxUnavailable`` is raised and the caller must treat
the command as "did not and will not run" — fail closed, never a bare exec.

Isolation contract (Codex 2026-08-09 18:16, accepted):
  * ``--unshare-all`` (+ explicit ``--unshare-net``): no network, fresh pid/ipc/
    uts/cgroup/user namespaces; ``--die-with-parent``; ``--new-session``;
    ``--cap-drop ALL``.
  * ``--clearenv`` + explicit allowlist: the guest env is a fixed base
    (PATH/HOME/TMPDIR) plus allowlisted pass-throughs (LANG/LC_*/TZ). Executor
    credentials and host secrets never enter.
  * Read-only system roots for the loader/interpreter only: /usr /bin /sbin
    /lib /lib64, plus /etc/alternatives (Debian/Ubuntu resolves /usr/bin/python3
    THROUGH it — a narrow ro slice, never a blanket /etc bind).
  * Fresh /proc, minimal /dev, tmpfs /tmp.
  * Exactly ONE writable window into the real filesystem: the task workdir.
  * Timeout with process-group cleanup: bwrap leads a new session; on timeout
    the whole group is killed (TERM then KILL) — no leaked children.

CI tests mock the runner (``subprocess.Popen``); the pure argv builder is the
asserted unit. Live effect tests (sibling/parent/network denial, greeting.py
creation) run only where bwrap exists.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


class SandboxUnavailable(RuntimeError):
    """The sandbox could not be constructed; the command did not run."""


@dataclass(frozen=True)
class SandboxResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool


_DEFAULT_ENV_ALLOWLIST: tuple[str, ...] = ("LANG", "LC_ALL", "LC_CTYPE", "TZ")

_RO_SYSTEM_PATHS: tuple[str, ...] = (
    "/usr",
    "/bin",
    "/sbin",
    "/lib",
    "/lib64",
    "/etc/alternatives",
)


def _resolve_bwrap(bwrap_path: str | None) -> str:
    candidate = bwrap_path or shutil.which("bwrap")
    if not candidate:
        raise SandboxUnavailable("bwrap not found on PATH; refusing to run unsandboxed")
    if not (os.path.isfile(candidate) and os.access(candidate, os.X_OK)):
        raise SandboxUnavailable(
            f"bwrap at {candidate!r} is not an executable file; "
            "refusing to run unsandboxed"
        )
    return candidate


def build_guest_env(
    workdir: str,
    *,
    allowlist: Sequence[str] = _DEFAULT_ENV_ALLOWLIST,
    host_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Explicit guest environment (post ``--clearenv``): fixed base plus
    allowlisted pass-throughs. Nothing else can leak in."""
    src = os.environ if host_env is None else host_env
    wd = str(Path(workdir).resolve())
    env: dict[str, str] = {"PATH": "/usr/bin:/bin", "HOME": wd, "TMPDIR": "/tmp"}
    for key in allowlist:
        if key in src:
            env[key] = src[key]
    return env


def build_bwrap_argv(
    command: Sequence[str],
    workdir: str,
    *,
    bwrap_path: str,
    env: Mapping[str, str],
    ro_system_paths: Sequence[str] = _RO_SYSTEM_PATHS,
) -> list[str]:
    """Pure argv builder — the unit CI asserts on; launches nothing."""
    if not command:
        raise ValueError("command must be a non-empty argv sequence")
    wd = str(Path(workdir).resolve())
    argv: list[str] = [
        bwrap_path,
        "--unshare-all",
        "--unshare-net",
        "--die-with-parent",
        "--new-session",
        "--cap-drop",
        "ALL",
        "--clearenv",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
    ]
    for p in ro_system_paths:
        argv += ["--ro-bind-try", p, p]
    argv += ["--bind", wd, wd, "--chdir", wd]
    for key in sorted(env):
        argv += ["--setenv", key, env[key]]
    argv += ["--", *command]
    return argv


def _kill_process_group(pid: int) -> None:
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return


def run_sandboxed(
    command: Sequence[str],
    workdir: str,
    *,
    timeout: float = 60.0,
    bwrap_path: str | None = None,
    env_allowlist: Sequence[str] = _DEFAULT_ENV_ALLOWLIST,
    host_env: Mapping[str, str] | None = None,
) -> SandboxResult:
    """Run ``command`` inside the boundary rooted at ``workdir``.

    Raises SandboxUnavailable (fail closed) when the boundary cannot be
    constructed. Enforces ``timeout`` with whole-process-group cleanup.
    """
    resolved = _resolve_bwrap(bwrap_path)
    wd = Path(workdir).resolve()
    if not wd.is_dir():
        raise SandboxUnavailable(
            f"workdir {str(wd)!r} does not exist or is not a directory"
        )
    guest_env = build_guest_env(str(wd), allowlist=env_allowlist, host_env=host_env)
    argv = build_bwrap_argv(command, str(wd), bwrap_path=resolved, env=guest_env)

    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        text=True,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
        return SandboxResult(proc.returncode, out, err, timed_out=False)
    except subprocess.TimeoutExpired:
        _kill_process_group(proc.pid)
        try:
            out, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
        rc = proc.returncode if proc.returncode is not None else -signal.SIGKILL
        return SandboxResult(rc, out or "", err or "", timed_out=True)
