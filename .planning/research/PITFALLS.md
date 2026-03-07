# Pitfalls: Freight TMS — Telegram Bot + FastAPI + Fleet Dashboard

**Domain:** Freight Transportation Management System — 100+ truck drivers, international routes
**Researched:** 2026-03-08
**Overall confidence:** HIGH for bot/deployment pitfalls (verified via official docs + GitHub issues), MEDIUM for fleet/UX pitfalls (multiple sources, domain reasoning)

---

## Critical Pitfalls

Mistakes that cause rewrites, data loss, or total system failure. Address these in Phase 1 before anything else.

| Pitfall | Risk Level | Prevention | Phase |
|---------|------------|-----------|-------|
| In-memory FSM state — lost on restart | CRITICAL | Use PicklePersistence (Phase 1 acceptable) or PostgreSQL-backed persistence (preferred). Never rely on ConversationHandler default in-memory dict for production | Phase 1 |
| Polling + Webhook running simultaneously | CRITICAL | Pick one mode at deploy time. Webhook for production (Railway has HTTPS). Delete webhook before switching to polling. Use `drop_pending_updates=True` on startup | Phase 1 |
| Multiple bot instances on same token | CRITICAL | Railway redeploys briefly run two instances in parallel. Use webhooks (not polling) — Telegram distributes webhook calls without the "Conflict: terminated by other getUpdates" error that polling causes | Phase 1 |
| Expense data loss when driver abandons mid-flow | CRITICAL | Store partial form data to DB after every step, not only on completion. Allow driver to resume with `/continue` command. Auto-save to `conversation_data` with persistent storage | Phase 1 |
| Telegram photo stored by file_id only — expires | HIGH | Download and store photo bytes to your own object storage (S3-compatible / Railway volume). file_id from Telegram becomes invalid after time or on bot token change | Phase 1 |
| Database migration breaks production on redeploy | HIGH | Run Alembic `upgrade head` as a separate pre-deploy step, not inside application startup code. Use expand-contract pattern for non-nullable column changes | Phase 1 |
| Fuel consumption false positives creating alert noise | HIGH | Threshold must account for route type (mountain vs flat), weather, and load weight. Default 10% over norm will fire constantly on steep international routes. Start with 20-25% threshold; tune down after data accumulates | Phase 2 |
| PicklePersistence breaks between PTB version upgrades | MEDIUM | In production, use database persistence (custom BasePersistence with PostgreSQL) rather than PicklePersistence. Pickle files are not forward-compatible across major PTB versions — deserialization fails silently | Phase 1 |
| Railway volume blocks horizontal scaling | MEDIUM | Do not store bot state in Railway volume. Use PostgreSQL (Railway managed DB) as the single source of truth. Volume is only acceptable for temporary file staging before upload to external storage | Phase 1 |

---

## UX Pitfalls — Drivers on Phones

These cause driver abandonment and rejection of the bot. Non-technical drivers using phones while tired, on bad roads, under time pressure. Every friction point multiplies dropout probability.

### Pitfall 1: Too Many Steps Before First Value
**What goes wrong:** Driver opens bot for first time, faces 8 questions before anything useful happens (registration, truck selection, route, shift start, etc.). They close the app and use WhatsApp.

**Prevention:**
- Maximum 3 steps for first-time registration (name, truck number, phone — everything else optional)
- `/start` immediately shows what the bot can do with one-tap buttons
- For expense submission: fuel dialog must be completable in under 60 seconds

**Phase:** Phase 1 — bake into initial conversation design, hard to retrofit

---

### Pitfall 2: No Recovery from Interruption
**What goes wrong:** Driver starts submitting fuel expense. Phone rings. They answer, come back, bot is in wrong state. They type something, bot responds with error or loops. They give up.

**Prevention:**
- Every state must display current progress at top ("Step 2 of 4 — enter liters")
- `/cancel` reachable from any state with confirmation
- `/continue` resumes last incomplete submission
- Set `conversation_timeout` to at least 30 minutes (drivers stop at checkpoints, fuel stations)
- On timeout, save partial data and send: "Your expense was saved as draft. /continue to finish."
- `allow_reentry=True` so `/fuel` from any state resets cleanly rather than silently failing

**Warning:** `conversation_timeout` with nested ConversationHandlers is unsupported in python-telegram-bot. Flatten conversation structure — avoid nesting.

