# JustAi Testing Guide

## Running Tests

```bash
cd ~/projects/JustAi

.venv/bin/pytest -q
.venv/bin/ruff check justai tests
.venv/bin/mypy justai
```

## Python CI

`.github/workflows/python-ci.yml` runs the package's own suite on every pull
request, and on pushes to `main` and `demo-build`, against Python 3.12 (the
minimum `pyproject.toml` promises) and 3.13:

```bash
ruff check justai tests
pytest -q tests/test_gate_*.py     # gate and concurrency suite, named explicitly
pytest -q                          # the whole suite
```

It checks out `github.event.pull_request.head.sha`. A pull request's default
checkout is `refs/pull/N/merge` — a commit GitHub synthesises by merging the
head into the current base — so a green check against it names a revision that
exists in nobody's branch and changes whenever the base moves. Pinning the head
SHA makes the result belong to one revision.

The gate suite is named separately from the full run because it is the part
that drives real interpreters against one run's approval gates: it fails first,
and it fails by name, instead of being one dot in a 550-test run.

### What this CI does and does not prove

It proves that, on a clean checkout with a Linux runner and CPython 3.12/3.13,
`ruff check` is clean and the whole suite passes offline.

It does not prove:

- **that the check is enforced.** The workflow reports a status; making it
  required is a repository ruleset change, outside this repo's files.
- **that any execution backend works.** No backend is integrated; the suite
  covers the control plane's own decisions, including the ones that fail
  closed because there is nothing to dispatch to.

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
- **anything about the Python control plane.** That suite is separate, and is
  run by `python-ci.yml` above rather than by this workflow.

## Design Principles

All tests run offline. External calls are mocked at the boundary: HTTP clients, subprocess calls, and optional observability clients.

Every behavior change should include a focused regression test when it affects public CLI behavior, orchestration decisions, docs contracts, or run accounting.
