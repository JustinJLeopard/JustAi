# Phase 5 Ratification

## Summary

Go, with owner action required before public exposure for historical secret rotation. The post-Phase-4 codebase passes tests, lint, type checks, current-tree secret scanning, full-history secret scanning with a narrow documented historical allowlist, Python and dashboard dependency audits, license metadata checks, clean virtualenv install verification, dashboard build verification, dashboard static smoke testing, and the 3-repo plan consistency audit.

## Branch + commit

- Branch: `refactor/phase5-ratification`
- Phase 4 parent/base: `9519eb7d3bc2280fd425bf4adf5b305b9cf605d0` (`refactor/phase4-chunk-gh` at branch cut)
- Ratification commit: this report is committed on top of the Phase 4 parent; use `git rev-parse HEAD` after checkout/pull for the exact immutable commit SHA.
- Memory snapshot: `/home/justinleopard/.swarm/memory.db.bak.20260430-1834-pre-phase5`

## Secret findings

Commands run:

- `/tmp/gitleaks version`: `8.30.1`
- `/tmp/gitleaks detect --source . --no-banner --redact --report-path /tmp/justai/gitleaks-report.json --report-format json --exit-code 0`
- `/tmp/gitleaks detect --source . --no-banner --redact --log-opts="--all" --exit-code 0`
- Re-run after action: `/tmp/gitleaks detect --source . --no-banner --redact --report-path /tmp/justai/gitleaks-report-after.json --report-format json --exit-code 1`
- Re-run after action: `/tmp/gitleaks detect --source . --no-banner --redact --log-opts="--all" --exit-code 1`

Findings surfaced:

| Rule | File | Line | Git-history extent | Classification | Action |
| --- | --- | ---: | --- | --- | --- |
| `generic-api-key` | `LocalManus/memory/seed_identity.py` | 23 | Historical only, commit `92a6e26f5ee096e11c41a91603d354ae08749e47`; file absent from current HEAD | True positive Honcho key fallback | Documented; owner should revoke/rotate Honcho key if not already done |
| `generic-api-key` | `LocalManus/scripts/setup_env.sh` | 36 | Historical only, same initial snapshot commit; file absent from current HEAD | True positive Honcho key | Documented; owner should revoke/rotate Honcho key if not already done |
| `generic-api-key` | `LocalManus/scripts/setup_manuslocal.sh` | 48 | Historical only, same initial snapshot commit; file absent from current HEAD | True positive Honcho key | Documented; owner should revoke/rotate Honcho key if not already done |
| `generic-api-key` | `LocalManus/scripts/setup_manuslocal.sh` | 51 | Historical only, same initial snapshot commit; file absent from current HEAD | True positive OpenRouter key | Documented; owner should revoke/rotate OpenRouter key if not already done |
| `telegram-bot-api-token` | `LocalManus/scripts/setup_manuslocal.sh` | 54 | Historical only, same initial snapshot commit; file absent from current HEAD | True positive Telegram bot token | Documented; owner should revoke/rotate Telegram bot token if not already done |

Manual context note: the same historical setup script also contained a local LiteLLM-style `OPENAI_API_KEY` assignment near the detected lines. It was not emitted as a gitleaks finding, but should be treated as historical exposure and revoked/rotated if it ever mapped to a live credential.

Fix applied:

- Added `.gitleaks.toml` extending default rules and allowlisting only commit `92a6e26f5ee096e11c41a91603d354ae08749e47`, with an explicit historical-secret rationale.
- Final current-tree and full-history gitleaks scans exit 0 with no leaks found.

## Python dep audit

Commands run:

- `.venv/bin/pip install pip-audit`
- `.venv/bin/pip-audit --format json --output /tmp/justai/pip-audit.json`
- `.venv/bin/pip-audit`
- `.venv/bin/pip install --upgrade pip`
- `.venv/bin/pip-audit --format json --output /tmp/justai/pip-audit-after.json`
- `.venv/bin/pip-audit`

Initial result:

- `pip 24.0` in the audit virtualenv had 3 known vulnerabilities: `CVE-2025-8869`, `CVE-2026-1703`, and `CVE-2026-3219`.
- `justai` was skipped because the editable local package is not on PyPI.

Fix applied:

- Upgraded the local audit environment's `pip` to `26.1`.

Final result:

- `pip-audit` reports no known vulnerabilities across 61 audited dependencies.
- Remaining skip: editable local package `justai (1.0.0)` cannot be audited through PyPI lookup.

## JS dep audit

Commands run in `dashboard/`:

- `npm audit --omit=dev --json > /tmp/justai/npm-audit-prod.json`
- `npm audit --omit=dev`
- `npm audit --json > /tmp/justai/npm-audit-all.json`
- `npm audit`
- `npm audit fix`
- Re-run prod and all-dependency audit commands, writing `*-after.json`

