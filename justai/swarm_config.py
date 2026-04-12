"""
JustAi — Swarm Configuration
==============================
Tier definitions for claude-flow swarm scaling.
Each tier specifies maxAgents, topology, and dispatch strategy.

Tiers: 15 (default), 50, 150, 1500
"""
from __future__ import annotations

from dataclasses import dataclass

TIERS = [15, 50, 150, 1500]


@dataclass
class SwarmTier:
    max_agents: int
    topology: str = "hierarchical-mesh"
    strategy: str = "specialized"
    poll_interval: float = 2.0
    spawn_timeout: float = 30.0
    task_timeout: float = 1800.0


_TIER_MAP: dict[int, SwarmTier] = {
    15:   SwarmTier(max_agents=15,   topology="hierarchical-mesh", strategy="specialized"),
    50:   SwarmTier(max_agents=50,   topology="hierarchical-mesh", strategy="specialized"),
    150:  SwarmTier(max_agents=150,  topology="mesh",              strategy="round-robin", poll_interval=5.0),
    1500: SwarmTier(max_agents=1500, topology="mesh",              strategy="round-robin", poll_interval=10.0, spawn_timeout=60.0),
}


def get_tier(agent_count: int) -> SwarmTier:
    """Get the tier config for a given agent count. Rounds up to next defined tier."""
    for t in TIERS:
        if agent_count <= t:
            return _TIER_MAP[t]
    return _TIER_MAP[TIERS[-1]]
