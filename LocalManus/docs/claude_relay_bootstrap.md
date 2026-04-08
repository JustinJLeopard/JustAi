# Claude Desktop Relay Bootstrap

This is the real-time companion channel to Honcho.

- Honcho: durable memory and cross-session summaries.
- Relay inbox (`~/.agent-inbox/*.json`): immediate blocker/handoff signals.

## Paths

- Claude inbox file: `~/.agent-inbox/claude.json`
- Codex inbox file: `~/.agent-inbox/codex.json`

## Claude startup sequence

```bash
# 1) Read queued pending handoffs
ml relay peek --for claude

# 2) Optional active wait for new handoff
ml relay poll --for claude --timeout 120 --interval 2

# 3) Acknowledge handled message(s)
ml relay ack <message-id> --for claude --by claude
```

## Codex send examples

```bash
ml relay send --to claude --from codex --kind blocker --priority high \
  'Blocked on schema decision for relay-room API.'

ml relay send --to claude --from codex --kind handoff \
  'Implemented LiteLLM routing patch; need architecture review before merge.'
```

## Back-channel to Codex

```bash
ml relay send --to codex --from claude --kind decision \
  'Use option B. Keep API versioned at /v2.'
```
