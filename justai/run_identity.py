#!/usr/bin/env python3
"""
JustAi — Run Identity
======================
The value that tells one orchestration run apart from another.

``session_ref`` is a human label. It is chosen for readability, it is reused on
purpose, and it is frequently not set at all — ``justai run`` leaves it empty
unless ``--session`` is passed, and the module default is the shared string
``sprint-2``. A label is the right thing to put in a trace, a memory key, or a
Discord message, and the wrong thing to derive an identity from.

It was, until this module existed, exactly what the approval gate was named
after: ``gates/gate_<session_ref>-plan-<index>.json``. Two ordinary concurrent
runs that agreed on a label and a plan index agreed on a filename, so a single
operator approval released both — including the run the operator never saw.

A run id is a UUID and nothing else. It is not derived from the label, the
clock, the process, or the goal, because every one of those collides between
two runs started together, and a gate that two runs can name is not a gate.

Deliberately not read from the environment
------------------------------------------
There is no ``JUSTAI_RUN_ID``. This module takes the identity as an argument or
mints a fresh one; it never consults process-global state. That is the same
rule :mod:`justai.checkpoint` records for auto mode, and for the same reason: a
long-lived process — the API server serves every request from one interpreter —
would hand one run's identity to every run after it, which is the collision
this module exists to end, reintroduced through a different door.
"""

from __future__ import annotations

import re
import uuid

#: A run id as stored and compared: 32 lowercase hex digits, no dashes.
#: Anchored, because a run id becomes a path component — see :func:`parse_run_id`.
_RUN_ID_PATTERN = re.compile(r"\A[0-9a-f]{32}\Z")


class InvalidRunId(ValueError):
    """A supplied run id is not a UUID, so nothing may be scoped to it."""


def new_run_id() -> str:
    """Mint the identity for one orchestration run. Call this once per run."""
    return uuid.uuid4().hex


def parse_run_id(value: object) -> str:
    """Validate an externally supplied run id and return its canonical form.

    Accepts the canonical dashed UUID form as well as bare hex, since an
    operator resuming a run copies whatever was printed at them.

    This is the only way a run id from outside the process — a ``--run-id``
    flag, a JSON request body — becomes a path component, so the check is a
    whitelist rather than a search for bad characters: a run id that is not a
    UUID cannot name a directory, and ``..``, ``/`` and an empty string are
    refused by not being UUIDs rather than by being listed.

    Raises:
        InvalidRunId: the value is not a UUID.
    """
    if not isinstance(value, str):
        raise InvalidRunId(f"run id must be a string, got {type(value).__name__}")

    candidate = value.strip().lower()
    if _RUN_ID_PATTERN.match(candidate):
        return candidate

    try:
        return uuid.UUID(candidate).hex
    except (ValueError, AttributeError, TypeError) as exc:
        raise InvalidRunId(
            f"run id must be a UUID minted for one run, got {value!r}. "
            "A session label, a timestamp, or a goal is not a run id — two runs "
            "can produce the same one, and then one approval releases both."
        ) from exc


def is_run_id(value: object) -> bool:
    """True if ``value`` is a usable run id. Never raises."""
    try:
        parse_run_id(value)
    except InvalidRunId:
        return False
    return True
