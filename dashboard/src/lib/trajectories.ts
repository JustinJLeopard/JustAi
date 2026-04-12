/**
 * JustAi — Trajectory Client
 *
 * Loads .traj.json files produced by mini-swe-agent runs.
 * Talks to the Vite dev server middleware at /api/trajectories.
 */

// ── Types ──────────────────────────────────────────────────────────────────────

export interface TrajToolCall {
  function: { name: string; arguments: string }
  id: string
  type: string
}

export interface TrajMessage {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string | null
  tool_calls?: TrajToolCall[]
  extra?: {
    actions?: { command: string; tool_call_id: string }[]
    response?: Record<string, unknown>
  }
}

export interface TrajInfo {
  model_stats: { instance_cost: number; api_calls: number }
  config: {
    agent: { mode: string; step_limit: number; cost_limit: number }
    model: { model_name: string }
  }
  mini_version: string
  exit_status: string
  submission: string
}

export interface Trajectory {
  info: TrajInfo
  messages: TrajMessage[]
}

export interface TrajFile {
  name: string
  size: number
  mtime: string
}

/** A single "step" = assistant reasoning + tool call + tool result. */
export interface TrajStep {
  index: number
  reasoning: string
  command: string
  toolName: string
  result: string
  returncode: number | null
}

// ── API ────────────────────────────────────────────────────────────────────────

export async function listTrajectories(): Promise<TrajFile[]> {
  const res = await fetch('/api/trajectories')
  if (!res.ok) throw new Error(`Failed to list trajectories: ${res.status}`)
  return res.json()
}

export async function loadTrajectory(name: string): Promise<Trajectory> {
  const res = await fetch(`/api/trajectories/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`Failed to load trajectory: ${res.status}`)
  return res.json()
}

/** Parse a trajectory into discrete steps (assistant action + tool response pairs). */
export function parseSteps(traj: Trajectory): TrajStep[] {
  const steps: TrajStep[] = []
  const msgs = traj.messages
  let stepIdx = 0

  for (let i = 0; i < msgs.length; i++) {
    const msg = msgs[i]
    if (msg.role !== 'assistant') continue

    const toolCalls = msg.tool_calls ?? []
    if (toolCalls.length === 0 && !msg.content) continue

    // Extract command from tool_calls or extra.actions
    let command = ''
    let toolName = ''
    if (toolCalls.length > 0) {
      const fn = toolCalls[0].function
      toolName = fn.name
      try {
        const args = JSON.parse(fn.arguments)
        command = args.command ?? fn.arguments
      } catch {
        command = fn.arguments
      }
    }

    // Look for following tool result
    let result = ''
    let returncode: number | null = null
    if (i + 1 < msgs.length && msgs[i + 1].role === 'tool') {
      const toolContent = msgs[i + 1].content ?? ''
      try {
        const parsed = JSON.parse(toolContent)
        returncode = parsed.returncode ?? null
        result = parsed.output ?? parsed.output_head ?? toolContent
        if (parsed.output_tail && parsed.output_head) {
          result = parsed.output_head + '\n... (truncated) ...\n' + parsed.output_tail
        }
      } catch {
        result = toolContent
      }
    }

    steps.push({
      index: stepIdx++,
      reasoning: msg.content ?? '',
      command,
      toolName,
      result,
      returncode,
    })
  }

  return steps
}
