#!/usr/bin/env python3
# =============================================================================
# ManusLocal — Delegate to Cloud Manus
# Packages local context and sends a task to the cloud Manus instance.
# This handles the <10% of tasks that ManusLocal cannot complete locally.
# =============================================================================

import os
import sys
import json
import requests
from datetime import datetime

def get_honcho_context():
    """Retrieve relevant context from Honcho to include with the delegation."""
    try:
        from honcho import Honcho
        h = Honcho(
            api_key=os.environ.get("HONCHO_API_KEY"),
            workspace_id="dev"
        )
        dev = h.peer("developer")
        context = dev.chat("What are the current active tasks and recent project state?")
        return context
    except Exception as e:
        return f"[Honcho context unavailable: {e}]"

def delegate_task(task_description: str, context: str = "", priority: str = "normal"):
    """
    Delegate a task to the cloud Manus instance.
    
    Args:
        task_description: The task to delegate
        context: Additional context to include
        priority: Task priority (normal, high, urgent)
    """
    api_url = os.environ.get("MANUS_API_URL")
    api_key = os.environ.get("MANUS_API_KEY")
    
    if not api_url:
        print("ERROR: MANUS_API_URL not configured.")
        print("Set MANUS_API_URL in the active LocalManus .env file")
        sys.exit(1)
    
    # Gather local context
    print("Gathering local context from Honcho...")
    honcho_context = get_honcho_context()
    
    # Build the delegation payload
    payload = {
        "task": task_description,
        "context": {
            "source": "ManusLocal",
            "timestamp": datetime.now().isoformat(),
            "machine": "justinleopard@DESKTOP-DEIJL6K (WSL Ubuntu-24.04)",
            "local_model": "qwen3:30b-a3b-q4_K_M",
            "reason_for_delegation": "Task exceeds local capabilities",
            "honcho_context": honcho_context,
            "additional_context": context
        },
        "priority": priority,
        "return_results": True
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Source": "ManusLocal"
    }
    
    print(f"Delegating to cloud Manus at {api_url}...")
    print(f"Task: {task_description}")
    
    try:
        response = requests.post(
            f"{api_url}/api/tasks",
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        print(f"\nDelegation successful!")
        print(f"Task ID: {result.get('task_id', 'N/A')}")
        print(f"Status: {result.get('status', 'submitted')}")
        return result
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Cannot connect to Manus API at {api_url}")
        print("Ensure you are connected to the internet and the API URL is correct.")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: Manus API returned error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python delegate_to_manus.py 'task description' [context]")
        sys.exit(1)
    
    task = sys.argv[1]
    ctx = sys.argv[2] if len(sys.argv) > 2 else ""
    
    delegate_task(task, ctx)
