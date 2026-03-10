# Sandbox / Production Isolation Strategy

## Goal

Eliminate accidental cross-deploys between sandbox and production.

## Isolation Matrix

| Layer | Production | Sandbox |
|---|---|---|
| Project dir | `/opt/hydra_bot` | `/opt/hydra_bot_sandbox` |
| Marker file | `.deploy-target: TARGET_ENV=production` | `.deploy-target: TARGET_ENV=sandbox` |
| `.env` | `APP_ENV=production`, `APP_INSTANCE=hydra-prod` | `APP_ENV=sandbox`, `APP_INSTANCE=hydra-sandbox` |
| Domain | `https://bot.neurounit.fun` | `https://bot-sandbox.neurounit.fun` |
| Gunicorn bind | `127.0.0.1:8443` | `127.0.0.1:18443` |
| systemd | `hydra-bot`, `hydra-worker` | `hydra-bot-sandbox`, `hydra-worker-sandbox` |
| Redis DB | `0` | `1` |
| PostgreSQL DB | `hydra_bot` | `hydra_bot_sandbox` |
| Smoke script | `deploy/production_smoke.sh` | `deploy/sandbox_smoke.sh` |

## Mandatory Deploy Flow

1. Run `deploy/guarded_deploy.sh --env sandbox --project-dir /opt/hydra_bot_sandbox`
2. Validate sandbox behavior and integrations.
3. Run `deploy/guarded_deploy.sh --env production --project-dir /opt/hydra_bot --strict-prod`

`guarded_deploy.sh` blocks deploy on:
- APP_ENV mismatch
- `.deploy-target` mismatch
- APP_INSTANCE mismatch
- production host used in sandbox
- sandbox host used in production

## Additional Rule

Never copy `.env` from production into sandbox or vice versa.
Always generate independent secrets for each environment.
