#!/usr/bin/env python3
"""
JustAi — Checkpoint
====================
Human-in-the-loop gate logic. Implements R0-R3 risk levels.

Design principle (from spec): default posture is AUTONOMOUS.
Bother the human only when genuinely necessary. R2 and R3 are rare.

  R0 — no gate, proceed immediately
  R1 — notify only, auto-proceed after 60s unless vetoed via Discord
  R2 — hard gate, wait for explicit approval (Discord or dashboard)
  R3 — blocked, operator must manually unlock before anything proceeds

AUTO MODE (--auto, or JUSTAI_AUTO_MODE=1 for a caller that does not pass one):
  R0 → proceed immediately (no change)
  R1 → proceed immediately (skip the 60s wait)
  R2 → still requires explicit approval
  R3 → still blocked

Auto mode is a property of one run, not of the process. :func:`evaluate` takes
it as an argument so a caller that has the answer says so; the environment is
only consulted when nobody did. Deriving it from process-global state let a
single ``--auto`` run disable the R1 operator veto for every later run in the
same interpreter — the API server shares one across all requests.

WHICH RUN A GATE BELONGS TO
---------------------------
A gate is identified by :class:`GateIdentity` — a run id and a plan index — and
lives at ``gates/<run_id>/plan-<index>.json``.

It used to be identified by a string built from the session label:
``gates/gate_<session_ref>-plan-<index>.json``. A label is reused on purpose and
is usually not set at all, so two ordinary concurrent runs agreed on a filename
and waited on the same file. One approval released both, including the run the
operator never looked at. An approval is a decision about one task in one run;
anything two runs can name is not an identity. See :mod:`justai.run_identity`.

Three consequences, all of them the point:

- **Legacy gates are ignored.** Nothing reads ``gates/gate_*.json`` any more. A
  leftover approval from the old layout cannot release anything, which is the
  correct reading of a file that names no run.
- **A record that contradicts its path is refused.** A gate copied or left over
  from another run carries that run's id, and is treated as no decision at all
  rather than as an approval. Refusing is the fail-closed direction: an R2 task
  keeps waiting.
- **Cleanup is scoped to one run.** :func:`cleanup_run` removes one run's
  records and can express nothing else, so parallel runs and parallel tests
  cannot unlink each other's gates.

WHO IS DRIVING A RUN
--------------------
A run id scopes a gate to one run. It says nothing about how many processes are
driving that run, and two of them is a real situation: ``--run-id`` resumes a
run whose gates are already on disk, and nothing stopped a resume from starting
while the run it resumes is still going.

:func:`own_run` is the claim. One process owns a run for the whole of its life —
reading the approval, dispatching the work it authorises, and removing the
records afterwards — and a second process asking for the same run is refused
(:class:`RunAlreadyActive`) rather than queued behind it.

Both halves matter. Holding the lock for the gate loop alone left everything
after it unserialised: a second resume woke the moment the first stage ended,
read the operator's single approval — cleanup had not yet re-taken the lock to
remove it — and dispatched the same work. And *waiting* would be the same
defect with a delay: a queued process executes the same run against the same
decision as soon as the first one lets go. Refusing is the fail-closed
direction — nothing ran twice, and the operator still has one run to answer.

WHAT SURVIVES A GATE
--------------------
Scoping decided which file a decision lands in. Three rules decide what happens
to that file afterwards, and each of them replaces a way the decision was lost:

- **A decision on disk is never written over.** The R2 branch marks its gate
  pending with :func:`_claim_gate`, which creates and does not replace. An
  unconditional write destroyed exactly the approval the run was about to wait
  for — a ``--run-id`` resume, a dashboard operator using the run id the API
  returns before the run reaches a gate, or anyone answering the notification
  promptly — and the run then waited forever.
- **A live run's lock is never removed.** ``flock`` excludes the holders of one
  inode, so unlinking the lock file under the lock ended exclusion rather than
  the run: a waiter woke holding an unreachable inode and the next process
  created a second lock at the free name. :func:`cleanup_run` leaves it, and
  :func:`sweep_gate_dirs` renames a directory out of the namespace before
  deleting anything, so no unlink ever happens under a held lock.
- **What is kept is kept on purpose.** A cleaned run leaves a directory holding
  only its lock; :func:`sweep_gate_dirs` collects those once they are old. A
  run interrupted at a gate keeps its records for as long as resuming it is a
  real possibility, because that is what makes ``--run-id`` a resume rather
  than a re-ask.

WHAT A RUN DIRECTORY IS
-----------------------
:func:`run_state` reads one directory and names it, and the two collectors act
on that reading rather than on a rule of their own:

- ``ACTIVE`` — a process holds the run's lock. Never touched, at any age.
- ``RESUMABLE`` — holds a decision, or a gate waiting for one, and is recent
  enough that an operator could still answer it. Kept.
- ``ABANDONED`` — the same, past the recovery window. Nobody is coming back for
  it; :func:`prune_abandoned_runs` collects it.
- ``TERMINAL`` — holds no decision at all: cleaned up, or never gated. Only its
  lock is left, and :func:`sweep_gate_dirs` collects it once it is old.
- ``FOREIGN`` — holds a file this module did not write. Never touched.

"Kept indefinitely" was the previous answer for anything holding a record, and
it is not a bound: a run killed while parked at R2 leaves a gate nobody will
ever decide, and ``gates/`` then grew by one directory per killed run forever.
Retention is now a window (:data:`GATE_ABANDON_TTL_SECONDS`, days) and a count
(:data:`GATE_MAX_RETAINED_RUNS`), which keeps ordinary resumability and cannot
grow without limit.

Nothing is ever deleted for its name alone. A directory leaving the namespace
is renamed to ``.trash-<run_id>-<fresh uuid>`` and labelled with a marker
naming this module, and only a directory whose name, marker and contents all
agree is deleted. Sweeping by prefix removed an operator's own
``.trash-``-named directory, and deriving the parked name from the run id alone
meant a second sweep of one run destroyed the first sweep's unfinished work.

Discord integration: posts to DISCORD_RELAY_CHANNEL_ID if token is set.
If Discord is not configured, R1 auto-proceeds silently, R2/R3 block
until a local signal file is written by the operator.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext, suppress
from dataclasses import dataclass
from enum import Enum
from fnmatch import fnmatch
from pathlib import Path

from justai.run_identity import is_run_id, parse_run_id
from justai.scope_planner import RiskLevel, Task

DISCORD_BOT_TOKEN = os.environ.get("RELAY_COORDINATOR_TOKEN", "")
DISCORD_CHANNEL_ID = os.environ.get("DISCORD_RELAY_CHANNEL_ID", "1491134768077865090")
R1_TIMEOUT_SECONDS = int(os.environ.get("JUSTAI_R1_TIMEOUT", "60"))
GATE_SIGNAL_DIR = Path(os.environ.get("JUSTAI_RUNTIME_ROOT", "/tmp/justai")) / "gates"

# How often a waiting gate re-reads its file. This is how quickly a decision is
# noticed, never what is decided, so a test may shorten it without touching the
# fail-closed contract: R2 still waits for an approval, R3 still never runs.
_POLL_OVERRIDE = os.environ.get("JUSTAI_GATE_POLL_SECONDS", "").strip()
R1_POLL_SECONDS = float(_POLL_OVERRIDE) if _POLL_OVERRIDE else 2.0
R2_POLL_SECONDS = float(_POLL_OVERRIDE) if _POLL_OVERRIDE else 3.0

#: Per-run advisory lock. Lives inside the run's own directory, so two runs
#: never contend and two processes driving one run (a resume) always do.
#:
#: Exclusion is a property of the *inode* this name points at, not of the name,
#: so nothing removes it while a run directory is in use — see
#: :func:`cleanup_run`. Unlinking it under the lock let the next process create
#: a second file at the same name and hold the same run at the same time.
LOCK_FILENAME = ".lock"

#: How long a spent run directory is kept before :func:`sweep_gate_dirs` may
#: remove it. Spent means the run's decisions have been cleaned up and only the
#: lock is left; a directory that still holds a gate record is resume material
#: and is never swept, at any age.
#:
#: An hour is a margin, not a retention policy. A spent directory holds nothing
#: an operator could want — its only content is a zero-byte lock — so the delay
#: exists solely to keep removal far away from anything in flight, and the
#: window it is guarding against is the microseconds another process spends
#: between creating the directory and locking the file inside it. Keeping it
#: short is what stops a machine that runs often from accumulating them.
GATE_TOMBSTONE_TTL_SECONDS = float(os.environ.get("JUSTAI_GATE_TOMBSTONE_TTL", str(3600)))

#: How long a run interrupted at a gate is kept before
#: :func:`prune_abandoned_runs` may collect it.
#:
#: This one *is* a retention policy, and it is measured in days because the
#: thing it is waiting for is a person: an R2 gate is a question asked of an
#: operator, and a weekend is an ordinary answer time. What it bounds is the
#: other end — a run killed while parked at a gate leaves a question nobody
#: will ever answer, and the previous rule ("a directory holding a record is
#: kept indefinitely") meant one directory per killed run, forever.
GATE_ABANDON_TTL_SECONDS = float(os.environ.get("JUSTAI_GATE_ABANDON_TTL", str(7 * 24 * 3600)))

#: How many resumable runs are kept regardless of age, newest first.
#:
#: A window alone is not a bound: enough interrupted runs inside it is still
#: unbounded. This is the backstop, set high enough that reaching it means
#: something is looping rather than that an operator is behind on approvals.
GATE_MAX_RETAINED_RUNS = int(os.environ.get("JUSTAI_GATE_MAX_RUNS", "128"))

#: Only these are gate records. Cleanup refuses to remove anything else.
_GATE_GLOB = "plan-*.json"
_TMP_PREFIX = ".gate-"

#: Where a directory is parked between leaving the namespace and being deleted.
#: Not a run id, so the sweep never mistakes one for a candidate.
_TRASH_PREFIX = ".trash-"

#: A tombstone this module wrote: the run it came from, and a value minted for
#: this one parking. The second half is what makes the name collision-free —
#: ``.trash-<run_id>`` was one name per run, so a second sweep of a run id
#: landed on the first sweep's unfinished work and cleared it out of the way.
_TOMBSTONE_NAME = re.compile(rf"\A{re.escape(_TRASH_PREFIX)}([0-9a-f]{{32}})-[0-9a-f]{{32}}\Z")

#: How many names to try before giving up. A fresh UUID does not collide; this
#: exists so a bug elsewhere cannot turn into an unbounded loop.
_TOMBSTONE_ATTEMPTS = 8

#: Written into a directory before it is parked, and checked before it is
#: deleted. A name proves nothing about who wrote it — an operator's own
#: ``.trash-``-named directory was deleted for its name alone.
TOMBSTONE_MARKER = ".justai-tombstone.json"
_MARKER_OWNER = "justai.checkpoint"
_MARKER_KIND = "swept-gate-directory"


class RunAlreadyActive(RuntimeError):
    """Another process is already driving this run, so this one must not.

    Raised by :func:`own_run`. Refusing is fail-closed: a second process that
    waited would execute the same run against the same approval as soon as the
    first one released it, which is the double execution rather than a fix for
    it.
    """


class RunState(Enum):
    """What one run directory is, as read off the directory itself.

    The two collectors act on this rather than on a rule of their own, so
    "still going", "still worth resuming" and "nobody is coming back" are one
    reading with one set of names rather than three implicit ones.
    """

    #: No directory. Nothing has been scoped to this run id.
    MISSING = "missing"
    #: Some process holds the run's lock. Never collected, at any age.
    ACTIVE = "active"
    #: Holds a gate record, and is recent enough for `--run-id` to mean resume.
    RESUMABLE = "resumable"
    #: Holds a gate record past the recovery window: a question nobody will
    #: answer now.
    ABANDONED = "abandoned"
    #: Holds no decision — cleaned up, or never reached a gate. Only its lock.
    TERMINAL = "terminal"
    #: Holds something this module did not write. Not ours to collect.
    FOREIGN = "foreign"


@dataclass(frozen=True)
class RunOwnership:
    """Proof that this process is the one driving ``run_id``.

    Handed out by :func:`own_run` and accepted by the operations that would
    otherwise take the run's lock for themselves. ``flock`` blocks a second
    descriptor even inside one process, so a run cleaning up under its own
    claim has to say so rather than queue behind itself.

    It carries no descriptor: a token cannot release a claim, only name one.
    """

    run_id: str
    directory: Path


@dataclass(frozen=True)
class GateIdentity:
    """Which task, in which run, an approval is about.

    ``session_ref`` rides along as the human label shown to the operator and
    recorded in the gate file. It is deliberately not part of the identity:
    labels are reused, and that reuse is what let one approval release two runs.

    Raises:
        InvalidRunId: ``run_id`` is not a UUID.
        ValueError: ``index`` is not a plan position.
    """

    run_id: str
    index: int
    session_ref: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", parse_run_id(self.run_id))
        if not isinstance(self.index, int) or isinstance(self.index, bool) or self.index < 0:
            raise ValueError(f"plan index must be a non-negative int, got {self.index!r}")

    @property
    def gate_name(self) -> str:
        return f"plan-{self.index}.json"

    def describe(self) -> str:
        """How this gate is named at an operator."""
        label = self.session_ref or "unlabelled"
        return f"run {self.run_id} (session: {label}), plan task {self.index}"


def _is_auto_mode() -> bool:
    """Read auto mode from the environment.

    This is the fallback for a caller that has no per-run answer to give — a
    direct ``evaluate`` call, or a shell that exported ``JUSTAI_AUTO_MODE``. A
    caller that knows passes ``auto=`` instead, and nothing writes this
    variable: a run's mode must not outlive the run.
    """
    return os.environ.get("JUSTAI_AUTO_MODE", "").lower() in ("1", "true", "yes")


def _discord_notify(message: str) -> bool:
    """Post a message to Discord. Returns True if successful."""
    if not DISCORD_BOT_TOKEN:
        return False
    try:
        import urllib.request

        payload = json.dumps({"content": message}).encode()
        req = urllib.request.Request(
            f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages",
            data=payload,
            headers={
                "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
                "Content-Type": "application/json",
                "User-Agent": "DiscordBot (JustAi, 1.0)",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201)
    except Exception:
        return False


def gate_dir(run_id: str) -> Path:
    """The directory holding one run's gates. Validates ``run_id`` first.

    ``GATE_SIGNAL_DIR`` is read at call time, not bound at import, so a test
    that redirects the runtime root redirects this too.
    """
    return GATE_SIGNAL_DIR / parse_run_id(run_id)


def _gate_file(gate: GateIdentity) -> Path:
    return gate_dir(gate.run_id) / gate.gate_name


def gate_path(gate: GateIdentity) -> Path:
    """Where the operator writes a decision about ``gate``, creating the run dir."""
    path = _gate_file(gate)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def run_gate_lock(run_id: str) -> Iterator[Path]:
    """Hold one run's advisory lock for the body, waiting if it is held.

    This is the out-of-band form, for an operation on a run this process is not
    driving — an operator's cleanup while the run is still going. It waits,
    because the operation is short and doing it to a run mid-checkpoint is
    what :func:`cleanup_run` must not do. A process that means to *drive* the
    run takes :func:`own_run` instead, which does not wait: two processes
    executing one run is not something to queue for.

    Scoped to the run, so ordinary concurrent runs never wait on each other.
    Two processes that share a run id — the resume path — do wait, which is the
    point: they would otherwise drive the same gate files at the same time, and
    :func:`cleanup_run` would be free to delete records another process was
    still reading.

    The lock is advisory and held only by this module, so the operator's own
    ``echo '{"status":"approved"}' > <path>`` is never blocked by it.

    Not reentrant. Each call opens its own descriptor, and ``flock`` blocks a
    second descriptor even inside one process, so nesting this on one run id
    deadlocks — including indirectly, via :func:`cleanup_run`, which takes the
    lock itself when it is handed no claim. Inside :func:`own_run`, pass the
    claim along instead of taking this.
    """
    directory = gate_dir(run_id)
    fd = _acquire_run_lock(directory)
    try:
        yield directory
    finally:
        with suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@contextmanager
def own_run(run_id: str) -> Iterator[RunOwnership]:
    """Claim a run for this process, for the whole of its life.

    Held across everything that acts on one decision — reading the approval,
    dispatching the work it authorises, and removing the record afterwards —
    because those are one step from any other process's point of view. The
    checkpoint used to hold the run's lock for the gate loop and release it
    there: a second resume woke as the first stage ended, read the same
    approval, and dispatched the same work.

    Does not wait. A run someone else is driving is refused with
    :class:`RunAlreadyActive`, and refused immediately: queueing would run the
    same run against the same decision a moment later. The caller has been told
    nothing was started, which is what makes it safe to fail.

    The lock file is never unlinked — see :func:`cleanup_run`. Releasing this
    claim releases the ``flock`` and closes the descriptor; the inode stays
    where every other process is looking for it.

    Raises:
        InvalidRunId: ``run_id`` is not a UUID.
        RunAlreadyActive: another process holds this run.
    """
    canonical = parse_run_id(run_id)
    directory = gate_dir(canonical)
    fd = _try_acquire_run_lock(directory)
    if fd is None:
        raise RunAlreadyActive(
            f"run already active: {canonical} is being driven by another process. "
            f"Its gates are at {directory}. Nothing was started; resume it once "
            f"that process has finished."
        )
    try:
        yield RunOwnership(run_id=canonical, directory=directory)
    finally:
        with suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _is_file_at(fd: int, path: Path) -> bool:
    """Whether ``fd`` is open on whatever ``path`` names right now."""
    try:
        on_disk = path.stat()
    except OSError:
        return False
    held = os.fstat(fd)
    return (on_disk.st_dev, on_disk.st_ino) == (held.st_dev, held.st_ino)


def _acquire_run_lock(directory: Path) -> int:
    """Block until this process holds the lock file *currently* at the path.

    ``flock`` excludes holders of one inode, and a path can stop naming the
    inode a waiter is queued on: :func:`sweep_gate_dirs` moves a spent
    directory aside, and the default runtime root is under ``/tmp``, where a
    system reaper does the same thing without asking. A waiter that kept
    whatever it was handed would wake holding an inode nothing can reach by
    name, and the next process — finding the name free — would create a second
    lock file and drive the same run at the same time.

    So the acquired lock is checked against the path before it counts, and a
    lock that no longer sits there is dropped and re-taken. This is not a
    lease: nothing expires, nothing is stolen, and a live holder is never
    displaced. The loop can only turn when something else moved the file, so it
    is bounded by that rather than by time.
    """
    while True:
        directory.mkdir(parents=True, exist_ok=True)
        lock_file = directory / LOCK_FILENAME
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o600)
        except FileNotFoundError:
            # The directory went away between being created and being opened.
            # Build it again and take whichever lock exists then.
            continue
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            if _is_file_at(fd, lock_file):
                return fd
        except BaseException:
            os.close(fd)
            raise
        with suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _try_acquire_run_lock(directory: Path) -> int | None:
    """Take the lock currently at the path without waiting. None if held.

    The non-blocking twin of :func:`_acquire_run_lock`, and it makes the same
    check for the same reason: the acquired lock has to still be the file at
    the path, or the holder is alone with an inode nothing can reach by name.
    A name that stopped pointing at the lock we took is retried, not refused —
    that is the directory having been moved aside, not the run being held.
    """
    while True:
        directory.mkdir(parents=True, exist_ok=True)
        lock_file = directory / LOCK_FILENAME
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o600)
        except FileNotFoundError:
            continue
        keep = False
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return None
            if not _is_file_at(fd, lock_file):
                with suppress(OSError):
                    fcntl.flock(fd, fcntl.LOCK_UN)
                continue
            keep = True
            return fd
        finally:
            if not keep:
                os.close(fd)


def _is_held(directory: Path) -> bool:
    """Whether some process holds this run's lock right now.

    Creates nothing: a directory with no lock file is a directory nobody is
    driving, and asking the question must not be what brings one into
    existence. The lock is taken and released to ask, which excludes nobody
    for any longer than the question takes.
    """
    lock_file = directory / LOCK_FILENAME
    try:
        fd = os.open(lock_file, os.O_RDWR)
    except OSError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        with suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def _try_lock_for_removal(directory: Path) -> int | None:
    """Take a run's lock without waiting, for a caller about to remove it.

    Creates the lock file when the directory has none — an operator who
    planted an approval before the run started leaves a directory nothing has
    ever excluded on, and a directory nothing can exclude on is one nothing
    could ever collect. It does not create the *directory*: one that is already
    gone is not this module's to rebuild.
    """
    lock_file = directory / LOCK_FILENAME
    try:
        fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o600)
    except OSError:
        return None
    keep = False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return None
        if not _is_file_at(fd, lock_file):
            with suppress(OSError):
                fcntl.flock(fd, fcntl.LOCK_UN)
            return None
        keep = True
        return fd
    finally:
        if not keep:
            os.close(fd)


def _atomic_write(path: Path, payload: str) -> None:
    """Publish ``payload`` at ``path`` in one step.

    A reader either sees the whole previous record or the whole new one. A
    half-written gate that happened to parse would be a decision nobody made.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=_TMP_PREFIX, suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _gate_payload(gate: GateIdentity, status: str, reason: str, task_title: str) -> str:
    """The record itself.

    The metadata is what makes a record checkable after it has been moved or
    left behind: a file carrying another run's id is refused on read rather
    than honoured as an approval.
    """
    return json.dumps(
        {
            "run_id": gate.run_id,
            "session_ref": gate.session_ref,
            "index": gate.index,
            "task": task_title,
            "status": status,
            "reason": reason,
            "ts": time.time(),
        }
    )


