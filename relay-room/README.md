# Relay Room

Relay Room is a CLI-first SpacetimeDB app for practicing local agent infrastructure. It gives you a small shared task board where `claude-code`, `codex`, and `localmanus` can hand work off to each other and leave an audit trail in the database.

This first milestone is intentionally narrow:

- one local SpacetimeDB database
- one `relay` CLI
- task posting, claiming, starting, completing, failing
- agent registration and lightweight inbox/messages
- append-only events for every state transition
- one read-only web board for operator visibility

## Quick Start

Five commands from clone to a running relay board:

```bash
# 1. Clone the repo
git clone git@github.com:justinleopard/relay-room.git && cd relay-room

# 2. Build the module, publish the DB, and install the relay CLI
bash scripts/start_relay_room.sh

# 3. Export the environment the CLI needs
export PATH="$HOME/.local/bin:$PATH" RELAY_DB_NAME="$(cat .relay-db-target)" RELAY_SERVER=local-server

# 4. Register the agents
relay register claude-code --caps planner,review && relay register codex --caps execution,verification && relay register localmanus --caps delegation,assistant

# 5. Open the board
relay board
```

## What Is Already Assumed

These instructions match the current machine state that was already verified:

- WSL Ubuntu is available
- `spacetime` 2.1.0 is installed
- `rustc`, `cargo`, and `tmux` are installed
- if Cargo lives under `~/.cargo`, non-interactive shells should load `~/.cargo/env`
- LocalManus is already available under `/home/justinleopard/projects/LocalManus`
- `ml status` is healthy

## Project Layout

```text
relay-room/
├── spacetimedb/
├── client/
├── scripts/
├── web/
└── Makefile
```

## First-Time Setup

Run this from WSL:

```bash
cd ~/projects/relay-room
bash scripts/start_relay_room.sh
export PATH="$HOME/.local/bin:$PATH"
export RELAY_DB_NAME="$(cat .relay-db-target 2>/dev/null || printf relay-room-dev)"
export RELAY_SERVER=local-server
```

What this does:

1. builds the SpacetimeDB module
2. reuses an existing local database target if one is already known
3. otherwise publishes a new local database and records its effective target in `.relay-db-target`
4. regenerates Rust bindings from the local module
5. installs the `relay` CLI into `~/.local/bin`

Important: on `local-server`, a freshly published anonymous database is sometimes easiest to address by its identity instead of the friendly name. `start_relay_room.sh` handles that and writes the correct target into `.relay-db-target`.

## Fast Health Checks

```bash
spacetime -V
ml status
relay status
```

Run the current automated checks:

```bash
make test
```

Install the git hooks that keep the installed `relay` binary in sync after pulls and branch switches:

```bash
make setup-hooks
```

## Register The Agents

```bash
relay register claude-code --caps planner,review
relay register codex --caps execution,verification
relay register localmanus --caps delegation,assistant
```

Then inspect the board:

```bash
relay board
```

## First End-to-End Handoff

Post a task from Claude to Codex:

```bash
relay post \
  --from claude-code \
  --to codex \
  --title "Prove the relay loop" \
  --payload "Claim this task, start it, then mark it done." \
  --priority 5 \
  --session first-run
```

List tasks:

```bash
relay tasks
```

Codex claims the task:

```bash
relay claim 1 --as codex
relay start 1 --as codex
relay done 1 --as codex --result "Relay loop verified."
```

Confirm it on the board:

```bash
relay board
```

## Watching The Board

Whole board:

```bash
relay watch
```

Single agent view:

```bash
relay watch --agent codex
```

## Read-Only Web Board

For a lightweight operator view, run:

```bash
cd ~/projects/relay-room
export PATH="$HOME/.local/bin:$PATH"
export RELAY_DB_NAME="$(cat .relay-db-target)"
export RELAY_SERVER=local-server
python3 scripts/relay_web.py
```

Then open:

```text
http://127.0.0.1:8765
```

The page is stdlib-only, auto-refreshes every 3 seconds, and renders the current Tasks and Agents tables by calling `relay board` and parsing the CLI output.

## Messages

Send a message:

```bash
relay msg --from claude-code --to codex --content "Check task 1." --task-ref 1
```

Read an inbox:

```bash
relay inbox codex
```

## Using It With LocalManus

At this milestone, LocalManus is represented on the board as an agent named `localmanus`. The stable execution path inside LocalManus is still the OpenFang `assistant`, not the broken `orchestrator`.

Useful LocalManus checks:

```bash
cd ~/projects/LocalManus
ml status
ml task "Confirm the LocalManus assistant path is healthy in one sentence."
```

A practical first workflow is:

