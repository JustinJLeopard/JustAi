#!/usr/bin/env python3
"""
JustAi — Agent Payment Ledger
================================
SQLite-backed cost attribution per agent, per run, per model.
Every pipeline run records its cost to the ledger, attributed to the
assigned agent.

Usage:
    from justai.ledger import Ledger

    ledger = Ledger()
    ledger.record(run_id="run-1", agent="mini-swe", model="gpt-5.4",
                  cost=0.042, tokens_in=1200, tokens_out=800, duration_s=12.5)
    summary = ledger.agent_summary("mini-swe")
    totals = ledger.all_agents()
    budget = ledger.check_budget("mini-swe", daily_limit=5.0)
"""
from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ── Config ───────────────────────────────────────────────────────────────────

DEFAULT_DB_PATH = os.environ.get(
    "JUSTAI_LEDGER_DB",
    str(Path(__file__).resolve().parent.parent / "data" / "ledger.db"),
)


# ── Data Types ──────────────────────────────────────────────────────────────

@dataclass
class LedgerEntry:
    id: int
    run_id: str
    agent: str
    model: str
    cost: float
    tokens_in: int
    tokens_out: int
    duration_s: float
    timestamp: float
    stage: str


@dataclass
class AgentSummary:
    agent: str
    total_cost: float
    total_runs: int
    total_tokens_in: int
    total_tokens_out: int
    avg_cost_per_run: float
    avg_duration: float
    last_run_at: float


@dataclass
class BudgetStatus:
    agent: str
    daily_spend: float
    daily_limit: float
    over_budget: bool
    remaining: float


# ── Ledger ──────────────────────────────────────────────────────────────────

class Ledger:
    """SQLite-backed cost ledger with per-agent tracking."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Create the database and table if they don't exist."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    model TEXT NOT NULL DEFAULT '',
                    cost REAL NOT NULL DEFAULT 0.0,
                    tokens_in INTEGER NOT NULL DEFAULT 0,
                    tokens_out INTEGER NOT NULL DEFAULT 0,
                    duration_s REAL NOT NULL DEFAULT 0.0,
                    timestamp REAL NOT NULL,
                    stage TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ledger_agent ON ledger(agent)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ledger_run ON ledger(run_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ledger_ts ON ledger(timestamp)
            """)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    # ── Write ──────────────────────────────────────────────────────────────

    def record(
        self,
        run_id: str,
        agent: str,
        model: str = "",
        cost: float = 0.0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        duration_s: float = 0.0,
        stage: str = "",
        timestamp: Optional[float] = None,
    ) -> int:
        """Record a cost entry in the ledger. Returns the entry ID."""
        ts = timestamp or time.time()
        with self._conn() as conn:
            cursor = conn.execute(
                """INSERT INTO ledger (run_id, agent, model, cost, tokens_in,
                   tokens_out, duration_s, timestamp, stage)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, agent, model, cost, tokens_in, tokens_out, duration_s, ts, stage),
            )
            return cursor.lastrowid or 0

    # ── Read ───────────────────────────────────────────────────────────────

    def agent_summary(self, agent: str) -> AgentSummary | None:
        """Get aggregate summary for a single agent."""
        with self._conn() as conn:
            row = conn.execute(
                """SELECT
                    agent,
                    SUM(cost) as total_cost,
                    COUNT(DISTINCT run_id) as total_runs,
                    SUM(tokens_in) as total_tokens_in,
                    SUM(tokens_out) as total_tokens_out,
                    AVG(cost) as avg_cost_per_run,
                    AVG(duration_s) as avg_duration,
                    MAX(timestamp) as last_run_at
                FROM ledger WHERE agent = ?""",
                (agent,),
            ).fetchone()

            if not row or row["total_cost"] is None:
                return None

            return AgentSummary(
                agent=row["agent"],
                total_cost=row["total_cost"],
                total_runs=row["total_runs"],
                total_tokens_in=row["total_tokens_in"],
                total_tokens_out=row["total_tokens_out"],
                avg_cost_per_run=row["avg_cost_per_run"],
                avg_duration=row["avg_duration"],
                last_run_at=row["last_run_at"],
            )

    def all_agents(self) -> list[AgentSummary]:
        """Get summaries for all agents."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT
                    agent,
                    SUM(cost) as total_cost,
                    COUNT(DISTINCT run_id) as total_runs,
                    SUM(tokens_in) as total_tokens_in,
                    SUM(tokens_out) as total_tokens_out,
                    AVG(cost) as avg_cost_per_run,
                    AVG(duration_s) as avg_duration,
                    MAX(timestamp) as last_run_at
                FROM ledger GROUP BY agent ORDER BY total_cost DESC"""
            ).fetchall()

            return [
                AgentSummary(
                    agent=r["agent"],
                    total_cost=r["total_cost"],
                    total_runs=r["total_runs"],
                    total_tokens_in=r["total_tokens_in"],
                    total_tokens_out=r["total_tokens_out"],
                    avg_cost_per_run=r["avg_cost_per_run"],
                    avg_duration=r["avg_duration"],
                    last_run_at=r["last_run_at"],
                )
                for r in rows
            ]

    def run_entries(self, run_id: str) -> list[LedgerEntry]:
        """Get all entries for a specific run."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM ledger WHERE run_id = ? ORDER BY timestamp",
                (run_id,),
            ).fetchall()
            return [self._row_to_entry(r) for r in rows]

    def recent_entries(self, limit: int = 50) -> list[LedgerEntry]:
        """Get recent ledger entries."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM ledger ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_entry(r) for r in rows]

    def daily_spend(self, agent: str, days: int = 1) -> float:
        """Get total spend for an agent in the last N days."""
        cutoff = time.time() - (days * 86400)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT SUM(cost) as total FROM ledger WHERE agent = ? AND timestamp >= ?",
                (agent, cutoff),
            ).fetchone()
            return row["total"] or 0.0

    def check_budget(self, agent: str, daily_limit: float) -> BudgetStatus:
        """Check if an agent is over their daily budget."""
        spend = self.daily_spend(agent, days=1)
        return BudgetStatus(
            agent=agent,
            daily_spend=round(spend, 4),
            daily_limit=daily_limit,
            over_budget=spend >= daily_limit,
            remaining=round(max(0, daily_limit - spend), 4),
        )

    def daily_rollup(self, days: int = 30) -> list[dict]:
        """Get daily cost rollup across all agents."""
        cutoff = time.time() - (days * 86400)
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT
                    date(timestamp, 'unixepoch') as day,
                    agent,
                    SUM(cost) as total_cost,
                    COUNT(*) as entries,
                    SUM(tokens_in) as tokens_in,
                    SUM(tokens_out) as tokens_out
                FROM ledger WHERE timestamp >= ?
                GROUP BY day, agent ORDER BY day DESC, total_cost DESC""",
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]

    def _row_to_entry(self, row: sqlite3.Row) -> LedgerEntry:
        return LedgerEntry(
            id=row["id"],
            run_id=row["run_id"],
            agent=row["agent"],
            model=row["model"],
            cost=row["cost"],
            tokens_in=row["tokens_in"],
            tokens_out=row["tokens_out"],
            duration_s=row["duration_s"],
            timestamp=row["timestamp"],
            stage=row["stage"],
        )