def _write_gate(gate: GateIdentity, status: str, reason: str = "", task_title: str = "") -> Path:
    """Record a decision about ``gate``, replacing whatever was there."""
    path = _gate_file(gate)
    _atomic_write(path, _gate_payload(gate, status, reason, task_title))
    return path


def _claim_gate(gate: GateIdentity, status: str, task_title: str = "") -> bool:
    """Record ``status`` for ``gate`` only if its file does not exist yet.

    Returns whether this call created the record.

    A run announces an R2 gate and then marks it pending, and that mark used to
    be an unconditional write. Everything already on disk went with it — which
    is precisely the decision the run was about to wait for:

    - ``--run-id`` resumes a run against gates already on disk, so an approval
      written before the restart was destroyed by the restart;
    - ``POST /api/run`` returns the run id *before* the run reaches a gate so a
      dashboard operator can approve while it is still asking, and that
      approval landed in the same window;
    - the announcement is an HTTP POST with a ten-second timeout, so an
      operator answering the Discord message promptly wrote into it too.

    In each case the run then waited forever for a decision it had been given
    and had itself deleted.

    Creating rather than writing keeps every one of those. It costs nothing in
    the other direction: a file that cannot speak for this run — another run's
    id, another plan index, malformed — is read as no decision whether it is
    preserved or overwritten, so the R2 task keeps waiting either way, and an
    operator's ``echo > gate`` still resolves it. Preserving it is the choice
    that keeps the evidence.

    ``os.link`` is what makes this one step: it fails rather than replaces, so
    no reader can catch the file half-created and no writer can lose a race to
    another.
    """
    path = _gate_file(gate)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=_TMP_PREFIX, suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(_gate_payload(gate, status, "", task_title))
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(tmp, path)
        except FileExistsError:
            return False
        return True
    finally:
        tmp.unlink(missing_ok=True)


