# Harness Notes — Sprint 5

## Sprint Focus
Polish + installer. No new features — documentation, packaging, and end-to-end verification.

## Harness Observations

### What Worked Well

1. **Memory as a sprint log.** Storing `justai/sprint4/status` and `justai/sprint5/dogfood` in claude-flow memory creates a persistent audit trail. HNSW search found "sprint status" results across both sprints with 0.65-0.70 similarity. This is genuinely useful for cross-session context.

2. **Installer preflight is fast.** `bash install.sh --check` runs in <1s, checks Python, Node, npm, spacetime, relay, claude-flow. Gives clear pass/fail. Good for CI or first-time setup validation.

3. **78 tests in 2 seconds.** All offline, all mocked. The test suite covers orchestrator pipeline (24), memory/tracing (25), and installer/docs (29). Fast feedback loop.

4. **MCP health check is reliable.** `curl :3100/health` returns in ~3ms. Used by `ruv_status.sh`, installer preflight, and dashboard sidebar. Single source of truth for "is memory available."

### What Didn't Work Well

1. **Explorer agent can't access WSL paths.** The Explore subagent failed to read `\\wsl.localhost\Ubuntu-24.04\...` paths. All WSL file operations had to go through `wsl.exe -d Ubuntu-24.04 -e bash -c "..."` in the Bash tool. This works but is slower and more fragile (quoting issues with nested strings).

2. **Still writing to Windows temp then copying.** Creating files in WSL requires the `Write → C:\Zo\Workspace\temp\ → cp /mnt/c/...` dance. Not a harness issue per se, but a workflow friction that adds ~5s per file.

3. **No real delegation test.** The e2e dogfood verified memory, installer, and imports — but didn't actually run `justai.orchestrator.run("goal")` end-to-end because that requires LiteLLM and SpacetimeDB with a live agent. The delegator is tested only via mocks. A true e2e test needs: LiteLLM running, SpacetimeDB running, mini-swe-agent registered as a claimant.

4. **Dashboard not tested in CI.** Vite build passes (`npx vite build`), TypeScript checks pass (`npx tsc --noEmit`), but there are no component tests. The views are manually verified only.

## Commands Reference (Sprint 5 additions)

```bash
# Install / preflight
bash install.sh              # full install
bash install.sh --check      # preflight only

# Copy .env template
cp .env.example .env         # then edit with your keys

# Run all tests
python3 -m pytest tests/ -v

# Quick memory check from Python
python3 -c "from justai.memory import Memory; m=Memory(); print(m.connected, m.stats())"
```

## Files Added This Sprint

```
install.sh           — single-command installer with preflight
.env.example         — environment variable template
requirements.txt     — pip dependencies (langfuse, pytest)
README.md            — rewritten with install, quick start, architecture diagram
docs/ARCHITECTURE.md — full system architecture with data flow diagrams
docs/ATTRIBUTION.md  — credits for all dependencies with licenses
tests/test_sprint5.py — 29 tests for installer, env, docs, package integrity
harness-notes/sprint5.md — this file
```
