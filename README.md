# JustAi

JustAi is the combined WSL workspace for the LocalManus runtime and the relay-room task layer. The goal is to keep one product root at `/home/justinleopard/projects/JustAi` while preserving the copied source trees for reference and incremental migration.

## Layout

- `LocalManus/` copied runtime and operator tooling
- `relay-room/` copied relay/task system
- `scripts/` root-level startup and health wrappers
- `tools/` root-level CLI entrypoints
- `tests/` JustAi-owned integration tests

## Quick Start

```bash
cd ~/projects/JustAi
bash scripts/start_justai.sh
```

## Root Commands

```bash
bash scripts/check_justai.sh
python3 tools/justai_cli.py status
python3 tools/justai_cli.py start
python3 tools/justai_cli.py health
python3 tools/justai_cli.py task "Reply with exactly READY."
python3 tools/justai_cli.py relay status
python3 tools/justai_cli.py mini "summarize the workspace"
```

## Environment

The root scripts read these variables when set:

- `JUSTAI_ROOT`
- `JUSTAI_LOCALMANUS_ROOT`
- `JUSTAI_RELAY_ROOT`
- `JUSTAI_SPACETIME_SESSION`
- `JUSTAI_RELAY_SERVER`

If unset, they default to the current JustAi workspace and copied subrepos.

## Current Scope

This first scaffold keeps the copied repos intact and delegates into them. The next passes will consolidate shared behavior behind the JustAi root and replace the remaining hard-coded path assumptions with JustAi-owned config.
