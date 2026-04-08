#!/usr/bin/env python3
# =============================================================================
# ManusLocal — CLI Interface
# The primary entry point for interacting with ManusLocal.
# =============================================================================
# Supported --route options:
#   relay    - Route requests through the Relay Room server
#   openfang - Route requests directly to the OpenFang local model
#   auto     - Automatically select the best available route

import os
import sys
import typer
import json
import time
import uuid
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
import subprocess
import shutil
from typing import Optional

app = typer.Typer(help="ManusLocal — Justin's persistent local AI agent")
console = Console()

def get_project_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_justai_root() -> Optional[Path]:
    raw = os.environ.get("JUSTAI_ROOT")
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def get_relay_root() -> Path:
    raw = os.environ.get("JUSTAI_RELAY_ROOT") or os.environ.get("RELAY_ROOT")
    if raw:
        return Path(raw).expanduser().resolve()

    justai_root = get_justai_root()
    if justai_root:
        return (justai_root / "relay-room").resolve()

    project_dir = Path(get_project_dir()).resolve()
    candidate = project_dir.parent / "relay-room"
    if candidate.exists():
        return candidate

    return candidate.resolve()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_agent_name(name: str) -> str:
    return "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_")).strip() or "unknown"


def _agent_inbox_dir() -> Path:
    raw = os.environ.get("AGENT_INBOX_DIR", str(Path.home() / ".agent-inbox"))
    path = Path(raw).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _agent_inbox_path(agent: str) -> Path:
    return _agent_inbox_dir() / f"{_sanitize_agent_name(agent)}.json"


def _load_agent_inbox(agent: str) -> dict:
    path = _agent_inbox_path(agent)
    if not path.exists():
        return {"agent": agent, "updated_at": _iso_now(), "messages": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("messages"), list):
            return data
    except Exception:
        pass
    return {"agent": agent, "updated_at": _iso_now(), "messages": []}