**Phase:** Phase 1 — core FSM design

---

### Pitfall 3: Buttons Not Showing on Restart
**What goes wrong:** Bot sends inline keyboard. Driver doesn't reply immediately. Bot restarts (Railway redeploy). Old inline keyboard callbacks are now orphaned — pressing them causes "query is too old" error or silent failure. Driver sees nothing happen.

**Prevention:**
- Always handle `CallbackQuery` errors with `answer_callback_query(show_alert=False)` fallback
- For critical actions, provide both inline buttons AND command alternatives (`/approve` not just a button)
- On any `BadRequest` for expired callback, send fresh message with new keyboard

**Phase:** Phase 1

---

### Pitfall 4: Photo Upload Silently Fails on Bad Network
**What goes wrong:** Driver at a border checkpoint with weak 2G signal. Takes photo of receipt. Upload appears to succeed on phone. Backend never receives it (timeout). Bot says nothing. Expense is submitted without photo — violating the "photo required" rule — or rejected without explanation.

**Prevention:**
- Set `read_timeout=30, write_timeout=30, connect_timeout=10` on bot initialization (default is 5 seconds — too low for photo uploads on mobile)
- On `TimedOut` exception: retry once with exponential backoff, then ask driver to try again with friendly message
- Never silently drop a failed photo upload — always notify driver
- Accept photo OR file (sendDocument) — some drivers send photos as files to avoid Telegram compression
- Do not make photo mandatory in MVP beta. Mark as "optional but encouraged" until upload reliability is confirmed

**Phase:** Phase 1

---

### Pitfall 5: Language and Instruction Overload
**What goes wrong:** Bot messages are long paragraphs in formal language. Driver on phone reads first two words and presses any button. Skips steps. Submits wrong data.

**Prevention:**
- Each bot message: maximum 2 lines of instruction
- Use bold for the question, plain text for context
- Example: "**Сколько литров залили?** (введите число, например: 120)"
- Avoid explaining why in the bot — save that for documentation/training
- All buttons in Russian, all confirmations in Russian
- Error messages must be friendly: "Введите только цифры, например: 450" not "Invalid input"

**Phase:** Phase 1 — build Russian UX copy into message templates from the start

---

### Pitfall 6: Duplicate Expense Submission
**What goes wrong:** Driver submits expense. Network is slow. Presses submit again (or bot sends "please confirm" and driver presses twice). Two identical expenses created in DB.

**Prevention:**
- Idempotency key on expense submission: hash of (driver_id, expense_type, amount, timestamp_floor_to_minute)
- At DB level: unique constraint on idempotency key
- Show "Expense #4821 submitted" with ID — driver can verify it was recorded once
- Disable submit button (inline keyboard replace with "Processing...") immediately on first press

**Phase:** Phase 1

---

### Pitfall 7: Odometer Sequence Errors From Phone Typos
**What goes wrong:** Driver types odometer reading with typo (12500 becomes 125000 or 1250). Bot accepts it. Fuel consumption calculation now completely wrong for this trip and all future calculations that depend on odometer delta.

**Prevention:**
- Server-side validation: new odometer must be > last odometer for this truck, and < last odometer + 5000 (max plausible km per fill-up)
- If odometer fails plausibility check: ask driver to confirm with explicit warning
- Store last known odometer per truck in DB — query before accepting new value
- Allow dispatcher to manually correct odometer readings in dashboard

**Phase:** Phase 1

---

## Technical Pitfalls

### Pitfall 1: ConversationHandler Race Condition with Concurrent Users
**What goes wrong:** Two drivers message bot simultaneously. `block=False` (concurrent updates enabled) means handlers can interleave. If any handler modifies shared state (global dict, mutable default argument), data from one user bleeds into another.

**Prevention:**
- Never use global mutable state in handlers — all state via `context.user_data` or database
- python-telegram-bot v20+ is asyncio-based but not thread-safe by design
- If using `concurrent_updates=True` on Application: each update must be fully self-contained
- Database writes must use proper async context managers (`async with session:`) to prevent connection pool exhaustion
- Default behavior (sequential updates per user, concurrent across users) is safe — do not enable concurrent updates unless you understand the implications

**Confidence:** HIGH — documented in python-telegram-bot concurrency wiki