def _record_belongs_to(record: dict, gate: GateIdentity) -> bool:
    """Whether ``record`` is a decision about ``gate``.

    The path already scopes a record to one run, so a hand-written
    ``{"status": "approved"}`` — the exact thing the operator instructions ask
    for — is accepted on the strength of where it sits. What is refused is a
    record that *contradicts* its location: one carrying a different run id or
    a different plan index was written about some other task, and honouring it
    would let a stale or copied file speak for a run that never saw it.

    ``session_ref`` is not checked. It is a label, it may legitimately change
    when a run is resumed under a new one, and it is not what identifies
    anything.
    """
    stated_run = record.get("run_id")
    if stated_run is not None and stated_run != gate.run_id:
        return False

    stated_index = record.get("index")
    return stated_index is None or stated_index == gate.index


def _read_gate(gate: GateIdentity) -> dict | None:
    """Read the decision about ``gate``, or None if there is not one yet.

    Every failure answers None — absent, unreadable, not JSON, not an object,
    or belonging to another run. None means "no decision", so an R2 task keeps
    waiting and an R1 veto keeps being looked for. A gate that cannot be read
    must never resolve as approval.
    """
    try:
        raw = _gate_file(gate).read_text()
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError:
        return None

    try:
        record = json.loads(raw)
    except Exception:
        return None

    if not isinstance(record, dict):
        return None
    if not _record_belongs_to(record, gate):
        return None
    return record


