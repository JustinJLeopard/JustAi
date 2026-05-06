# Security

## Reporting Vulnerabilities

Please report security issues privately by email:

security@justinleopard.com

Include the affected commit, file path, reproduction steps, and any evidence needed to validate impact. Please do not open a public issue for suspected secrets, account access, or exploitable behavior until the report has been reviewed.

## Historical Secret Disclosure

This repository contains historical commits with credentials that were committed before the current public-release cleanup. Those credentials are not present in the current tree.

The following historical credential classes are explicitly allowlisted for repository-history review:

| Credential class | Historical location | Approximate range | Current status |
| --- | --- | --- | --- |
| Hosted memory/API service key | `LocalManus/memory/seed_identity.py`, `LocalManus/scripts/setup_env.sh`, `LocalManus/scripts/setup_manuslocal.sh` | Initial snapshot `92a6e26f5ee096e11c41a91603d354ae08749e47` through the cleanup/ratification lineage ending before current `main` | Rotated/revoked; inert |
| Model-router API key | `LocalManus/scripts/setup_manuslocal.sh` | Initial snapshot `92a6e26f5ee096e11c41a91603d354ae08749e47` through the cleanup/ratification lineage ending before current `main` | Rotated/revoked; inert |
| Messaging bot token | `LocalManus/scripts/setup_manuslocal.sh` | Initial snapshot `92a6e26f5ee096e11c41a91603d354ae08749e47` through the cleanup/ratification lineage ending before current `main` | Revoked or otherwise confirmed non-production and financially inert |
| Local model-proxy style API key | `LocalManus/scripts/setup_manuslocal.sh` | Initial snapshot `92a6e26f5ee096e11c41a91603d354ae08749e47` through the cleanup/ratification lineage ending before current `main` | Rotated/revoked; inert |

All credentials listed above have been reviewed during the public-release process and confirmed rotated, revoked, or otherwise inert before the repository was made public. New findings in the current tree should not be treated as covered by this historical allowlist.

## Current Tree Expectations

The current tree is expected to remain free of live credentials. Use `.env.example` for configuration examples and keep real secrets in local environment variables or deployment secret stores.