1. Use `relay post` to assign work to `localmanus`
2. Use `ml task` to execute the requested work through the LocalManus assistant
3. Reflect the task lifecycle back into Relay Room with `relay claim`, `relay start`, and `relay done`

Example:

```bash
relay post \
  --from codex \
  --to localmanus \
  --title "Summarize next backend slice" \
  --payload "Give a short recommendation for the next schema improvement." \
  --session manus-demo
```

Then run:

```bash
cd ~/projects/LocalManus
ml task "Give a short recommendation for the next Relay Room schema improvement."
```

And reflect the result:

```bash
relay claim 2 --as localmanus
relay start 2 --as localmanus
relay done 2 --as localmanus --result "Returned next schema recommendation through assistant path."
```

Dispatcher note:
- `scripts/relay_dispatch.sh` treats `localmanus` as the relay identity, but the actual execution path is `mini_local_cloud.sh -> mini`.
- On successful runs it now prefers `~/projects/LocalManus/logs/last_honcho_post_task.txt` for the relay result summary, then falls back to the copied trajectory snapshot in `/tmp/relay_traj_<id>.json`, then finally to the run-log tail.
- On failed runs it keeps `/tmp/relay_dispatch_run_<id>.txt` and logs the retained path for inspection.

## Discord Integration — Agent-to-Agent Communication Bus

**Status:** Sprint 3 (ADR-002 adopted 2026-04-07)

As of Sprint 3, Discord is the source of truth for all agent-to-agent (A2A) communication.
SpacetimeDB remains the source of truth for structured task lifecycle and audit trail.
Together they form a complete comms + task system.

### How It Works

- **One bot per agent** in the same Discord server "The Relay Room"
- **Every agent sees every message natively** via their own Discord WebSocket stream
- **Human oversight** — Justin sees the same channels the agents post to
- **Heartbeat contract** — each agent posts to #heartbeats every 5 minutes
- **Boot catchup** — on startup, agents re-read the last 20 messages from key channels

### Channels

| Channel | Purpose |
|---------|---------|
| #lobby | Boot announcements, daily kickoffs |
| #relay-room | Primary A2A work comms |
| #deployments | Deployment/merge notices |
| #heartbeats | Bot keepalives |
| #alerts | Failures, stale agent warnings |
| #logs | Session lifecycle events |

### Quick Start — Discord Bots

See docs/BOT_CREATION.md for initial bot app setup.

Setup server structure:



Start all 4 bot listeners:



Verify health:



### For More Details

- **ADR-002** (docs/ADR-002-discord-comms.md) — architecture decision and protocol
- **Discord Architecture** (docs/DISCORD_ARCHITECTURE.md) — full technical details
- **Sprint 3 Plan** (docs/SPRINT_3.md) — current sprint tasks
- **Bot Creation** (docs/BOT_CREATION.md) — Developer Portal setup guide

---


## Operator Notes

- Install-sync matters: the repo-local CLI can move ahead of `~/.local/bin/relay` after new commits land. Run `make setup-hooks` once per clone to install `post-merge` and `post-checkout` hooks that automatically run `make install`.
- If you are debugging a just-landed CLI feature and have not installed hooks yet, prefer running from `client/` with `cargo run -- ...` so you know you are using the current code.
- `RELAY_DB_NAME` is really the active database target. It may be either a friendly name or a database identity.
- Default requested name: `relay-room-dev`
- Default server: `local-server`
- The CLI uses `spacetime call` and `spacetime sql` under the hood. Binding generation uses `spacetime generate --module-path spacetimedb`.
- SQL support in this CLI is basic; `select * from ...` and simple `where` filters work, but richer SQL should not be assumed
- If you want a separate clean database, set a new requested name and rerun startup:

```bash
export RELAY_DB_NAME=relay-room-dev-2
bash scripts/start_relay_room.sh
export RELAY_DB_NAME="$(cat .relay-db-target)"
```

## Commands Reference

```bash
relay register <agent> --caps <caps>
relay status
relay board
relay tasks [--to <agent>] [--status <status>]
relay show <id> [--json]
relay inbox <agent>
relay post --from <agent> --to <agent> --title <title> [--payload <text>] [--priority <n>] [--session <name>] [--json]
relay claim <id> --as <agent>
relay start <id> --as <agent>
relay done <id> --as <agent> --result <text>
relay fail <id> --as <agent> --error <text>
relay msg --from <agent> --to <agent> --content <text> [--task-ref <id>]
relay watch [--agent <agent>] [--every <seconds>]
```

Auxiliary scripts:

```bash
scripts/start_relay_room.sh   # build/publish/install bootstrap
scripts/setup_hooks.sh        # install post-merge/post-checkout auto-install hooks
scripts/relay_dispatch.sh     # localmanus polling loop
scripts/relay_web.py          # read-only web board on localhost:8765
```