def cleanup_run(run_id: str, owner: RunOwnership | None = None) -> int:
    """Remove one run's gate records. Returns how many were removed.

    The signature is the containment: a run id is the only thing this takes, it
    is validated as a UUID before it becomes a path, and the directory it names
    is the only one touched. A parallel run or a parallel test cannot unlink
    another run's gates through this, because there is no way to ask it to.

    What is removed is the run's decisions: the gate records, and any temp file
    an interrupted write left behind. Anything else found in the directory is
    left alone, since deleting something unrecognised is not cleanup.

    **The lock and the directory are kept.** Removing the lock is what this used
    to do, and it is not cleanup either — it is the end of exclusion. ``flock``
    excludes the holders of one *inode*, so unlinking the file while holding it
    left every waiter queued on an inode that no longer had a name: the waiter
    woke holding nothing anyone else could reach, the next process found the
    name free and created a second lock, and both then drove the same run's
    gates at once. Nothing removes a live run's lock, so that cannot happen.

    The directory therefore survives as a tombstone holding only the lock.
    :func:`sweep_gate_dirs` is what bounds how many of those accumulate.

    Args:
        run_id: The run whose records are removed. Validated as a UUID, and the
            only thing this takes that can name a path.
        owner: This process's claim on the run, when it has one. Cleanup takes
            the run's lock for itself when nobody hands it one, and ``flock``
            blocks a second descriptor even inside one process — so a run
            cleaning up inside its own :func:`own_run` has to say so or
            deadlock against itself. A token for a different run is refused: a
            claim on one run proves nothing about another.

    Raises:
        InvalidRunId: ``run_id`` is not a UUID.
        ValueError: ``owner`` names a different run.
    """
    canonical = parse_run_id(run_id)
    directory = gate_dir(canonical)
    if directory.parent != GATE_SIGNAL_DIR:
        raise ValueError(f"refusing to clean a path outside the gate directory: {directory}")
    if owner is not None and owner.run_id != canonical:
        raise ValueError(
            f"an ownership claim on run {owner.run_id} says nothing about run {canonical}"
        )
    if not directory.is_dir():
        return 0

    removed = 0
    held = nullcontext(directory) if owner is not None else run_gate_lock(canonical)
    with held:
        for record in sorted(directory.glob(_GATE_GLOB)):
            record.unlink(missing_ok=True)
            removed += 1
        for leftover in directory.glob(f"{_TMP_PREFIX}*.tmp"):
            leftover.unlink(missing_ok=True)
    return removed