**Phase:** Phase 1

---

### Pitfall 2: Webhook Secret Token Not Validated
**What goes wrong:** FastAPI webhook endpoint accepts any POST request. Attacker discovers endpoint URL (token in path is not enough), sends fake updates. Bot processes forged commands.

**Prevention:**
- Set `secret_token` parameter when calling `setWebhook`
- Validate `X-Telegram-Bot-Api-Secret-Token` header in FastAPI route
- Return 403 immediately if token missing or wrong — do not process update
- Use `fastapi-security-telegram-webhook` package or implement manually (10 lines)

**Confidence:** HIGH — official Telegram Bot API docs, Bot API 6.1+

**Phase:** Phase 1

---

### Pitfall 3: FastAPI + python-telegram-bot Event Loop Conflict
**What goes wrong:** FastAPI uses uvicorn's asyncio event loop. python-telegram-bot v20+ creates its own event loop via `Application.run_webhook()`. Running both naively results in "there is no current event loop" errors or deadlocks.

**Prevention:**
- Do NOT call `application.run_webhook()` — this starts its own loop and blocks
- Instead: initialize Application without running it, pass updates manually from FastAPI route
- Pattern:
  ```python
  # startup event
  await application.initialize()
  await application.start()

  # webhook route
  @app.post("/webhook")
  async def webhook(request: Request):
      update = Update.de_json(await request.json(), application.bot)
      await application.process_update(update)
      return {"ok": True}

  # shutdown event
  await application.stop()
  await application.shutdown()
  ```
- Use FastAPI lifespan context manager for bot startup/shutdown

**Confidence:** HIGH — python-telegram-bot v20+ documentation and community patterns

**Phase:** Phase 1

---

### Pitfall 4: Alembic Auto-Migration on App Startup
**What goes wrong:** Developer adds `alembic upgrade head` inside FastAPI startup event. On Railway redeploy, two instances start simultaneously (briefly). Both run migrations concurrently. Migration table gets corrupted. Production database in broken state.

**Prevention:**
- Run Alembic migration as a separate Railway service or pre-deploy command, never inside application code
- Railway `startCommand` for migration: `alembic upgrade head && uvicorn main:app ...`
- Use advisory locks in Alembic env.py to prevent concurrent migration runs
- Test migration rollback path before every deploy: `alembic downgrade -1` must work

**Confidence:** HIGH — Alembic official docs + production incident reports

**Phase:** Phase 1

---

### Pitfall 5: N+1 Query on Dashboard — 100 Trucks Loading
**What goes wrong:** Dashboard loads fleet list. For each truck (100+), ORM fires separate query to get driver name, last expense, last location. Page takes 8 seconds to load. Dispatchers stop using it.

**Prevention:**
- Always eager-load relationships in dashboard queries: `options(joinedload(Truck.driver), joinedload(Truck.last_expense))`
- Dashboard queries must have explicit `LIMIT` clauses
- Add database indexes on: `driver_id`, `truck_id`, `created_at`, `status` from Day 1 — cheaper to add early than retrofit
- Use SQLAlchemy `selectinload` for collections, `joinedload` for single relations

**Confidence:** HIGH — standard SQLAlchemy pattern

**Phase:** Phase 1 (indexes), Phase 2 (dashboard load optimization)

---

### Pitfall 6: Fuel Anomaly Alert Noise — False Positive Storm
**What goes wrong:** System calculates fuel consumption wrong due to: (a) odometer typo, (b) partial fill-up not recorded, (c) fill-up at different fuel station with different fuel grade, (d) mountain route. Director gets 30 alerts per day. Stops reading them. Real fraud goes unnoticed.

**Prevention:**
- Minimum 2 fill-ups required before anomaly detection fires (single data point is not enough)
- Configurable per-truck norm with route type modifier (flat / hilly / mixed)
- Anomaly alert includes context: "Truck 003, Fill-up #4, 120L consumed, norm 95L, route Almaty-Aktau (desert, heat)"
- Alert batching: do not send individual Telegram messages per anomaly — batch daily digest
- Dispatcher must be able to mark anomaly as "reviewed / false positive" from dashboard
- Three-strikes rule: alert only if anomaly appears in 3 consecutive fill-ups

**Confidence:** MEDIUM — domain research + fuel tracking industry patterns

