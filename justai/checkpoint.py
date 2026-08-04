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
  run interrupted at a gate keeps its records indefinitely, because that is
  what makes ``--run-id`` a resume rather than a re-ask.

Discord integration: posts to DISCORD_RELAY_CHANNEL_ID if token is set.
If Discord is not configured, R1 auto-proceeds silently, R2/R3 block
until a local signal file is written by the operator.
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
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

#: Only these are gate records. Cleanup refuses to remove anything else.
_GATE_GLOB = "plan-*.json"
_TMP_PREFIX = ".gate-"

#: Where a swept directory is parked between leaving the namespace and being
#: deleted. Not a run id, so the sweep never mistakes one for a candidate.
_TRASH_PREFIX = ".trash-"


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
    """Hold one run's advisory lock for the body.

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
    lock itself. Take it once around the work and clean up after releasing it,
    the way the checkpoint stage does.
    """
    directory = gate_dir(run_id)
    fd = _acquire_run_lock(directory)
    try:
        yield directory
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


def cleanup_run(run_id: str) -> int:
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

    Takes the run's lock, so it must not be called while that lock is already
    held — see :func:`run_gate_lock`.
    """
    directory = gate_dir(run_id)
    if directory.parent != GATE_SIGNAL_DIR:
        raise ValueError(f"refusing to clean a path outside the gate directory: {directory}")
    if not directory.is_dir():
        return 0

    removed = 0
    with run_gate_lock(run_id):
        for record in sorted(directory.glob(_GATE_GLOB)):
            record.unlink(missing_ok=True)
            removed += 1
        for leftover in directory.glob(f"{_TMP_PREFIX}*.tmp"):
            leftover.unlink(missing_ok=True)
    return removed


def _discard(path: Path) -> None:
    """Delete a directory that is no longer reachable under its run's name."""
    shutil.rmtree(path, ignore_errors=True)


def _is_spent(directory: Path, cutoff: float) -> bool:
    """Whether ``directory`` holds nothing but its own lock, and has for a while.

    A gate record is a decision, or a run still waiting to be given one, and it
    is what ``--run-id`` resumes against — so a directory holding one is never
    spent, at any age. Anything unrecognised is not this module's to remove
    either. What is left is a run that has been cleaned up, or one that never
    reached a gate at all.
    """
    try:
        for entry in directory.iterdir():
            if entry.name != LOCK_FILENAME:
                return False
        return directory.stat().st_mtime <= cutoff
    except OSError:
        return False


def _sweep_one(directory: Path, cutoff: float) -> bool:
    """Remove one spent run directory. Returns whether it was removed.

    Ordering is the whole design, and it is why this is safe without a lease:

    1. Take the run's lock without waiting. A run mid-checkpoint holds it — a
       parked R2 gate holds it for as long as the operator takes — so failing
       here means the run is alive and there is nothing to sweep.
    2. Confirm the lock is still the one at the path, and that the directory is
       spent, while holding it.
    3. **Rename** the directory. Renaming is not deleting: it takes the whole
       object out of the namespace in one step, so a run arriving afterwards
       builds a fresh directory and a fresh lock, and the two never share a
       name or an inode.
    4. Release, and only then delete. Nothing is ever unlinked while a lock is
       held, which is the rule cleanup used to break.

    A process that was already queued on the lock when step 1 won it wakes
    holding an inode that is now under the trash name; :func:`_acquire_run_lock`
    is what notices and re-takes the live one.
    """
    lock_file = directory / LOCK_FILENAME
    try:
        fd = os.open(lock_file, os.O_RDWR)
    except OSError:
        # No lock file means no directory this module is responsible for.
        return False

    trash = directory.parent / f"{_TRASH_PREFIX}{directory.name}"
    renamed = False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        try:
            if not _is_file_at(fd, lock_file) or not _is_spent(directory, cutoff):
                return False
            _discard(trash)
            os.rename(directory, trash)
            renamed = True
        finally:
            with suppress(OSError):
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)

    if renamed:
        _discard(trash)
    return renamed


def sweep_gate_dirs(older_than_seconds: float | None = None) -> int:
    """Remove spent run directories. Returns how many were removed.

    A run directory outlives the run: :func:`cleanup_run` keeps the lock, and a
    run that dies before reaching cleanup keeps everything. Without this, the
    count of directories under ``gates/`` would be the number of runs ever
    started.

    What is honestly *not* swept, at any age:

    - a run that still holds a gate record — an interrupted R2 gate is a
      pending approval nobody answered, and it is what ``--run-id`` resumes
      against. Those are retained deliberately and indefinitely; an operator
      who is done with one removes the directory.
    - a run whose lock is held, which is to say a run that is still going.
    - a directory holding anything this module did not write.
    - anything under ``gates/`` that is not named by a run id.

    Args:
        older_than_seconds: How long a spent directory is kept before it may be
            removed. Defaults to :data:`GATE_TOMBSTONE_TTL_SECONDS`, which is
            generous on purpose — the cost of keeping one is an empty
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

    cutoff = time.time() - older_than_seconds
    removed = 0
    with suppress(OSError):
        for candidate in sorted(root.iterdir()):
            if candidate.name.startswith(_TRASH_PREFIX):
                # A sweep that died between the rename and the delete.
                _discard(candidate)
                continue
            if not is_run_id(candidate.name) or not candidate.is_dir():
                continue
            if _sweep_one(candidate, cutoff):
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
