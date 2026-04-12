# JustAi v1.0.0 Release Plan

**Primary target:** Wednesday 2026-04-15
**Fallback:** Saturday 2026-04-18

---

## Pre-Release Checklist (Complete by Tuesday 04/14 evening)

### Already Done (Sprint 12)
- [x] All 464 tests pass
- [x] LICENSE file (MIT) at repo root
- [x] CHANGELOG.md at repo root
- [x] README badges (license, python, tests, version)
- [x] README clone URL points to real GitHub repo
- [x] README updated: 7 views, --swarm, 464 tests
- [x] pyproject.toml: URLs, classifiers, keywords
- [x] .gitignore: node_modules, tool configs, screenshots, DBs
- [x] No secrets in tracked files (verified: grep sk-)
- [x] Dashboard TypeScript clean

### Still To Do
- [ ] Verify `bash install.sh` works from clean clone
- [ ] Verify `pip install -e .` and `justai version` works
- [ ] Test `cd dashboard && npm ci && npm run build` (production build)
- [ ] Pick 3-4 best screenshots, commit to `docs/screenshots/`
- [ ] Embed 1-2 screenshots in README
- [ ] Check PyPI name: `pip index versions justai`
- [ ] Write RELEASE_NOTES.md (GitHub release body)
- [ ] Draft social posts (Twitter thread, Reddit, HN)

---

## Day-by-Day

### Sunday 04/13 — Polish (2-3 hours)
- Embed screenshots in README
- Write RELEASE_NOTES.md
- Test install.sh from scratch
- Check PyPI name availability

### Monday 04/14 — Final Prep (2 hours)
- One last `python3 -m pytest tests/`
- Create draft release: `gh release create v1.0.0 --draft`
- Preview on GitHub — check formatting
- Draft social posts

### Tuesday 04/14 evening — Ship It
- Push to main: `git push origin main`
- Tag: `git tag -a v1.0.0 -m "JustAi v1.0.0 — AI orchestration for mini-swe-agent"`
- Push tag: `git push origin v1.0.0`
- Publish release: convert draft to published
- Set topics: `gh repo edit --add-topic ai-agent,swe-bench,code-agent,orchestration,mini-swe-agent,developer-tools,ai-coding,llm-agent,python,react`

### Wednesday 04/15 — Launch Day
- 9:00 AM PT — Submit to Hacker News: "Show HN: JustAi — Orchestration for mini-swe-agent (74% SWE-bench)"
- 10:00 AM PT — Twitter/X thread (problem → solution → screenshot → numbers → link)
- 12:00 PM PT — Reddit r/LocalLLaMA + r/MachineLearning [Project] tag
- Afternoon — Post in SWE-agent Discord, LiteLLM Discord, AI agent communities
- Optional: `pip install build && python -m build && twine upload dist/*` to PyPI

### Thursday 04/16 — Follow-up
- Publish Dev.to article: "Building an AI Orchestrator for the World's Best Code Agent"
- Respond to GitHub issues
- Optional: Product Hunt submission (Thursdays are best)

### Fallback: Saturday 04/18
If Wednesday is missed, shift by 3 days. Saturday HN submissions get lower competition.

---

## GitHub Release Template

```bash
gh release create v1.0.0 \
  --title "v1.0.0 — AI Orchestration for mini-swe-agent" \
  --notes-file RELEASE_NOTES.md \
  docs/screenshots/mission-control.png \
  docs/screenshots/trajectory-viewer.png \
  docs/screenshots/dashboard-dark.png
```

### Release Notes Structure
```
## Highlights
- 9-stage orchestration pipeline with LLM-powered planning and review
- Swarm parallel dispatch via claude-flow (tested 15 to 1500 agents)
- 7 real-time dashboard views with Glass Aurora design
- Trajectory learning: agents improve from past runs
- 464 tests across 12 sprints

## Quick Start
git clone + install.sh + justai run

## Key Numbers
- 464 tests | 22 Python modules | 7 dashboard views
- Swarm dispatch: 1ms at 15 agents, 3ms at 1500 agents
- Trajectory search: 22ms for semantic vector match

## Full Changelog
(link to CHANGELOG.md)
```

---

## Visibility Strategy

| Platform | Timing | Approach |
|----------|--------|----------|
| Hacker News | Wed 9am PT | "Show HN" — short title, link to repo |
| Twitter/X | Wed 10am PT | Thread: problem → solution → screenshot → link |
| Reddit r/LocalLLaMA | Wed 12pm PT | Technical, self-hosted angle, architecture diagram |
| Reddit r/MachineLearning | Wed 12pm PT | [Project] tag, focus on pipeline design |
| Discord communities | Wed afternoon | SWE-agent, LiteLLM, AI builder servers |
| Dev.to | Thu | Tutorial-format article |
| Product Hunt | Thu | "Orchestration for the world's best code agent" |

### GitHub Topics
```
ai-agent, swe-bench, code-agent, orchestration, mini-swe-agent,
developer-tools, ai-coding, llm-agent, python, react
```

---

## PyPI (Optional, Day 1)

```bash
# Check name
pip index versions justai

# Build
pip install build twine
python -m build

# Test
twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ justai

# Publish
twine upload dist/*
```