**Phase:** Phase 2 (anomaly detection), Phase 3 (tuning)

---

### Pitfall 7: Telegram file_id Dependency — Photo Receipt Loss
**What goes wrong:** System stores only Telegram `file_id` for receipt photos. Bot token is rotated (security incident, accidental exposure). All file_ids become invalid. Six months of expense photo evidence gone. Disputes cannot be resolved.

**Prevention:**
- On receipt photo received: immediately download bytes via `bot.get_file()` and upload to persistent storage
- S3-compatible storage (AWS S3, MinIO, Backblaze B2) — not Railway volume
- Store both: `telegram_file_id` (for quick display) and `storage_url` (permanent record)
- Background task pattern: `asyncio.create_task(download_and_store(file_id))` so bot responds to driver immediately while upload happens asynchronously
- Set `write_timeout=60` for upload operations — photo uploads to storage can be slow

**Confidence:** HIGH — Telegram Bot API documentation explicitly warns about file_id impermanence

**Phase:** Phase 1

---

### Pitfall 8: Currency Rounding and Float Arithmetic
**What goes wrong:** Expense amounts stored as `FLOAT` in database. KZT amounts (large integers) lose precision. Summation on dashboard shows $0.01 discrepancies that accumulate. Director doesn't trust the numbers.

**Prevention:**
- Store all monetary amounts as `NUMERIC(12,2)` or `INTEGER` (store kopecks/tenge, not rubles/KZT)
- Use Python `Decimal` for all arithmetic, never `float`
- Exchange rates: store as `NUMERIC(10,6)` — six decimal places minimum
- Currency conversion: always store original amount + original currency + rate_used + converted_amount

**Confidence:** HIGH — standard financial software pattern

**Phase:** Phase 1

---

## Railway / Deployment Pitfalls

### Pitfall 1: Cold Start Kills First Webhook Update
**What goes wrong:** Railway container has been idle. Telegram sends an update (webhook). Container starts up (15-22 seconds for Python + uvicorn + SQLAlchemy connection pool). Telegram times out waiting for response (5 second timeout). Telegram retries the update. Container is now warm. Bot processes the update twice. Driver gets duplicate response.

**Prevention:**
- Implement webhook endpoint idempotency: process each `update_id` exactly once (store processed update_ids in Redis or DB)
- Health check endpoint (`/health`) pinged every 60 seconds keeps container warm — configure in `railway.json`:
  ```json
  {
    "deploy": {
      "healthcheckPath": "/health",
      "healthcheckTimeout": 30,
      "restartPolicyType": "ON_FAILURE",
      "restartPolicyMaxRetries": 10
    }
  }
  ```
- Start PostgreSQL connection pool lazily (first request) not eagerly at startup
- Use `drop_pending_updates=True` when setting webhook to discard updates that accumulated during downtime

**Confidence:** HIGH — Railway help station documented, Telegram retry behavior documented

**Phase:** Phase 1

---

### Pitfall 2: Nixpacks Cannot Detect Monorepo Structure
**What goes wrong:** Repository has `bot/`, `api/`, `frontend/` directories. Nixpacks cannot determine entry point. Build fails or wrong service starts.

