"""The sandbox must not silently relocate the executor's working directory.

Atom C confined execution to a single writable window, but nothing sets
JUSTAI_TASK_WORKDIR, so every run landed in a random /tmp scratch directory.
Before Atom C the executor inherited the process cwd. The effect was that any
goal writing to a real path failed, with a misleading "No such file or
directory" that named a path which does exist on the host.
"""

from __future__ import annotations

import os
import shutil

import pytest

from justai import agent_dispatch as ad

needs_bwrap = pytest.mark.skipif(shutil.which("bwrap") is None, reason="bwrap not installed")


def test_default_workdir_is_cwd_not_a_scratch_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("JUSTAI_TASK_WORKDIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert os.path.realpath(ad._task_workdir()) == os.path.realpath(str(tmp_path))


def test_configured_workdir_still_wins(tmp_path, monkeypatch):
    other = tmp_path / "explicit"
    other.mkdir()
    monkeypatch.setenv("JUSTAI_TASK_WORKDIR", str(other))
    monkeypatch.chdir(tmp_path)
    assert os.path.realpath(ad._task_workdir()) == os.path.realpath(str(other))


@needs_bwrap
def test_relative_write_lands_in_the_users_working_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("JUSTAI_TASK_WORKDIR", raising=False)
    monkeypatch.chdir(tmp_path)
    ok, out = ad._run_local_command("printf %s HELLO > artifact.txt")
    assert ok is True, out
    assert (tmp_path / "artifact.txt").read_text() == "HELLO"


@needs_bwrap
def test_write_outside_the_workdir_explains_the_boundary(tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.setenv("JUSTAI_TASK_WORKDIR", str(workdir))
    ok, out = ad._run_local_command(f"printf %s HELLO > {outside}/a.txt")
    assert ok is False
    assert "sandbox" in out.lower(), f"failure must name the boundary, got: {out}"
    assert str(workdir) in out, f"failure should name the writable workdir, got: {out}"


# --- The workdir is bound read-write, so a too-broad choice must be refused
#     loudly. Silently substituting a scratch dir is the original bug. ---

def test_home_directory_is_refused(monkeypatch, tmp_path):
    from justai.sandbox import SandboxUnavailable
    monkeypatch.delenv("JUSTAI_TASK_WORKDIR", raising=False)
    monkeypatch.setattr(ad.os, "getcwd", lambda: os.path.expanduser("~"))
    with pytest.raises(SandboxUnavailable, match="home directory"):
        ad._task_workdir()


def test_filesystem_root_is_refused_not_silently_swapped(monkeypatch):
    from justai.sandbox import SandboxUnavailable
    monkeypatch.delenv("JUSTAI_TASK_WORKDIR", raising=False)
    monkeypatch.setattr(ad.os, "getcwd", lambda: "/")
    with pytest.raises(SandboxUnavailable):
        ad._task_workdir()


def test_configured_workdir_is_validated_too(monkeypatch):
    from justai.sandbox import SandboxUnavailable
    monkeypatch.setenv("JUSTAI_TASK_WORKDIR", "/")
    with pytest.raises(SandboxUnavailable):
        ad._task_workdir()


def test_deleted_working_directory_fails_closed(monkeypatch):
    from justai.sandbox import SandboxUnavailable
    def gone():
        raise FileNotFoundError("cwd removed")
    monkeypatch.delenv("JUSTAI_TASK_WORKDIR", raising=False)
    monkeypatch.setattr(ad.os, "getcwd", gone)
    with pytest.raises(SandboxUnavailable, match="working directory"):
        ad._task_workdir()


def test_hint_ignores_regex_and_url_noise(tmp_path):
    # s/a/b/, https://x/y, 24/7 and ~/notes.txt must not be reported as paths.
    noise = "sed s/a/b/ && curl https://x/y && echo 24/7 && cat ~/notes.txt"
    assert ad._outside_workdir_paths(noise, str(tmp_path)) == []


def test_hint_reports_a_real_outside_path(tmp_path):
    found = ad._outside_workdir_paths("printf x > /etc/nope.txt", str(tmp_path))
    assert found == ["/etc/nope.txt"]


def test_hint_does_not_report_paths_inside_the_workdir(tmp_path):
    inside = tmp_path / "sub"
    inside.mkdir()
    assert ad._outside_workdir_paths(f"printf x > {inside}/a.txt", str(tmp_path)) == []