def _is_gate_record(name: str) -> bool:
    return fnmatch(name, _GATE_GLOB)


def _is_module_owned(entry: Path) -> bool:
    """Whether ``entry`` is a file this module writes, and nothing else.

    Symbolic links are not: following one deletes something that was never in
    this directory. Directories are not either — nothing here writes one.
    """
    try:
        if entry.is_symlink() or not entry.is_file():
            return False
    except OSError:
        return False
    name = entry.name
    return (
        name in (LOCK_FILENAME, TOMBSTONE_MARKER)
        or _is_gate_record(name)
        or (name.startswith(_TMP_PREFIX) and name.endswith(".tmp"))
    )


def _entries(directory: Path) -> list[Path] | None:
    try:
        return sorted(directory.iterdir())
    except OSError:
        return None


def _decided_at(entries: list[Path]) -> float:
    """When this run's decisions last changed: the newest gate record.

    The records are what a decision is, so they are what dates one. An operator
    answering a gate writes *into* an existing file, which leaves the
    directory's own timestamp untouched — dating a run by the directory would
    let an approval written a minute ago be collected as abandoned. Dating it
    by everything in the directory has the opposite failure: the prune creates
    a missing lock file to exclude on, and that bumps the directory, so a run
    would look freshly touched by the very call deciding whether to keep it.
    """
    newest = 0.0
    for entry in entries:
        if not _is_gate_record(entry.name):
            continue
        with suppress(OSError):
            newest = max(newest, entry.stat().st_mtime)
    return newest