**Prevention:**
- Add explicit `Procfile` at repo root: `web: uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- OR add `railway.json` with explicit start command
- Separate Railway services for bot and API (recommended) — each service points to same repo but different start commands
- Keep `requirements.txt` at repo root even in monorepo structure

**Confidence:** MEDIUM — Railway help station reports + Nixpacks documentation

**Phase:** Phase 1

---

### Pitfall 3: Volume Attachment Prevents Zero-Downtime Redeploys
**What goes wrong:** Railway volume attached to bot service. On redeploy, Railway must stop old container before starting new one (to prevent two containers mounting same volume). Bot has 10-30 second downtime on every deploy. Users get "bot not responding" during peak times.

**Prevention:**
- Store nothing on Railway volume that must be available during redeploy
- Photos: upload to external storage (S3/B2) immediately on receipt — do not stage on volume
- SQLite: do not use — use Railway managed PostgreSQL
- If volume needed (e.g., for temp file processing): accept the downtime and schedule deploys at 3AM

**Confidence:** HIGH — Railway official documentation on volumes explicitly states this limitation

**Phase:** Phase 1

---

### Pitfall 4: Environment Variable Leakage in Logs
**What goes wrong:** FastAPI startup logs print application settings including `BOT_TOKEN`, `DATABASE_URL` with password. Railway log stream is accessible to all project members. Bot token compromised.

**Prevention:**
- Never log settings objects directly — use `settings.model_dump(exclude={'bot_token', 'database_url'})`
- Pydantic BaseSettings: mask sensitive fields with `SecretStr` type
- Railway environment variables: use Railway's variable reference feature, not hardcoded values
- Rotate tokens periodically — document rotation procedure in ops runbook

**Confidence:** HIGH — security best practice

**Phase:** Phase 1

---

### Pitfall 5: Railway Free / Hobby Plan Limits Cause Production Surprises
**What goes wrong:** Development on Hobby plan ($5/month). Bot is fine with 5 users. At 100 drivers all submitting expenses after a long haul: concurrent requests spike, memory limit hit, container OOM-killed. Bot stops. Expenses lost.

**Prevention:**
- Use `concurrent_updates=False` (default) in python-telegram-bot — sequential update processing per user prevents memory spikes from concurrent photo processing
- Set explicit memory limit awareness: async photo processing should yield frequently to event loop
- Load test before production: simulate 50 concurrent expense submissions
- Plan for Pro plan ($20/month) — it includes priority resources and no cold starts on active services
- PostgreSQL: Railway managed Postgres starts at 1GB RAM — adequate for MVP but monitor

**Confidence:** MEDIUM — Railway pricing docs + general resource planning

**Phase:** Phase 1

---

### Pitfall 6: Webhook URL Trailing Characters / Incorrect $PORT
**What goes wrong:** Railway sets `$PORT` dynamically. Webhook URL constructed with wrong port or trailing semicolon (documented Railway bug). Telegram cannot reach webhook. Bot silently stops receiving updates. No error shown in bot — it just stops responding.

**Prevention:**
- Construct webhook URL using `RAILWAY_PUBLIC_DOMAIN` env var, not `PORT`:
  ```python
  WEBHOOK_URL = f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}/webhook/{BOT_TOKEN}"
  ```
- After deploy: call `bot.get_webhook_info()` and log the response — verify URL is correct
- Add `/webhook-status` admin endpoint that returns `getWebhookInfo` result
- Set up monitoring: external ping to `/health` every 5 minutes, alert if no response

**Confidence:** MEDIUM — Railway help station documented the trailing semicolon bug

**Phase:** Phase 1

---

## What to Test First

Before writing any feature code, validate these assumptions. Failure here means the architecture is broken.

### Test 1: Webhook Round-Trip on Railway (Day 1)
Deploy a minimal FastAPI + python-telegram-bot app to Railway with webhook. Send a `/start` command from real phone. Confirm response arrives within 3 seconds. If this fails, debug before building anything else.

**Why first:** Everything depends on this. A broken webhook setup discovered in Week 3 means rewriting integration.

---

### Test 2: FSM State Survives Bot Restart (Day 1)
Start a conversation. Restart the Railway service. Send next message. Verify bot remembers the state. This validates persistence setup.

**Why early:** FSM without persistence is unusable for drivers who get interrupted mid-flow. Discover the persistence approach that works on Railway before building 10 conversation flows.

---

### Test 3: Photo Upload on Throttled Connection (Week 1)
Use Chrome DevTools network throttling (or real 2G SIM) to simulate slow upload. Submit a receipt photo. Verify: (a) bot does not silently fail, (b) photo is stored in your storage (not just Telegram), (c) timeout errors produce friendly retry message.

**Why early:** Photo receipt is the core differentiator. If it fails silently on bad networks, drivers lose trust in the entire system.

---

### Test 4: 50 Concurrent Expense Submissions (Before Phase 1 Launch)
Write a script that sends 50 simultaneous expense submissions with photos from different user IDs. Measure: response time, error rate, DB connection pool exhaustion, memory usage on Railway.

**Why before launch:** 100+ drivers return from same border crossing at same time. This is a realistic scenario.

---

### Test 5: Odometer Validation Edge Cases (Week 1)
Test these inputs to the odometer field: `0`, negative number, current odometer minus 100, current plus 100000, letters, comma-separated decimal, emoji. All must produce friendly error messages and not crash the conversation state.

**Why early:** Odometer errors silently corrupt fuel consumption calculations for the lifetime of the truck record.

---

### Test 6: Alembic Migration on Live DB with Data (Before Phase 2)
Run the Phase 2 migration script against a copy of production DB with real data. Time it. Verify no table locks > 1 second. Verify rollback works. Verify app still functions during migration (if expand-contract pattern used).

**Why before Phase 2:** Phase 2 adds trip entity and foreign keys to existing expense table. This is the most dangerous schema change.

---

## Phase-Specific Warning Summary

| Phase Topic | Most Likely Pitfall | Mitigation |
|-------------|-------------------|------------|
| FSM conversation design | State loss on restart, driver abandonment mid-flow | Persistent storage + resume flow from Day 1 |
| Photo receipt handling | Silent upload failures on 2G networks | Timeout tuning + retry + own storage (not file_id) |
| FastAPI + PTB integration | Event loop conflict, duplicate updates | Manual update processing pattern, idempotency keys |
| Railway deployment | Cold starts, volume limits, Nixpacks confusion | Healthcheck + webhook mode + external storage |
| Fuel anomaly detection | False positive storm rendering alerts useless | Multi-fill threshold, route modifier, batch alerts |
| Dashboard queries | N+1 queries on 100-truck fleet list | Eager loading + indexes from Day 1 |
| Database migrations | Production downtime on schema changes | Expand-contract + separate migration step |
| Multi-currency | Float arithmetic rounding errors | NUMERIC type + Decimal arithmetic from Day 1 |
| Concurrent users | Race conditions in shared state | No global mutable state, DB as source of truth |

---

## Sources

- [python-telegram-bot Concurrency Wiki](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Concurrency) — HIGH confidence, official
- [python-telegram-bot ConversationHandler Docs v22.5](https://docs.python-telegram-bot.org/en/stable/telegram.ext.conversationhandler.html) — HIGH confidence, official
- [python-telegram-bot Making Your Bot Persistent](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Making-your-bot-persistent) — HIGH confidence, official
- [Handling Network Errors — python-telegram-bot Wiki](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Handling-network-errors) — HIGH confidence, official
- [Telegram Bot API — Errors](https://core.telegram.org/api/errors) — HIGH confidence, official
- [Railway Volumes Reference](https://docs.railway.com/volumes/reference) — HIGH confidence, official
- [Railway PostgreSQL Docs](https://docs.railway.com/databases/postgresql) — HIGH confidence, official
- [Alembic Migrations Without Downtime — Exness Tech Blog](https://medium.com/exness-blog/alembic-migrations-without-downtime-a3507d5da24d) — MEDIUM confidence (verified against official Alembic patterns)
- [Zero-Downtime Upgrades with Alembic and SQLAlchemy](https://that.guru/blog/zero-downtime-upgrades-with-alembic-and-sqlalchemy/) — MEDIUM confidence
- [Building Robust Telegram Bots](https://henrywithu.com/building-robust-telegram-bots/) — MEDIUM confidence (verified core claims against official docs)
- [ConversationHandler Race Condition — GitHub Issue #1175](https://github.com/python-telegram-bot/python-telegram-bot/issues/1175) — HIGH confidence
- [PicklePersistence Backwards Compatibility — GitHub Issue #3379](https://github.com/python-telegram-bot/python-telegram-bot/issues/3379) — HIGH confidence
- [Railway Cold Start Discussion](https://station.railway.com/questions/cold-start-slow-ee224f40) — MEDIUM confidence
- [Telegram Bot Webhook Complete Guide — FreeCodeCamp](https://www.freecodecamp.org/news/how-to-build-and-deploy-python-telegram-bot-v20-webhooks/) — MEDIUM confidence
- [Fixing 429 Errors: Retry Policies for Telegram Bot API](https://telegramhpc.com/news/574/) — MEDIUM confidence
- [5 Steps to Effective Alert Management in Fleet Operations — Pitstop](https://pitstopconnect.com/2024/03/05/5-steps-to-effective-alert-management-workflows-in-fleet-operations/) — MEDIUM confidence
- [Fleet Management Dashboard Design Guide — Hicron](https://hicronsoftware.com/blog/fleet-management-dashboard-design/) — MEDIUM confidence
- Existing fuel bot codebase (ДНЕВНИК.md) — HIGH confidence for proven driver UX patterns
