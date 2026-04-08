# OpenHands Setup for ManusLocal

OpenHands is being pulled via Docker. Once ready, start it with:

Prereq (WSL): Docker must be available (Docker Desktop running with WSL integration enabled for your distro).

State: OpenHands writes auth/session state to `~/.openhands-state` (created automatically by `ml openhands start`).

Optional: if you want OpenHands to be able to use GitHub-related MCP tooling, set `GITHUB_PERSONAL_ACCESS_TOKEN` in your shell before starting the container.

```bash
# Quick start (uses LiteLLM proxy at localhost:4000)
docker run -it --rm \
  -e SANDBOX_RUNTIME_CONTAINER_IMAGE=ghcr.io/all-hands-ai/runtime:0.39-nikolaik \
  -e SANDBOX_USER_ID=$(id -u) \
  -e SANDBOX_RUNTIME_BINDING_ADDRESS=127.0.0.1 \
  -e SANDBOX_REMOTE_RUNTIME_API_TIMEOUT=60 \
  -e RUNTIME_MOUNT="$HOME/projects:/workspace:rw" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $HOME/projects:/opt/workspace_base \
  -v $HOME/.openhands-state:/.openhands-state \
  -v $HOME/.openhands-state:/home/enduser/.openhands-state \
  -p 3001:3000 \
  --add-host host.docker.internal:host-gateway \
  -e LLM_MODEL="openai/gpt-5.4" \
  -e LLM_BASE_URL="http://host.docker.internal:4000/v1" \
  -e LLM_API_KEY="$LITELLM_KEY" \
  -e OPENHANDS_STATE_DIR="/.openhands-state" \
  -e GITHUB_PERSONAL_ACCESS_TOKEN \
  ghcr.io/all-hands-ai/openhands:0.39
```

Then open http://localhost:3001 in your browser.
If you need a custom port, run `ml openhands start --port <port>`.

If OpenHands appears stuck on "Waiting for runtime to start", these two env vars are important:
- `SANDBOX_RUNTIME_BINDING_ADDRESS=127.0.0.1` helps avoid Docker Desktop runtime port-forward failures.
- `SANDBOX_REMOTE_RUNTIME_API_TIMEOUT=60` prevents MCP initialization from timing out during runtime boot.

Or use the ManusLocal CLI shortcut:
```bash
ml openhands start
```