def _state_of(directory: Path, now: float, abandon_after: float) -> RunState:
    """Classify a run directory from its contents alone.

    Deliberately does not ask whether the lock is held: a caller holding it —
    which is every caller that is about to remove the directory — would see its
    own claim and read the run as active. Holding the lock *is* the proof that
    nobody else is driving it, so the two questions are separate.
    """
    entries = _entries(directory)
    if entries is None:
        return RunState.MISSING
    if any(not _is_module_owned(entry) for entry in entries):
        return RunState.FOREIGN
    if not any(_is_gate_record(entry.name) for entry in entries):
        return RunState.TERMINAL
    if _decided_at(entries) <= now - abandon_after:
        return RunState.ABANDONED
    return RunState.RESUMABLE


def run_state(run_id: str) -> RunState:
    """What one run's directory says about it. Changes nothing.

    The evidence both collectors act on, available to an operator deciding
    whether a run is worth resuming or is simply over.

    Raises:
        InvalidRunId: ``run_id`` is not a UUID.
    """
    directory = gate_dir(run_id)
    if not directory.is_dir():
        return RunState.MISSING
    if _is_held(directory):
        return RunState.ACTIVE
    return _state_of(directory, time.time(), GATE_ABANDON_TTL_SECONDS)


def _tombstone_payload(run_id: str, tombstone_name: str) -> str:
    return json.dumps(
        {
            "owner": _MARKER_OWNER,
            "kind": _MARKER_KIND,
            "run_id": run_id,
            "tombstone": tombstone_name,
            "ts": time.time(),
        }
    )


def _park_as_tombstone(directory: Path) -> Path | None:
    """Take a run directory out of the namespace. Returns where it went.

    Called under the run's lock. Renaming is not deleting: it moves the whole
    object in one step, so a run arriving afterwards builds a fresh directory
    and a fresh lock and the two never share a name or an inode. Nothing is
    unlinked while a lock is held, which is the rule cleanup used to break.

    The name carries a value minted here, so it cannot be the name of anything
    else — the previous name was ``.trash-<run_id>``, one per run, and the
    sweep deleted whatever sat there to make room. The marker goes in *before*
    the rename, so a crash in between leaves a labelled directory rather than
    an unexplained one; the marker is a file this module writes, so a directory
    still holding one is still terminal and the next sweep finishes the job.
    """
    run_id = directory.name
    for _ in range(_TOMBSTONE_ATTEMPTS):
        tombstone = directory.parent / f"{_TRASH_PREFIX}{run_id}-{uuid.uuid4().hex}"
        if os.path.lexists(tombstone):
            continue
        try:
            _atomic_write(directory / TOMBSTONE_MARKER, _tombstone_payload(run_id, tombstone.name))
            os.rename(directory, tombstone)
        except OSError:
            return None
        return tombstone
    return None


def _owned_tombstone_entries(path: Path) -> list[Path] | None:
    """The contents of ``path``, if this module parked it. Otherwise None.

    Three things have to agree, because any one of them alone is somebody
    else's directory:

    - the **name**, which carries a run id and a minted value in the shape
      :func:`_park_as_tombstone` writes. ``.trash-operator-owned`` is not it,
      and deleting on the prefix alone is what removed one.
    - the **marker**, naming this module, this kind of directory, the run it
      came from and the name it was parked under. A name can be typed by
      anyone; the marker is only ever written just before a rename.
    - the **contents**, which must be nothing but files this module writes. A
      tombstone somebody put something into stops being ours to delete.
    """
    match = _TOMBSTONE_NAME.match(path.name)
    if match is None:
        return None
    try:
        if path.is_symlink() or not path.is_dir():
            return None
    except OSError:
        return None
    entries = _entries(path)
    if entries is None or any(not _is_module_owned(entry) for entry in entries):
        return None

    try:
        record = json.loads((path / TOMBSTONE_MARKER).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict):
        return None
    if record.get("owner") != _MARKER_OWNER or record.get("kind") != _MARKER_KIND:
        return None
    if record.get("run_id") != match.group(1) or record.get("tombstone") != path.name:
        return None
    return entries


def _delete_tombstone(path: Path) -> bool:
    """Delete a directory this module parked, and only such a directory.

    Entry by entry and then the directory itself, rather than recursively: the
    contents have already been checked to be files this module writes, so
    there is nothing here that needs a recursive delete and nothing that could
    hide one.
    """
    entries = _owned_tombstone_entries(path)
    if entries is None:
        return False
    for entry in entries:
        with suppress(OSError):
            entry.unlink()
    try:
        path.rmdir()
    except OSError:
        return False
    return True


