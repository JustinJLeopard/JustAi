# JustAi Testing Guide

## Running Tests

```bash
cd ~/projects/JustAi

.venv/bin/pytest -q
.venv/bin/ruff check justai tests
.venv/bin/mypy justai
```

## Test Scope

The current suite covers the control plane:

- intent classification
- scope planning
- plan review
- checkpoints
- local dispatch/error handling
- trajectory, ledger, memory, and tracing helpers
- CLI and script wrappers
- dashboard/API support
- docs contract checks

## Dashboard CI

The dashboard is a separate npm project with its own suite. Run it locally with:

```bash
cd dashboard

npm ci
npm run build
npm test
```

`.github/workflows/dashboard-ci.yml` runs those same three commands on every
pull request, and on pushes to `main` and `demo-build`.

### Node version

The Node major is declared **once**, in `dashboard/package.json`:

```json
"engines": {
  "node": "24.x"
}
```

Both consumers read that one field:

| Consumer | How it reads it |
| --- | --- |
| Vercel, at deploy time | reads `engines.node` from `dashboard/package.json` |
| `actions/setup-node`, in CI | `node-version-file: dashboard/package.json` in `.github/workflows/dashboard-ci.yml` |

To change the Node major, edit `engines.node` and nothing else. (`npm` mirrors
`engines` into the root entry of `package-lock.json`; regenerate it with
`npm install --package-lock-only` so `npm ci` stays happy.)

setup-node resolves a `package.json` given to `node-version-file` in a
documented order — `volta.node`, then `devEngines.runtime`, then
`engines.node`, then whatever `volta.extends` points at. This project sets only
`engines.node`, so that is the field that wins. Note the precedence between the
two *inputs*: if a workflow sets `node-version` **and** `node-version-file`,
setup-node uses `node-version` and ignores the file, warning but not failing.
That is why the workflow sets no `node-version` — a literal there would
silently win and let the two declarations drift apart again.

`24.x` is a major rather than an exact patch because [Vercel offers only major
versions](https://vercel.com/docs/functions/runtimes/node-js/node-js-versions)
and rolls out minor/patch updates itself. A deploy always runs the latest
`24.x`, so pinning one patch would test a toolchain the deploy never promises.
CI resolving `24.x` to a newer patch than the last local run is expected, not
drift.

### What this CI does and does not prove

It proves that, on a clean checkout with a Linux runner and Node 24.x:

- `npm ci` succeeds — so `package.json` and `package-lock.json` are in sync, and
  the install is exactly what the lockfile pins
- `npm run build` succeeds — `tsc` typechecks and `vite build` produces `dist/`
- `npm test` passes — the whole `dashboard/` vitest suite runs green

It does not prove:

- **that the check is enforced.** The workflow reports a status; it does not
  make that status required. Requiring it is a repository ruleset change, made
  outside this repo's files.
- **that the deployed demo is green.** Vercel builds from the `demo-build`
  branch. Changes on `main` — including this workflow and the `npm ci` install
  command — reach production only via a separate backport to `demo-build`.
- **that the Vercel build itself passes.** CI runs `npm ci` on a GitHub runner;
  it does not invoke Vercel. The two are aligned by declaring the same Node
  major and the same install command, not by CI executing the deploy.
- **anything about the Python control plane.** That suite is separate and is not
  run by this workflow.

## Design Principles

All tests run offline. External calls are mocked at the boundary: HTTP clients, subprocess calls, and optional observability clients.

Every behavior change should include a focused regression test when it affects public CLI behavior, orchestration decisions, docs contracts, or run accounting.
