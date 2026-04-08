# Claude Learning Log — Self-Improvement System

## Purpose

This document is a persistent learning system designed to make each session
better than the last. Every time Claude reviews sprints, encounters problems,
or discovers better patterns, they get logged here. The next session starts
by reading this file and applying accumulated lessons.

---

## How This Works

### End of Every Session
1. **Log lessons learned** — What went well? What was slow? What surprised me?
2. **Log pattern improvements** — Better ways to review, plan, or communicate
3. **Log tool/env learnings** — WSL quirks, Desktop Commander patterns, etc.
4. **Update the efficiency playbook** — Reusable procedures for common tasks

### Start of Every Session
1. Read this file before doing anything else
2. Apply the efficiency playbook to the day's work
3. Note any new patterns discovered during the session

---

## Lessons Learned

### 2026-04-08 — Sprint 8+9 Review Day

**Session efficiency:**
- Reading WSL files via Desktop Commander is unreliable — `read_file` often
  returns metadata only. PowerShell `Get-Content` via `start_process` is the
  reliable fallback. Use `Get-Content -Tail N` for end-of-file, `-TotalCount N`
  for beginning.
- `read_multiple_files` works for content but can overflow context on large files.
  Use it for small-to-medium docs, individual `start_process` for large source.- `Select-String` (PowerShell grep) is excellent for targeted source verification.
  Pattern + Context flags give exactly the evidence needed for code review.
- `list_directory` works reliably with WSL UNC paths. Always use it first to
  confirm file existence before attempting reads.
- WSL paths: `\\wsl.localhost\Ubuntu-24.04\...` works for Desktop Commander tools.
  Never use Linux-style `/home/...` paths from the Windows side.
- `wsl` command doesn't work from PowerShell in this environment — use
  `cmd.exe /c "wsl ..."` or stick to UNC path access.

**Review patterns:**
- Sprint review is most efficient when done in 3 passes:
  1. Read handoff + scorecard (understand what was claimed)
  2. Verify key implementations in source (spot-check, not exhaustive)
  3. Cross-reference plan vs delivery (catch scope drift)
- Don't verify every file. Focus on the novel/risky implementations:
  new schema fields, new endpoints, new CLI commands, error handling paths.
- The "live validation" section of Codex handoffs is trustworthy when backed
  by specific output examples. Be more skeptical of vague claims.

**Planning patterns:**
- Sprint plans that mix task types (ops, governance, technical) need explicit
  dependency graphs. Don't assume everything can parallelize.
- Draft plans should be marked DRAFT and finalized after team discussion.
- Include risk notes — they've been consistently useful for anticipating blockers.

**Communication:**
- Justin values concise verdicts followed by detail. Lead with the decision,
  follow with evidence.
- When Justin says "make your own call," do it decisively. Don't hedge.

---

## Efficiency Playbook

### Sprint Review Procedure (reusable)
```
1. Read: SPRINT_N_HANDOFF_FOR_CLAUDE.md + SPRINT_N_SCORECARD.md
2. Read: Original SPRINT_N.md plan (for scope comparison)
3. Verify: 2-3 key source files using Select-String for specific patterns
4. Check: Tests exist and handoff says they pass
5. Check: Honcho writeback succeeded
6. Verdict: APPROVED/NEEDS WORK with specific evidence
7. Write: SPRINT_N_REVIEW_BY_CLAUDE.md
```
### Sprint Planning Procedure (reusable)
```
1. Read: Previous sprint retrospective + deferred backlog
2. Read: User's priorities for next sprint
3. Assess: What's the right mix of technical + organizational tasks?
4. Write: Task table with priority, assignee, dependencies
5. Write: Task details with goal, implementation notes, acceptance criteria
6. Write: Dependency graph (ASCII art works fine)
7. Write: Success criteria checklist
8. Write: Risk notes
9. Write: Deferred backlog update
```

### End-of-Day Procedure (reusable)
```
1. Write: END_OF_DAY_YYYYMMDD.md — full project state snapshot
2. Write: SPRINT_N_REVIEW_BY_CLAUDE.md — if sprint was reviewed
3. Update: SPRINT_(N+1).md — draft plan for next sprint
4. Write: CLAUDE_NOTES_YYYYMMDD.md — questions, thoughts, observations
5. Update: CLAUDE_LEARNING_LOG.md (this file) — new lessons + patterns
6. Save: Key docs to Google Drive
7. Verify: All docs cross-reference correctly
```

### File Access Cheatsheet (this environment)
```
# List directory
list_directory("\\wsl.localhost\Ubuntu-24.04\home\justinleopard\projects\relay-room\...")

# Read small files (< 100 lines)
read_multiple_files(["\\\\wsl.localhost\\Ubuntu-24.04\\..."])

# Read specific content
start_process('Get-Content "\\wsl.localhost\Ubuntu-24.04\..." -TotalCount 50')
start_process('Get-Content "\\wsl.localhost\Ubuntu-24.04\..." -Tail 80')

# Search for patterns in source
start_process('Select-String -Path "\\wsl.localhost\...\file.py" -Pattern "regex" -Context 1,3')

# Write files (chunk in 25-30 lines)
write_file("\\wsl.localhost\...\file.md", content, mode="rewrite")
write_file("\\wsl.localhost\...\file.md", more_content, mode="append")
```

---

## Metrics to Track (Self-Assessment)

| Metric | Sprint 8+9 Session | Target |
|--------|-------------------|--------|
| Tool calls to read one file | 3-5 (path issues) | 1-2 |
| Minutes to review a sprint | ~15 min | ~10 min |
| Sprint plan completeness | High (7 tasks, details) | Maintain |
| Questions surfaced for user | Good | Maintain |
| Docs written per session | 6 | As needed |

---

## Growth Areas
- **Speed:** File access is still the bottleneck. Memorize the working path
  patterns and stop experimenting with paths that don't work.
- **Proactivity:** Could have suggested the learning system earlier rather
  than waiting for Justin to ask. Look for meta-improvements unprompted.
- **Depth:** Source verification could go deeper — check error handling paths,
  not just happy paths. The Sprint 9 agent-name bug was caught by Codex live,
  not by me in review.
- **Connections:** Start linking sprint work to larger project goals more
  explicitly. Every task should trace back to a strategic objective.