"""Slice D: Agent Payment Ledger — tests for SQLite ledger, budget, and API."""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


class TestLedgerCRUD(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        from justai.ledger import Ledger

        self.ledger = Ledger(db_path=self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_record_and_retrieve(self):
        entry_id = self.ledger.record(
            run_id="run-1",
            agent="mini-swe",
            model="gpt-5.4",
            cost=0.042,
            tokens_in=1200,
            tokens_out=800,
            duration_s=12.5,
        )
        assert entry_id > 0
        entries = self.ledger.recent_entries(limit=10)
        assert len(entries) == 1
        assert entries[0].run_id == "run-1"
        assert entries[0].cost == 0.042

    def test_agent_summary(self):
        self.ledger.record(run_id="r1", agent="agent-a", cost=0.05)
        self.ledger.record(run_id="r2", agent="agent-a", cost=0.03)
        self.ledger.record(run_id="r3", agent="agent-b", cost=0.10)

        summary = self.ledger.agent_summary("agent-a")
        assert summary is not None
        assert summary.total_cost == 0.08
        assert summary.total_runs == 2

    def test_agent_summary_nonexistent(self):
        summary = self.ledger.agent_summary("nonexistent")
        assert summary is None

    def test_all_agents(self):
        self.ledger.record(run_id="r1", agent="agent-a", cost=0.05)
        self.ledger.record(run_id="r2", agent="agent-b", cost=0.10)

        agents = self.ledger.all_agents()
        assert len(agents) == 2
        assert agents[0].agent == "agent-b"  # Higher cost first
        assert agents[0].total_cost == 0.10

    def test_run_entries(self):
        self.ledger.record(run_id="run-1", agent="a", cost=0.01, stage="planner")
        self.ledger.record(run_id="run-1", agent="a", cost=0.02, stage="reviewer")
        self.ledger.record(run_id="run-2", agent="b", cost=0.05)

        entries = self.ledger.run_entries("run-1")
        assert len(entries) == 2
        assert entries[0].stage == "planner"
        assert entries[1].stage == "reviewer"

    def test_daily_spend(self):
        self.ledger.record(run_id="r1", agent="agent-a", cost=0.05)
        self.ledger.record(run_id="r2", agent="agent-a", cost=0.03)
        self.ledger.record(run_id="r3", agent="agent-b", cost=0.10)

        spend = self.ledger.daily_spend("agent-a", days=1)
        assert spend == 0.08

    def test_check_budget_under(self):
        self.ledger.record(run_id="r1", agent="agent-a", cost=0.50)
        status = self.ledger.check_budget("agent-a", daily_limit=5.0)
        assert status.over_budget is False
        assert status.remaining == 4.5

    def test_check_budget_over(self):
        self.ledger.record(run_id="r1", agent="agent-a", cost=6.0)
        status = self.ledger.check_budget("agent-a", daily_limit=5.0)
        assert status.over_budget is True
        assert status.remaining == 0.0

    def test_daily_rollup(self):
        self.ledger.record(run_id="r1", agent="agent-a", cost=0.05)
        rollup = self.ledger.daily_rollup(days=1)
        assert len(rollup) >= 1
        assert rollup[0]["agent"] == "agent-a"


class TestLedgerDataTypes(unittest.TestCase):
    def test_ledger_entry_dataclass(self):
        from justai.ledger import LedgerEntry

        e = LedgerEntry(
            id=1,
            run_id="r",
            agent="a",
            model="m",
            cost=0.1,
            tokens_in=100,
            tokens_out=50,
            duration_s=5.0,
            timestamp=time.time(),
            stage="planner",
        )
        assert e.cost == 0.1

    def test_agent_summary_dataclass(self):
        from justai.ledger import AgentSummary

        s = AgentSummary(
            agent="a",
            total_cost=1.0,
            total_runs=5,
            total_tokens_in=5000,
            total_tokens_out=2000,
            avg_cost_per_run=0.2,
            avg_duration=10.0,
            last_run_at=time.time(),
        )
        assert s.avg_cost_per_run == 0.2

    def test_budget_status_dataclass(self):
        from justai.ledger import BudgetStatus

        b = BudgetStatus(
            agent="a", daily_spend=3.0, daily_limit=5.0, over_budget=False, remaining=2.0
        )
        assert b.remaining == 2.0


class TestLedgerAPI(unittest.TestCase):
    def test_ledger_agents_endpoint(self):
        from justai.api import APIHandler

        handler = APIHandler.__new__(APIHandler)
        handler.path = "/api/ledger/agents"
        handler.headers = {}

        responses = []
        handler._json = lambda data, status=200: responses.append((data, status))
        handler.do_GET()

        assert len(responses) == 1
        data, _ = responses[0]
        assert isinstance(data, list)

    def test_ledger_daily_endpoint(self):
        from justai.api import APIHandler

        handler = APIHandler.__new__(APIHandler)
        handler.path = "/api/ledger/daily"
        handler.headers = {}

        responses = []
        handler._json = lambda data, status=200: responses.append((data, status))
        handler.do_GET()

        assert len(responses) == 1

    def test_ledger_budget_endpoint(self):
        from justai.api import APIHandler

        handler = APIHandler.__new__(APIHandler)
        handler.path = "/api/ledger/budget/mini-swe?limit=5.0"
        handler.headers = {}

        responses = []
        handler._json = lambda data, status=200: responses.append((data, status))
        handler.do_GET()

        assert len(responses) == 1
        data, _ = responses[0]
        assert "over_budget" in data


if __name__ == "__main__":
    unittest.main()
