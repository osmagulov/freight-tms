# Agent Instructions — Freight TMS

## Role

You are an autonomous engineering agent working on Freight TMS — a fleet management system for 100+ truck drivers on international routes (CN↔KZ, KZ↔RU, Central Asia, Turkey, Georgia).

## How to Work

- Work autonomously without asking for permission on coding tasks
- Use GSD workflow for planning and execution (`/gsd:progress`, `/gsd:execute-phase N`)
- Commit changes atomically after each completed task
- Fix bugs you find along the way — don't leave broken code
- Never stop mid-task to ask "should I continue?" — just continue

## Architecture (read CLAUDE.md for full details)

Single process: FastAPI + python-telegram-bot webhook in one uvicorn process.

```
src/main.py              — lifespan, /telegram endpoint, GET /
src/core/config.py       — Settings with async_database_url property
src/db/                  — SQLAlchemy models, CRUD, async engine
src/bot/bot_app.py       — register_handlers(), all PTB ConversationHandlers
src/services/r2.py       — Cloudflare R2 upload (non-blocking via run_in_executor)
src/web/                 — JWT auth, Jinja2 panel routes, HTML templates
antigravity_modules/     — Bot conversation flows (trip, expense, location, closing)
alembic/versions/        — DB migrations
```

## Deployed Environment

- **Railway URL**: https://freight-tms-api-production.up.railway.app
- **Telegram Webhook**: https://freight-tms-api-production.up.railway.app/telegram
- **Web Panel**: https://freight-tms-api-production.up.railway.app/panel/drivers
- **Login**: username `dispatcher`, password `dispatcher123`
- **Project**: `freight-tms` on Railway (project ID: aaf49726-602e-4903-a3d1-821da3f352ef)

## Non-Negotiable Rules

1. **No polling** — PTB webhook only, `.updater(None)`
2. **async_database_url** — always, never raw DATABASE_URL for engine
3. **Alembic in preDeployCommand** — never in FastAPI startup
4. **All ConversationHandlers** need `name=` + `persistent=True`
5. **BcryptHasher explicitly** — `PasswordHash((BcryptHasher(),))` not `.recommended()`
6. **run_in_executor** for all boto3 calls
7. **railway.toml**: `preDeployCommand` as string, `restartPolicyType` as `"ON_FAILURE"` (uppercase)

## Common Fixes Reference

| Problem | Fix |
|---------|-----|
| `HasherNotAvailable: argon2` | Use `PasswordHash((BcryptHasher(),))` not `.recommended()` |
| `preDeployCommand: Array must contain at most 1 element` | Change array `["alembic","upgrade","head"]` to string `"alembic upgrade head"` |
| `restartPolicyType: Invalid input` | Must be `"ON_FAILURE"` (uppercase) in railway.toml |
| Healthcheck fails | Check startup crash — test with `python -c "from src.main import app"` locally |
| Bot loses conversation state on redeploy | All ConversationHandlers need `persistent=True` |

## Development Commands

```bash
# Check Railway deploy status
railway deployment list

# View live logs
railway logs

# Deploy
railway up --detach

# Run migrations locally (needs .env)
alembic upgrade head

# Test app imports
DATABASE_URL="postgresql://x:x@localhost/x" TELEGRAM_BOT_TOKEN="x" \
JWT_SECRET_KEY="x"*32 ADMIN_USERNAME="x" ADMIN_PASSWORD_HASH="x" \
python -c "from src.main import app; print('OK')"
```

## GSD Project State

- Milestone: v1.0 MVP
- Phase 1 (Infrastructure): COMPLETE ✓
- Phase 2 (Expense Control): Next
- Run `/gsd:progress` to see current state and next action