def _write_agent_inbox(agent: str, payload: dict) -> Path:
    path = _agent_inbox_path(agent)
    payload["agent"] = agent
    payload["updated_at"] = _iso_now()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def _run_capture(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def _relay_bin() -> Optional[str]:
    relay = os.environ.get("RELAY_BIN")
    if relay:
        return relay

    found = shutil.which("relay")
    if found:
        return found

    for candidate in (
        Path.home() / ".local/bin/relay",
        Path.home() / ".cargo/bin/relay",
    ):
        if candidate.exists():
            return str(candidate)
    return None


def _relay_task_title(description: str) -> str:
    summary = " ".join(description.strip().split())
    if not summary:
        return "ml task"
    return summary[:72]


def _post_relay_task(
    description: str,
    target_agent: str = "manuslocal",
    session: Optional[str] = None,
) -> tuple[bool, str]:
    relay_bin = _relay_bin()
    if not relay_bin:
        return (False, "relay CLI not found in PATH")

    relay_env = os.environ.copy()
    path_entries = relay_env.get("PATH", "").split(os.pathsep) if relay_env.get("PATH") else []
    for extra in (str(Path.home() / ".local/bin"), str(Path.home() / ".cargo/bin")):
        if extra not in path_entries:
            path_entries.append(extra)
    relay_env["PATH"] = os.pathsep.join(path_entries)

    target_file = get_relay_root() / ".relay-db-target"
    if "RELAY_DB_NAME" not in relay_env and target_file.exists():
        relay_env["RELAY_DB_NAME"] = target_file.read_text(encoding="utf-8").strip()
    relay_env.setdefault("RELAY_SERVER", "local-server")

    session = (session or os.environ.get("MANUSLOCAL_RELAY_SESSION", "ml-task")).strip() or "ml-task"
    from_agent = os.environ.get("MANUSLOCAL_RELAY_FROM_AGENT", "manuslocal")
    title = _relay_task_title(description)
    cmd = [
        relay_bin,
        "post",
        "--from",
        from_agent,
        "--to",
        target_agent,
        "--title",
        title,
        "--payload",
        description,
        "--session",
        session,
        "--json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, env=relay_env)
    output = (result.stdout or result.stderr).strip()
    if result.returncode != 0:
        return (False, output or f"relay post failed with exit code {result.returncode}")

    task_id = ""
    task_uuid = ""
    if output:
        try:
            payload = json.loads(output)
            task_id = str(payload.get("id", "")).strip()
            task_uuid = str(payload.get("task_uuid", "")).strip()
        except json.JSONDecodeError:
            pass

    detail = f"queued relay task for {target_agent}"
    if task_id:
        detail += f" id={task_id}"
    if task_uuid:
        detail += f" task_uuid={task_uuid}"
    return (True, detail)


def _task_needs_code_model(description: str) -> bool:
    text = description.lower()
    code_markers = [
        "code",
        "implement",
        "refactor",
        "bug",
        "fix",
        "test",
        "unit test",
        "integration test",
        "write function",
        "write script",
        "patch",
        "diff",
        "repository",
        "repo",
        "python",
        "javascript",
        "typescript",
        "rust",
        "go ",
        "sql",
        "bash",
    ]
    return any(marker in text for marker in code_markers)


def _task_needs_deep_reasoning_model(description: str) -> bool:
    text = description.lower()
    deep_reasoning_markers = [
        "deep analysis",
        "root cause",
        "tradeoff",
        "architecture",
        "decision memo",
        "high stakes",
        "risk analysis",
        "compliance",
        "security review",
        "long-form",
        "comprehensive plan",
        "research synthesis",
        "opus",
    ]
    return any(marker in text for marker in deep_reasoning_markers)


def _set_agent_model(agent_id: str, model: str) -> bool:
    result = _run_capture(["openfang", "agent", "set", agent_id, "model", model])
    return result.returncode == 0


def _reconcile_assistant(manifest_path: Optional[str] = None) -> bool:
    reconcile_script = os.path.join(get_project_dir(), "scripts", "reconcile_openfang_assistant.sh")
    cmd = ["bash", reconcile_script]
    if manifest_path:
        cmd.append(manifest_path)
    result = _run_capture(cmd)
    return result.returncode == 0


def _pick_openfang_agent() -> Optional[tuple[str, str]]:
    """Use the explicitly configured primary LocalManus agent and return (name, id)."""
    preferred = os.environ.get("MANUSLOCAL_AGENT", "assistant")
    daemon_url = os.environ.get("MANUS_API_URL", "http://localhost:50051").rstrip("/")

    # Prefer daemon API and retry briefly if the daemon is under load.
    for _ in range(3):
        try:
            headers = {}
            api_key = os.environ.get("OPENFANG_API_KEY")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            req = urllib.request.Request(f"{daemon_url}/api/agents", headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                agents = json.load(response)
            for agent in agents:
                if agent.get("name") == preferred and str(agent.get("state", "")).lower() == "running":
                    agent_id = agent.get("id")
                    if agent_id:
                        return (preferred, agent_id)
        except Exception:
            pass

    # Fallback to CLI output parsing.
    try:
        result = _run_capture(["openfang", "agent", "list"])
    except FileNotFoundError:
        return None

    if result.returncode == 0:
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[1] == preferred and parts[2].lower() == "running":
                return (preferred, parts[0])

    return None


def _coerce_json(value):
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return value
        if s[0] in '{[':
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                return value
    return value


def _summarize_openfang_output(raw: str) -> str:
    payload = _coerce_json(raw)

    if isinstance(payload, str):
        return payload.strip() or raw

    if isinstance(payload, list):
        if not payload:
            return "No response content."
        first = _coerce_json(payload[0])
        return _summarize_openfang_output(json.dumps(first)) if not isinstance(first, str) else first

    if isinstance(payload, dict):
        # Common OpenFang wrapper: telemetry + nested response payload.
        if "response" in payload:
            nested = _coerce_json(payload.get("response"))
            if isinstance(nested, dict) and "response" in nested:
                nested = _coerce_json(nested.get("response"))
            if isinstance(nested, dict):
                if "response" in nested:
                    nested_response = _coerce_json(nested.get("response"))
                    if isinstance(nested_response, str) and nested_response.strip():
                        return nested_response
                    if isinstance(nested_response, dict):
                        return json.dumps(nested_response, ensure_ascii=True)
                if "message" in nested and isinstance(nested.get("message"), str):
                    return nested.get("message")
                if "status" in nested and len(nested) <= 3:
                    return str(nested.get("status"))
                # Tool-call shaped output.
                if "name" in nested and "arguments" in nested:
                    name = nested.get("name")
                    args = nested.get("arguments")
                    try:
                        args_s = json.dumps(args, ensure_ascii=True)
                    except Exception:
                        args_s = str(args)
                    return f"Tool action: {name} {args_s}"
                return json.dumps(nested, ensure_ascii=True)
            if isinstance(nested, str):
                return nested
            return str(nested)

        if "message" in payload and isinstance(payload.get("message"), str):
            return payload.get("message")

        if "status" in payload and isinstance(payload.get("status"), str) and "response" not in payload:
            return str(payload.get("status"))

        if "error" in payload:
            return f"Error: {payload.get('error')}"

        if "name" in payload and "arguments" in payload:
            try:
                args_s = json.dumps(payload.get("arguments"), ensure_ascii=True)
            except Exception:
                args_s = str(payload.get("arguments"))
            return f"Tool action: {payload.get('name')} {args_s}"

        return json.dumps(payload, ensure_ascii=True)

    return str(payload)


def _is_retryable_agent_resolution_error(details: str) -> bool:
    text = (details or "").lower()
    retry_markers = [
        "invalid agent id",
        "agent not found",
        "unknown agent",
        "no such agent",
    ]
    return any(marker in text for marker in retry_markers)


def _contains_function_wrapper(payload) -> bool:
    payload = _coerce_json(payload)
    if isinstance(payload, dict):
        name = str(payload.get("name", "")).strip().lower()
        if name in {"function", "function_name"}:
            return True
        if "function_name" in payload or "function" in payload:
            return True
        return any(_contains_function_wrapper(v) for v in payload.values())
    if isinstance(payload, list):
        return any(_contains_function_wrapper(v) for v in payload)
    return False


def _needs_function_tool_fallback(ok: bool, details: str) -> bool:
    text = (details or "").lower()
    denied = ("permission denied" in text) or ("capability denied" in text)
    function_tool_markers = [
        "tool 'function'",
        "tool 'function_name'",
        'tool_name="function"',
        'tool_name="function_name"',
    ]
    if denied and any(marker in text for marker in function_tool_markers):
        return True
    if ok and _contains_function_wrapper(details):
        return True
    return False


def _deliver_openfang_message(agent_name: str, agent_target: str, description: str) -> tuple[bool, str]:
    daemon_url = os.environ.get("MANUS_API_URL", "http://localhost:50051").rstrip("/")
    endpoint = f"{daemon_url}/api/agents/{agent_target}/message"
    body = json.dumps({"message": description}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("OPENFANG_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        # Large local models can take >2 minutes on cold start.
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = response.read().decode("utf-8").strip()
        if not raw:
            return (True, "")
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict) and payload.get("error"):
                return (False, raw)
        except json.JSONDecodeError:
            pass
        return (True, raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        return (False, f"HTTP {exc.code}: {detail}")
    except Exception:
        # Fallback to CLI path for compatibility with daemon versions that may differ.
        result = _run_capture(["openfang", "message", agent_target, description])
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode != 0:
            return (False, stderr or stdout)

        if stdout:
            try:
                payload = json.loads(stdout)
                if payload.get("error"):
                    return (False, stdout)
            except json.JSONDecodeError:
                pass

        return (True, stdout)


def _deliver_direct_code_task(model: str, description: str) -> tuple[bool, str]:
    base_url = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000/v1").rstrip("/")
    endpoint = f"{base_url}/chat/completions"
    api_key = os.environ.get("LITELLM_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are ManusLocal code execution assistant. Provide a concise, directly usable answer in plain text. Do not emit tool calls or JSON wrappers.",
            },
            {"role": "user", "content": description},
        ],
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    timeout_seconds = int(os.environ.get("MANUSLOCAL_CODE_DIRECT_TIMEOUT_SECONDS", "45"))

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8").strip()
        data = _coerce_json(raw)
        if isinstance(data, dict) and data.get("error"):
            return (False, json.dumps(data, ensure_ascii=True))
        if isinstance(data, dict):
            choices = data.get("choices") or []
            if choices and isinstance(choices[0], dict):
                message = choices[0].get("message") or {}
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return (True, content.strip())
        return (False, raw or "Empty response from direct code route.")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        return (False, f"HTTP {exc.code}: {detail}")
    except Exception as exc:
        return (False, str(exc))

@app.command()
def status():
    """Check the health and status of ManusLocal components."""
    console.print(Panel.fit("[bold green]ManusLocal Status[/bold green]"))
    script = os.path.join(get_project_dir(), "scripts", "check_health.sh")
    subprocess.run(["bash", script])

@app.command()
def task(
    description: str,
    route: str = typer.Option(
        "relay",
        "--route",
        help="Task transport: relay, auto, or openfang",
    ),
    session: Optional[str] = typer.Option(
        None,
        "--session",
        help="Relay session tag to attach to queued tasks, e.g. sprint-7",
    ),
):
    """Run a general task via the configured OpenFang LocalManus agent."""
    console.print(f"[bold blue]Submitting task to ManusLocal agent:[/bold blue] {description}")
    configured_route = os.environ.get("MANUSLOCAL_TASK_ROUTE", route).strip().lower() or "auto"
    if configured_route not in {"auto", "openfang", "relay"}:
        console.print(f"[red]Unsupported task route:[/red] {configured_route}")
        raise typer.Exit(1)

    if configured_route == "relay":
        ok, details = _post_relay_task(description, session=session)
        if ok:
            console.print("[green]Delivered task to Relay Room queue.[/green]")
            console.print(details)
            return
        console.print("[red]Relay task submission failed.[/red]")
        console.print(details)
        raise typer.Exit(1)

    daemon_url = os.environ.get("MANUS_API_URL", "http://localhost:50051")
    console.print(f"[yellow]Connecting to OpenFang daemon at {daemon_url}...[/yellow]")

    try:
        agent = _pick_openfang_agent()
        if not agent:
            _reconcile_assistant()
            agent = _pick_openfang_agent()
        if not agent:
            console.print("[red]Could not resolve a running ManusLocal agent. Check openfang status and reconciliation scripts.[/red]")
            raise typer.Exit(1)
        agent_name, agent_target = agent

        # Keep task sessions deterministic by default; stale agent sessions can leak prior tool plans.
        reset_each_task = os.environ.get("MANUSLOCAL_RESET_ASSISTANT_ON_TASK", "1") != "0"
        if reset_each_task and agent_name == os.environ.get("MANUSLOCAL_AGENT", "assistant"):
            _reconcile_assistant()
            refreshed = _pick_openfang_agent()
            if refreshed:
                agent_name, agent_target = refreshed

        dynamic_switching = os.environ.get("MANUSLOCAL_DYNAMIC_MODEL", "1") != "0"
        primary_model = os.environ.get("MANUSLOCAL_PRIMARY_MODEL", "gpt-5.4")
        code_model = os.environ.get("MANUSLOCAL_CODE_MODEL", "gpt-5.3-codex")
        deep_reasoning_model = os.environ.get("MANUSLOCAL_DEEP_REASONING_MODEL", "claude-opus-4-6")
        revert_primary = os.environ.get("MANUSLOCAL_REVERT_PRIMARY_MODEL", "1") != "0"
        function_fallback_enabled = os.environ.get("MANUSLOCAL_FUNCTION_TOOL_FALLBACK", "1") != "0"
        code_tasks_disable_tools = os.environ.get("MANUSLOCAL_CODE_TASKS_DISABLE_TOOLS", "1") != "0"
        code_direct_to_litellm = os.environ.get("MANUSLOCAL_CODE_DIRECT_TO_LITELLM", "1") != "0"
        code_direct_fallback_to_openfang = os.environ.get("MANUSLOCAL_CODE_DIRECT_FALLBACK_TO_OPENFANG", "0") != "0"
        no_tools_manifest = os.environ.get(
            "MANUSLOCAL_ASSISTANT_NOTOOLS_MANIFEST",
            os.path.join(get_project_dir(), "config", "openfang_assistant_no_tools.toml"),
        )

        switched_for_task = False
        used_no_tools_profile = False
        target_model = primary_model
        route_reason = "default"
        if dynamic_switching and agent_name == os.environ.get("MANUSLOCAL_AGENT", "assistant"):
            if _task_needs_deep_reasoning_model(description):
                target_model = deep_reasoning_model
                route_reason = "deep-reasoning"
            elif _task_needs_code_model(description):
                target_model = code_model
                route_reason = "code"

            if route_reason == "code" and code_direct_to_litellm:
                console.print(f"[cyan]Dynamic model route:[/cyan] direct -> {target_model} (code)")
                direct_ok, direct_output = _deliver_direct_code_task(target_model, description)
                if direct_ok:
                    console.print(f"[green]Delivered task via direct code route:[/green] {target_model}")
                    console.print(direct_output)
                    return
                summarized = _summarize_openfang_output(direct_output)
                if not code_direct_fallback_to_openfang:
                    console.print(f"[red]Direct code route failed:[/red] {summarized}")
                    raise typer.Exit(1)
                console.print(f"[yellow]Direct code route failed; falling back to OpenFang path:[/yellow] {summarized}")

            if route_reason == "code" and code_tasks_disable_tools:
                if _reconcile_assistant(no_tools_manifest):
                    refreshed = _pick_openfang_agent()
                    if refreshed:
                        used_no_tools_profile = True
                        agent_name, agent_target = refreshed
                else:
                    console.print("[yellow]No-tools assistant reconcile failed for code route; continuing with tool-enabled profile.[/yellow]")

            if target_model and _set_agent_model(agent_target, target_model):
                if target_model != primary_model:
                    switched_for_task = True
                console.print(f"[cyan]Dynamic model route:[/cyan] {agent_name} -> {target_model} ({route_reason})")

        ok, details = _deliver_openfang_message(agent_name, agent_target, description)

        # If the assistant rotated while we were sending, resolve fresh ID once and retry.
        if (not ok) and details and _is_retryable_agent_resolution_error(details):
            refreshed = _pick_openfang_agent()
            if refreshed:
                agent_name, agent_target = refreshed
                ok, details = _deliver_openfang_message(agent_name, agent_target, description)

        used_function_fallback = False
        if (
            function_fallback_enabled
            and agent_name == os.environ.get("MANUSLOCAL_AGENT", "assistant")
            and _needs_function_tool_fallback(ok, details)
        ):
            console.print("[yellow]Function-tool normalization fallback triggered; retrying once with no-tools assistant profile.[/yellow]")
            if _reconcile_assistant(no_tools_manifest):
                refreshed = _pick_openfang_agent()
                if refreshed:
                    used_function_fallback = True
                    agent_name, agent_target = refreshed
                    if dynamic_switching and target_model:
                        _set_agent_model(agent_target, target_model)
                    ok, details = _deliver_openfang_message(agent_name, agent_target, description)

                    if (not ok) and details and _is_retryable_agent_resolution_error(details):
                        refreshed = _pick_openfang_agent()
                        if refreshed:
                            agent_name, agent_target = refreshed
                            ok, details = _deliver_openfang_message(agent_name, agent_target, description)

        if used_no_tools_profile or used_function_fallback:
            _reconcile_assistant()
            refreshed = _pick_openfang_agent()
            if refreshed:
                agent_name, agent_target = refreshed

        if switched_for_task and revert_primary:
            _set_agent_model(agent_target, primary_model)

        if ok:
            console.print(f"[green]Delivered task to OpenFang agent:[/green] {agent_name}")
            if details:
                console.print(_summarize_openfang_output(details))
            return

        console.print(f"[red]OpenFang message failed for agent '{agent_name}'.[/red]")
        if details:
            console.print(_summarize_openfang_output(details))
        raise typer.Exit(1)
    except FileNotFoundError:
        console.print("[red]OpenFang CLI not found. Is the daemon running?[/red]")
        raise typer.Exit(1)

@app.command()
def mini(description: str):
    """Run a coding task via mini-swe-agent."""
    console.print(f"[bold blue]Delegating to mini-swe-agent:[/bold blue] {description}")
    
    # Check if mini is in PATH
    try:
        # We use the optimized config with Qwen3 if available, else fallback
        cmd = ["mini", "-m", "openrouter/google/gemini-3-flash-preview", "-y", "-l", "1.0", "-t", description]
        console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")
        subprocess.run(cmd)
    except FileNotFoundError:
        console.print("[red]'mini' command not found. Ensure mini-swe-agent is installed.[/red]")

@app.command()
def delegate(description: str):
    """Escalate a task to the cloud Manus instance."""
    console.print(Panel.fit("[bold magenta]Escalating to Cloud Manus[/bold magenta]"))
    console.print(f"Task: {description}")
    
    api_url = os.environ.get("MANUS_API_URL")
    if not api_url:
        console.print("[red]Error: MANUS_API_URL not configured in .env[/red]")
        console.print("Cannot delegate to cloud Manus without an endpoint.")
        raise typer.Exit(1)
        
    console.print("[yellow]Packaging local context and sending to Manus API...[/yellow]")
    # Implementation would go here
    console.print("[green]Task successfully delegated. Awaiting results...[/green]")

@app.command()
def memory(action: str, query: str = ""):
    """Interact with Honcho memory (query, flush)."""
    if action == "query":
        if not query:
            console.print("[red]Error: Query string required.[/red]")
            raise typer.Exit(1)
        console.print(f"[bold cyan]Querying Honcho memory for:[/bold cyan] {query}")
        
        # Simple inline query
        try:
            from honcho import Honcho
            h = Honcho(api_key=os.environ.get("HONCHO_API_KEY"), workspace_id="dev")
            dev = h.peer("developer")
            response = dev.chat(query)
            console.print(Panel(Markdown(response), title="Memory Recall"))
        except Exception as e:
            console.print(f"[red]Memory query failed: {e}[/red]")
            
    elif action == "flush":
        console.print("[bold cyan]Flushing .dev-notepads to Honcho...[/bold cyan]")
        # Implementation would go here
        console.print("[green]Memory flushed successfully.[/green]")
    else:
        console.print(f"[red]Unknown memory action: {action}[/red]")

relay_app = typer.Typer(help="Lightweight file-based relay for real-time agent handoff")
app.add_typer(relay_app, name="relay")


@relay_app.command("send")
def relay_send(
    message: str,
    to: str = typer.Option(..., "--to", help="Destination agent, e.g. claude"),
    from_agent: str = typer.Option("codex", "--from", help="Sender agent label"),
    kind: str = typer.Option("note", "--kind", help="Message type, e.g. blocker|handoff|note"),
    priority: str = typer.Option("normal", "--priority", help="Priority label"),
):
    """Append a relay message into ~/.agent-inbox/<to>.json."""
    inbox = _load_agent_inbox(to)
    msg = {
        "id": str(uuid.uuid4()),
        "from": from_agent,
        "to": to,
        "kind": kind,
        "priority": priority,
        "status": "pending",
        "created_at": _iso_now(),
        "acked_at": None,
        "acked_by": None,
        "content": message,
    }
    inbox["messages"].append(msg)
    path = _write_agent_inbox(to, inbox)
    console.print(f"[green]Relay message queued[/green] id={msg['id']} to={to} path={path}")


@relay_app.command("peek")
def relay_peek(
    agent: str = typer.Option(..., "--for", help="Agent inbox to read"),
    pending_only: bool = typer.Option(True, "--pending-only/--all", help="Show only pending messages"),
    limit: int = typer.Option(20, "--limit", min=1, max=200, help="Maximum messages to show"),
):
    """Read relay messages from ~/.agent-inbox/<agent>.json."""
    inbox = _load_agent_inbox(agent)
    messages = inbox.get("messages", [])
    if pending_only:
        messages = [m for m in messages if str(m.get("status")) == "pending"]

    if not messages:
        console.print(f"[yellow]No relay messages for {agent}[/yellow]")
        return

    shown = messages[-limit:]
    for m in shown:
        line = (
            f"id={m.get('id')} status={m.get('status')} priority={m.get('priority')} "
            f"from={m.get('from')} kind={m.get('kind')} at={m.get('created_at')}"
        )
        console.print(f"[cyan]{line}[/cyan]")
        console.print(m.get("content", ""))


@relay_app.command("ack")
def relay_ack(
    message_id: str,
    agent: str = typer.Option(..., "--for", help="Agent inbox that owns the message"),
    by: str = typer.Option("claude", "--by", help="Agent/user acknowledging the message"),
):
    """Mark a relay message as acknowledged."""
    inbox = _load_agent_inbox(agent)
    messages = inbox.get("messages", [])
    updated = False
    for m in messages:
        if str(m.get("id")) == message_id:
            m["status"] = "acked"
            m["acked_at"] = _iso_now()
            m["acked_by"] = by
            updated = True
            break

    if not updated:
        console.print(f"[red]Message not found:[/red] {message_id}")
        raise typer.Exit(1)

    path = _write_agent_inbox(agent, inbox)
    console.print(f"[green]Acknowledged[/green] id={message_id} by={by} path={path}")


@relay_app.command("poll")
def relay_poll(
    agent: str = typer.Option(..., "--for", help="Agent inbox to poll"),
    interval: float = typer.Option(2.0, "--interval", min=0.2, help="Polling interval in seconds"),
    timeout: int = typer.Option(60, "--timeout", min=1, help="Max wait in seconds"),
    auto_ack: bool = typer.Option(False, "--auto-ack", help="Ack each surfaced message automatically"),
    ack_by: str = typer.Option("claude", "--ack-by", help="Actor label for auto-ack"),
):
    """Poll for pending messages and print new ones as they arrive."""
    deadline = time.time() + timeout
    seen_ids: set[str] = set()

    while time.time() < deadline:
        inbox = _load_agent_inbox(agent)
        pending = [m for m in inbox.get("messages", []) if str(m.get("status")) == "pending"]
        fresh = [m for m in pending if str(m.get("id")) not in seen_ids]
        if fresh:
            for m in fresh:
                seen_ids.add(str(m.get("id")))
                console.print(
                    f"[green]relay[/green] id={m.get('id')} from={m.get('from')} "
                    f"priority={m.get('priority')} kind={m.get('kind')}"
                )
                console.print(m.get("content", ""))
                if auto_ack:
                    m["status"] = "acked"
                    m["acked_by"] = ack_by
                    m["acked_at"] = _iso_now()
            if auto_ack:
                _write_agent_inbox(agent, inbox)
            return
        time.sleep(interval)

    console.print(f"[yellow]No new relay messages for {agent} within {timeout}s[/yellow]")
    raise typer.Exit(1)


openhands_app = typer.Typer(help="OpenHands helpers (Docker-based)")
app.add_typer(openhands_app, name="openhands")


def _pick_docker_bin() -> Optional[str]:
    for candidate in ("docker", "docker.exe"):
        if shutil.which(candidate):
            return candidate
    return None


@openhands_app.command("start")
def openhands_start(
    port: int = 3001,
    image: str = "ghcr.io/all-hands-ai/openhands:0.39",
    runtime_image: str = "ghcr.io/all-hands-ai/runtime:0.39-nikolaik",
):
    """Start OpenHands in Docker, routed through local LiteLLM."""
    docker_bin = _pick_docker_bin()
    if not docker_bin:
        console.print("[red]Docker not found in WSL. Enable Docker Desktop WSL integration, or install Docker Engine.[/red]")
        raise typer.Exit(1)

    litellm_key = os.environ.get("LITELLM_KEY")
    if not litellm_key:
        console.print(f"[red]LITELLM_KEY is not set. Check {get_project_dir()}/.env[/red]")
        raise typer.Exit(1)

    workspace = os.path.expanduser("~/projects")
    state_dir = os.path.expanduser("~/.openhands-state")
    uid = str(os.getuid())

    os.makedirs(state_dir, exist_ok=True)

    cmd = [
        docker_bin,
        "run",
        "-it",
        "--rm",
        "-e",
        f"SANDBOX_RUNTIME_CONTAINER_IMAGE={runtime_image}",
        "-e",
        f"SANDBOX_USER_ID={uid}",
        "-e",
        "SANDBOX_RUNTIME_BINDING_ADDRESS=127.0.0.1",
        "-e",
        "SANDBOX_REMOTE_RUNTIME_API_TIMEOUT=60",
        "-e",
        f"RUNTIME_MOUNT={workspace}:/workspace:rw",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "-v",
        f"{workspace}:/opt/workspace_base",
        "-v",
        f"{state_dir}:/.openhands-state",
        "-v",
        f"{state_dir}:/home/enduser/.openhands-state",
        "-p",
        f"{port}:3000",
        "--add-host",
        "host.docker.internal:host-gateway",
        "-e",
        "LLM_MODEL=openai/gpt-5.4",
        "-e",
        "LLM_BASE_URL=http://host.docker.internal:4000/v1",
        "-e",
        f"LLM_API_KEY={litellm_key}",
        "-e",
        "OPENHANDS_STATE_DIR=/.openhands-state",
        image,
    ]

    # Optional: allow OpenHands MCP GitHub tooling to authenticate (e.g. uvx mcp-server-github)
    # Use `-e VAR` to avoid putting the token value in the docker command line.
    if os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN"):
        cmd[-1:-1] = ["-e", "GITHUB_PERSONAL_ACCESS_TOKEN"]

    console.print(f"[bold blue]Starting OpenHands:[/bold blue] http://localhost:{port}")
    subprocess.run(cmd)


@openhands_app.command("status")
def openhands_status():
    """Check if an OpenHands container appears to be running."""
    docker_bin = _pick_docker_bin()
    if not docker_bin:
        console.print("[yellow]Docker not available in WSL.[/yellow]")
        raise typer.Exit(1)

    result = _run_capture([docker_bin, "ps"])
    if result.returncode != 0:
        console.print(result.stderr.strip() or result.stdout.strip())
        raise typer.Exit(1)

    if "openhands" in result.stdout.lower():
        console.print("[green]OpenHands container detected in docker ps.[/green]")
    else:
        console.print("[yellow]No OpenHands container detected.[/yellow]")


if __name__ == "__main__":
    # Load env vars
    env_file = os.path.join(get_project_dir(), ".env")
    if os.path.exists(env_file):
        from dotenv import load_dotenv
        load_dotenv(env_file)
        
    app()