Initial result:

- Production dependencies: 0 vulnerabilities.
- All dependencies: 1 moderate dev/build-chain vulnerability in `postcss <8.5.10` (`GHSA-qx2v-qp2m-jg93`), with non-breaking fix available.

Fix applied:

- Ran `npm audit fix`, updating `dashboard/package-lock.json`.

Final result:

- Production audit: 0 vulnerabilities.
- All-dependency audit: 0 vulnerabilities.

## License audit

Checks:

- `LICENSE` exists at repo root.
- License text is MIT.
- Copyright holder is `Justin Leopard`.
- Year is `2026`.
- `pyproject.toml` has `license = {text = "MIT"}`.
- `dashboard/package.json` now has `"license": "MIT"`.
- `README.md` has a license section pointing to `LICENSE`.
- No vendored third-party source trees were found outside ignored dependency directories.

Fixes/artifacts:

- Added `"license": "MIT"` to `dashboard/package.json`.
- Generated `docs/THIRD_PARTY_LICENSES.md` with `pip-licenses --format=markdown`.

## Clean-venv install verify

Commands run:

- Created `/tmp/justai/clean-venv`
- `pip install --upgrade pip`
- `pip install -e '.[dev]' 2>&1 | tee /tmp/justai/clean-install.log`
- `python -c "import justai; print(justai.__file__)"`
- `which justai-cli || which justai || python -m justai --help || true`
- `pytest -q tests/`

Result:

- Install duration: `0:09.01`
- Clean venv size: `150M`
- Import path: `/home/justinleopard/projects/JustAi-verify-2026-04-30/justai/__init__.py`
- Console script found: `/tmp/justai/clean-venv/bin/justai`
- Pip warnings/errors: none found in install log
- Tests: `370 passed, 14 subtests passed in 6.97s`

## Dashboard build verify

Commands run in `dashboard/`:

- `rm -rf node_modules dist`
- `npm ci`
- `npm run build`
- `ls -la dist/`
- `du -sh dist/`
- `npx serve dist -l 4173 -s` plus `curl -sI http://localhost:4173/`

Result:

- `npm ci` duration: `0:07.72`
- Build duration: `0:04.37`
- Vite build: success, 696 modules transformed, built in 2.31s
- Dist size: `652K`
- Smoke test: `HTTP/1.1 200 OK`, `Content-Type: text/html; charset=utf-8`
- Warning accepted: Vite reports the main JS chunk is `649.90 kB` after minification, above the 500 kB advisory threshold. This is a bundle-size warning, not a build failure.

## 3-repo plan consistency

Memory keys consulted:

- `safe-mini-substrate-architecture`
- `justai-safe-mini-scaffold-pattern`

Audit result:

- `justai/runner_protocol.py` exists and contains the local stub `AgentRunner` Protocol and safe-mini migration TODO.
- `README.md` references `safe-mini`, `justai`, and `local-resident`.
- `docs/ARCHITECTURE.md` references the 3-repo decomposition and assigns `safe-mini` as the future runtime substrate and `local-resident` as the experiment/calibration driver.
- No live code imports `safe_mini`; current code imports the local `justai.runner_protocol` stub.
- `pyproject.toml` does not declare `safe-mini` as a dependency.

Fix applied:

- Added a comment block to `pyproject.toml` showing the future Phase A git URL dependency shape and Phase B version-pin transition, without declaring the dependency now.

## Final test/lint/type results

Commands run:

- `.venv/bin/pytest -q --tb=short 2>&1 | tee /tmp/justai/final-pytest.log`
- `.venv/bin/ruff check justai tests`
- `.venv/bin/mypy justai`

Result:

- Pytest: `370 passed, 14 subtests passed in 7.11s`
- Ruff: all checks passed
- Mypy: success, no issues found in 22 source files

## Open items / accepted risks

- Historical secrets remain in pre-existing git history at commit `92a6e26f5ee096e11c41a91603d354ae08749e47`. They are absent from current HEAD and are narrowly allowlisted for ratification scans, but public release should not proceed until Justin confirms the Honcho, OpenRouter, Telegram, and historical local LiteLLM/OpenAI-style credentials are revoked or rotated.
- The dashboard build emits a Vite chunk-size warning for the main JS bundle. This is accepted for Phase 5 because the build succeeds, the static smoke test serves HTML successfully, and bundle splitting is post-closure polish unless Phase 6 chooses to gate on bundle size.
- `pip-audit` skips the editable local `justai` package because it is not published on PyPI. This is expected and accepted.

## Recommendation

Proceed to Phase 6 closure only after Justin confirms the historical credentials listed above have been revoked or rotated. No code, test, lint, type, install, dependency-audit, license, dashboard-build, smoke-test, or 3-repo-consistency blocker remains in the current HEAD.