def _remove_run_dir(directory: Path, should_remove: Callable[[Path], bool]) -> bool:
    """Collect one run directory. Returns whether it left the namespace.

    Ordering is the whole design, and it is why this is safe without a lease:

    1. Take the run's lock without waiting. A run mid-checkpoint holds it — a
       parked R2 gate holds it for as long as the operator takes — so failing
       here means the run is alive and there is nothing to collect.
    2. Re-ask ``should_remove`` while holding it. Whatever was read before the
       lock was read of an unheld directory.
    3. **Rename** the directory out of the namespace, labelled as ours.
    4. Release, and only then delete.

    A process that was already queued on the lock when step 1 won it wakes
    holding an inode that is now under the tombstone name;
    :func:`_acquire_run_lock` is what notices and re-takes the live one. A
    crash between 3 and 4 leaves a tombstone the next sweep finishes.
    """
    fd = _try_lock_for_removal(directory)
    if fd is None:
        return False

    tombstone = None
    try:
        if not should_remove(directory):
            return False
        tombstone = _park_as_tombstone(directory)
    finally:
        with suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

    if tombstone is None:
        return False
    _delete_tombstone(tombstone)
    return True


def _run_dirs(root: Path) -> Iterator[Path]:
    """Every entry under ``root`` that this module could have written.

    A name that is not a run id was not written here. A symbolic link is not a
    run directory either, whatever it points at.
    """
    entries = _entries(root)
    for candidate in entries or []:
        if candidate.is_symlink() or not is_run_id(candidate.name):
            continue
        if candidate.is_dir():
            yield candidate


def sweep_gate_dirs(older_than_seconds: float | None = None) -> int:
    """Remove terminal run directories. Returns how many were removed.

    A run directory outlives the run: :func:`cleanup_run` keeps the lock, and a
    run that dies before reaching cleanup keeps everything. Without this, the
    count of directories under ``gates/`` would be the number of runs ever
    started.

    What is honestly *not* swept here, at any age:

    - a run that still holds a gate record. An interrupted R2 gate is a pending
      approval nobody answered, and it is what ``--run-id`` resumes against;
      age is not evidence that it was abandoned, since an operator may take a
      weekend over one. :func:`prune_abandoned_runs` is what eventually bounds
      those, on a window measured in days.
    - a run whose lock is held, which is to say a run that is still going.
    - a directory holding anything this module did not write.
    - anything under ``gates/`` that is not named by a run id.

    A ``.trash-`` entry is finished rather than swept: it is a directory a
    previous call had already taken out of the namespace, and only one whose
    name, marker and contents all say this module parked it is deleted.

    Args:
        older_than_seconds: How long a terminal directory is kept before it may
            be removed. Defaults to :data:`GATE_TOMBSTONE_TTL_SECONDS`, which
            is generous on purpose — the cost of keeping one is an empty
            directory, and the cost of removing one early is nothing at all,
            but a wide margin keeps this away from anything still in flight.

    Raises:
        ValueError: a negative age, which would sweep the future.
    """
    if older_than_seconds is None:
        older_than_seconds = GATE_TOMBSTONE_TTL_SECONDS
    if older_than_seconds < 0:
        raise ValueError(f"a retention window cannot be negative, got {older_than_seconds!r}")

    root = GATE_SIGNAL_DIR
    if not root.is_dir():
        return 0

    now = time.time()
    cutoff = now - older_than_seconds

    def spent(directory: Path) -> bool:
        if _state_of(directory, now, GATE_ABANDON_TTL_SECONDS) is not RunState.TERMINAL:
            return False
        # A terminal directory holds only its lock, whose timestamp never moves
        # once it is created, so the directory's own is what dates it.
        try:
            return directory.stat().st_mtime <= cutoff
        except OSError:
            return False

    removed = 0
    for parked in _entries(root) or []:
        if parked.name.startswith(_TRASH_PREFIX):
            # A previous call that died between the rename and the delete.
            _delete_tombstone(parked)
    for candidate in _run_dirs(root):
        if _remove_run_dir(candidate, spent):
            removed += 1
    return removed


def prune_abandoned_runs(
    older_than_seconds: float | None = None, keep_at_most: int | None = None
) -> int:
    """Remove gate records nobody is coming back for. Returns how many runs went.

    The narrow counterpart to :func:`sweep_gate_dirs`, and the bound on the one
    thing that used to be kept forever. A run interrupted at a gate is resume
    material: ``--run-id`` reads exactly those records, so removing them early
    turns a resume into a re-ask, and possibly into a second execution of work
    an operator already approved. But a run *killed* at a gate leaves the same
    records and nobody will ever answer them, and the two are indistinguishable
    from the outside — so what separates them is time, and the window is
    measured in days.

    Never removes a run whose lock is held, or a directory holding a file this
    module did not write.

    Args:
        older_than_seconds: How long a run with an undecided gate is kept after
            anything about it last changed. Defaults to
            :data:`GATE_ABANDON_TTL_SECONDS`.
        keep_at_most: How many resumable runs are kept regardless of age,
            newest first. A window alone is not a bound; this is what makes the
            directory count finite whatever happens. Defaults to
            :data:`GATE_MAX_RETAINED_RUNS`.

    Raises:
        ValueError: a negative window or a negative count.
    """
    if older_than_seconds is None:
        older_than_seconds = GATE_ABANDON_TTL_SECONDS
    if older_than_seconds < 0:
        raise ValueError(f"a recovery window cannot be negative, got {older_than_seconds!r}")
    if keep_at_most is None:
        keep_at_most = GATE_MAX_RETAINED_RUNS
    if keep_at_most < 0:
        raise ValueError(f"a retained count cannot be negative, got {keep_at_most!r}")

    root = GATE_SIGNAL_DIR
    if not root.is_dir():
        return 0

    now = time.time()

    def abandoned(directory: Path) -> bool:
        return _state_of(directory, now, older_than_seconds) is RunState.ABANDONED

    def resumable(directory: Path) -> bool:
        return _state_of(directory, now, older_than_seconds) is RunState.RESUMABLE

    removed = 0
    retained: list[tuple[float, Path]] = []
    for candidate in _run_dirs(root):
        if _is_held(candidate):
            continue
        state = _state_of(candidate, now, older_than_seconds)
        if state is RunState.ABANDONED:
            if _remove_run_dir(candidate, abandoned):
                removed += 1
        elif state is RunState.RESUMABLE:
            retained.append((_decided_at(_entries(candidate) or []), candidate))

    # Oldest first, so what survives the count bound is the work most likely to
    # still be worth resuming.
    surplus = len(retained) - keep_at_most
    for _, directory in sorted(retained)[: max(surplus, 0)]:
        if _remove_run_dir(directory, resumable):
            removed += 1
    return removed


def evaluate(task: Task, gate: GateIdentity, auto: bool | None = None) -> tuple[bool, str]:
    """
    Evaluate whether a task should proceed given its risk level.

    Returns (proceed: bool, reason: str).

    R0 → (True, "auto-approved")
    R1 → notify, wait up to 60s for veto, then (True, "auto-approved after timeout")
         In auto mode: (True, "R1 auto-approved (auto mode)") — no wait
    R2 → block until gate file written with status=approved
    R3 → always (False, "blocked — operator must manually unlock")

    Args:
        task: The task whose risk level gates it.
        gate: Which task, in which run. Required, and required to carry a real
            run id: an approval is a decision about one task in one run, and
            the string identity this replaced was one two runs could agree on.
        auto: This run's auto-mode decision. ``None`` means the caller has none
            and the environment answers. Pass it explicitly rather than
            exporting it: one run's mode must not decide another's, and R1 is
            where the operator's veto lives.
    """
    risk = task.risk
    auto_mode = _is_auto_mode() if auto is None else auto

    # R0: no gate
    if risk == RiskLevel.R0:
        return True, "R0 auto-approved"

    # R1: notify and auto-proceed after timeout (or immediately in auto mode)
    if risk == RiskLevel.R1:
        if auto_mode:
            return True, "R1 auto-approved (auto mode)"

        path = gate_path(gate)
        msg = (
            f"[JustAi R1] Task starting in {R1_TIMEOUT_SECONDS}s — veto to stop:\n"
            f"  **{task.title}**\n"
            f"  Risk: R1 (low — modifying existing code)\n"
            f"  {gate.describe()}\n"
            f'  To veto: write `{{"status": "vetoed"}}` to {path}'
        )
        notified = _discord_notify(msg)
        if not notified:
            print(
                f"[checkpoint] R1: {task.title} — proceeding in {R1_TIMEOUT_SECONDS}s (Discord not configured)"
            )
            print(f"  {gate.describe()}")
            print(f'  Veto: echo \'{{"status":"vetoed"}}\' > {path}')

        deadline = time.time() + R1_TIMEOUT_SECONDS
        while time.time() < deadline:
            record = _read_gate(gate)
            if record and record.get("status") == "vetoed":
                return False, f"R1 vetoed: {record.get('reason', 'no reason given')}"
            if record and record.get("status") == "approved":
                return True, "R1 manually approved"
            time.sleep(R1_POLL_SECONDS)

        return True, f"R1 auto-approved after {R1_TIMEOUT_SECONDS}s"

    # R2: hard gate — wait indefinitely for approval
    if risk == RiskLevel.R2:
        path = gate_path(gate)
        msg = (
            f"[JustAi R2] **APPROVAL REQUIRED** before task executes:\n"
            f"  **{task.title}**\n"
            f"  Risk: R2 (interface/schema change)\n"
            f"  {gate.describe()}\n"
            f'  To approve: write `{{"status": "approved"}}` to {path}\n'
            f'  To reject: write `{{"status": "rejected"}}`'
        )
        notified = _discord_notify(msg)
        if not notified:
            print(f"[checkpoint] R2 GATE: {task.title}")
            print(f"  {gate.describe()}")
            print(f"  Waiting for approval. Write to: {path}")
            print(f'  Approve: echo \'{{"status":"approved"}}\' > {path}')

        # Created, never written over: an approval already on disk is the
        # decision this is about to wait for. See :func:`_claim_gate`.
        _claim_gate(gate, "pending", task_title=task.title)
        while True:
            record = _read_gate(gate)
            if record and record.get("status") == "approved":
                return True, "R2 approved by operator"
            if record and record.get("status") in ("rejected", "vetoed"):
                return False, f"R2 rejected: {record.get('reason', 'no reason given')}"
            time.sleep(R2_POLL_SECONDS)

    # R3: always blocked
    if risk == RiskLevel.R3:
        msg = (
            f"[JustAi R3] **BLOCKED** — task requires manual unlock:\n"
            f"  **{task.title}**\n"
            f"  {gate.describe()}\n"
            f"  R3 tasks never proceed automatically."
        )
        _discord_notify(msg)
        print(f"[checkpoint] R3 BLOCKED: {task.title}")
        print("  This task requires manual operator intervention.")
        return False, "R3 blocked — operator must manually unlock"

    return True, "unknown risk level — defaulting to proceed"
