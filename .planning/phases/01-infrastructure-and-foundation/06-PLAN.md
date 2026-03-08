---
phase: 01-infrastructure-and-foundation
plan: 06
type: execute
wave: 3
depends_on:
  - "01-02"
  - "01-03"
  - "01-04"
  - "01-05"
files_modified:
  - railway.toml
  - .env.example
autonomous: false
requirements:
  - INFRA-01
  - INFRA-02
  - INFRA-03
  - INFRA-04
  - INFRA-05
user_setup:
  - service: railway
    why: "Production deployment platform"
    env_vars:
      - name: TELEGRAM_BOT_TOKEN
        source: "Telegram BotFather (@BotFather) -> /newbot or existing bot -> API Token"
      - name: DATABASE_URL
        source: "Railway Dashboard -> Your service -> Variables -> Add Reference -> ${{Postgres.DATABASE_URL}}"
      - name: WEBHOOK_URL
        source: "Railway Dashboard -> Your service -> Settings -> Networking -> Public URL (e.g. https://freight-tms-production.up.railway.app)"
      - name: JWT_SECRET_KEY
        source: "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
      - name: ADMIN_USERNAME
        source: "Choose your dispatcher login username"
      - name: ADMIN_PASSWORD_HASH
        source: "Generate with: python -c \"from pwdlib import PasswordHash; print(PasswordHash.recommended().hash('yourpassword'))\""
      - name: R2_ACCOUNT_ID
        source: "Cloudflare Dashboard -> R2 -> Overview -> Account ID"
      - name: R2_ACCESS_KEY_ID
        source: "Cloudflare Dashboard -> R2 -> Manage R2 API Tokens -> your token"
      - name: R2_SECRET_ACCESS_KEY
        source: "Same R2 API token page"
      - name: R2_BUCKET_NAME
        source: "The name of your Cloudflare R2 bucket (e.g. freight-tms-photos)"
    dashboard_config:
      - task: "Add PostgreSQL addon"
        location: "Railway Dashboard -> your project -> Add Service -> Database -> PostgreSQL"
      - task: "Add Railway Volume for bot persistence"
        location: "Railway Dashboard -> your service -> Storage -> Add Volume -> Mount Path: /data"
      - task: "Set WEBHOOK_URL after first deploy"
        location: "Railway Dashboard -> your service -> Settings -> Networking -> copy the Public URL, then add as WEBHOOK_URL env var -> Redeploy"

must_haves:
  truths:
    - "railway.toml exists with preDeployCommand running alembic upgrade head"
    - "railway.toml startCommand runs uvicorn on $PORT"
    - "Railway service has all required env vars set"
    - "First Railway deploy completes: Alembic pre-deploy succeeds, app starts, /telegram webhook active"
    - "Driver can complete /start registration and record appears in PostgreSQL"
    - "Web panel /panel/drivers is accessible and requires login"
    - "Railway redeploy preserves driver in-progress conversation (FSM state in Volume)"
  artifacts:
    - path: "railway.toml"
      provides: "Railway deployment configuration with preDeployCommand and startCommand"
      contains: "preDeployCommand"
    - path: ".env.example"
      provides: "Template of all required environment variables"
      contains: "WEBHOOK_URL"
  key_links:
    - from: "railway.toml preDeployCommand"
      to: "alembic upgrade head"
      via: "Railway pre-deploy container (separate from runtime, no Volume mount)"
      pattern: "alembic.*upgrade.*head"
    - from: "railway.toml startCommand"
      to: "uvicorn src.main:app"
      via: "$PORT env var (Railway sets this automatically)"
      pattern: "uvicorn.*PORT"
---

<objective>
Create railway.toml with pre-deploy Alembic hook and uvicorn start command, create .env.example for all required env vars, and guide through the Railway deployment with a structured smoke test checklist.

Purpose: Plans 01-05 built all the code. This plan ships it to Railway and verifies all 5 phase success criteria are met in production.
Output: railway.toml, .env.example, deployed Railway service passing smoke tests.
</objective>

<execution_context>
@/Users/osmagulov/.claude/get-shit-done/workflows/execute-plan.md
@/Users/osmagulov/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/01-infrastructure-and-foundation/01-RESEARCH.md
@.planning/phases/01-infrastructure-and-foundation/01-01-SUMMARY.md
@.planning/phases/01-infrastructure-and-foundation/01-02-SUMMARY.md
@.planning/phases/01-infrastructure-and-foundation/01-03-SUMMARY.md
@.planning/phases/01-infrastructure-and-foundation/01-04-SUMMARY.md
@.planning/phases/01-infrastructure-and-foundation/01-05-SUMMARY.md
@railway.toml
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create railway.toml and .env.example</name>
  <files>railway.toml, .env.example</files>
  <action>
  Create railway.toml at the project root:
  ```toml
  [build]
  builder = "nixpacks"

  [deploy]
  preDeployCommand = ["alembic", "upgrade", "head"]
  startCommand = "uvicorn src.main:app --host 0.0.0.0 --port $PORT"
  healthcheckPath = "/"
  healthcheckTimeout = 100
  restartPolicyType = "on-failure"
  restartPolicyMaxRetries = 3
  ```

  Notes on this configuration:
  - `preDeployCommand` array format (not string) is confirmed as Railway's supported syntax
  - `alembic upgrade head` runs in a separate container — no Railway Volume mounted, only DATABASE_URL env var needed
  - `$PORT` is set by Railway automatically; must not hardcode a port number
  - `healthcheckPath = "/"` uses the GET / endpoint from src/main.py that returns {"status": "ok"}
  - `nixpacks` builder auto-detects Python from requirements.txt and creates virtualenv

  Create .env.example at the project root:
  ```
  # Telegram Bot
  TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather

  # Database (Railway provides this automatically as postgresql://...)
  # Do NOT change the format — async_database_url property handles the postgresql+asyncpg:// conversion
  DATABASE_URL=postgresql://user:password@host:5432/dbname

  # Webhook (Set to your Railway public URL after first deploy)
  WEBHOOK_URL=https://your-service.up.railway.app

  # Cloudflare R2 Storage
  R2_ACCOUNT_ID=your_cloudflare_account_id
  R2_ACCESS_KEY_ID=your_r2_token_key_id
  R2_SECRET_ACCESS_KEY=your_r2_token_secret
  R2_BUCKET_NAME=freight-tms-photos

  # JWT Auth (generate with: python -c "import secrets; print(secrets.token_hex(32))")
  JWT_SECRET_KEY=replace_with_32_random_bytes_hex

  # Admin credentials for web panel
  # Generate hash with: python -c "from pwdlib import PasswordHash; print(PasswordHash.recommended().hash('yourpassword'))"
  ADMIN_USERNAME=dispatcher
  ADMIN_PASSWORD_HASH=your_bcrypt_hash_here
  ```

  Also verify that `alembic/env.py` uses `settings.DATABASE_URL` (not `settings.async_database_url`) for the migration connection. Alembic uses a synchronous psycopg2-style URL during pre-deploy if using synchronous migration runner, or asyncpg if the existing env.py is configured for async. Read alembic/env.py and confirm:
  - If env.py calls `get_url()` which returns `settings.DATABASE_URL` → Railway provides `postgresql://` format → works with psycopg2 sync driver if installed, or may need adjustment
  - If env.py already uses async pattern (run_async_migrations) → ensure `settings.async_database_url` is used for `create_async_engine` in env.py

  Read alembic/env.py and update it if needed: replace any `settings.DATABASE_URL` call with `settings.async_database_url` in the `create_async_engine(...)` call. The pre-deploy container needs DATABASE_URL set but the `postgresql+asyncpg://` scheme is what asyncpg engine needs.

  Add `psycopg2-binary>=2.9.0` to requirements.txt only if alembic/env.py uses synchronous (non-async) migration runner. If env.py already uses async runner with asyncpg, skip this — asyncpg is already in requirements.txt.
  </action>
  <verify>
  Run: `cat railway.toml` — shows preDeployCommand with alembic upgrade head and startCommand with uvicorn $PORT.
  Run: `cat .env.example` — shows all 10 required env var keys.
  Run: `python -c "import toml; d = toml.load('railway.toml'); print(d['deploy']['preDeployCommand'])"` — OR just `grep preDeployCommand railway.toml` — matches.
  Run: `grep "WEBHOOK_URL\|R2_ACCOUNT_ID\|JWT_SECRET_KEY\|ADMIN_PASSWORD_HASH" .env.example | wc -l` — prints 4 (all present).
  </verify>
  <done>railway.toml exists with preDeployCommand = ["alembic", "upgrade", "head"] and startCommand using $PORT. .env.example lists all 10 env vars with comments. alembic/env.py uses async_database_url for engine creation.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Checkpoint: Smoke test Phase 1 on Railway production</name>
  <action>
  Built: PostgreSQL schema with driver-vehicle FK, FastAPI+PTB webhook in one process, FSM persistence via Railway Volume + PicklePersistence, Cloudflare R2 photo upload, JWT-authenticated web panel with drivers list and vehicle edit. railway.toml configures Alembic pre-deploy hook and uvicorn start.

  Pre-deploy checklist (complete before first Railway deploy):
  1. Railway: Add PostgreSQL addon (Railway Dashboard -> Add Service -> Database -> PostgreSQL)
  2. Railway: Set env vars: TELEGRAM_BOT_TOKEN, DATABASE_URL=${{Postgres.DATABASE_URL}}, JWT_SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD_HASH, R2_* (if R2 ready)
  3. Leave WEBHOOK_URL empty for first deploy
  4. Git commit all Phase 1 code and push to Railway-connected branch
  </action>
  <verify>
  Smoke test after first Railway deploy:

  Step 1 — Alembic pre-deploy: Railway deploy logs show "alembic upgrade head" before app start. No error = Alembic ran against PostgreSQL.

  Step 2 — App startup: GET https://your-service.up.railway.app/ returns {"status": "ok", "message": "Freight TMS API is running"}

  Step 3 — Set WEBHOOK_URL and redeploy: Add WEBHOOK_URL to Railway env vars, redeploy. Logs show "Webhook set to .../telegram"

  Step 4 — Driver registration: Send /start in Telegram, complete registration with a vehicle plate. Query PostgreSQL: SELECT id, vehicle_id FROM drivers; — vehicle_id is NOT null.

  Step 5 — FSM persistence: Start /start, stop mid-flow. Trigger Railway redeploy. Resume — bot continues from paused step (not from beginning).

  Step 6 — Web panel: GET /panel/drivers → redirects to /panel/login. Login → shows drivers table. Vehicle edit form saves make/model/fuel_norm.

  Step 7 — R2 photo (if configured): Submit expense with photo. SELECT photo_r2_url FROM expenses ORDER BY id DESC LIMIT 1; shows R2 URL. URL loads photo in browser.
  </verify>
  <done>Human confirms all 5 Phase 1 success criteria pass on Railway. Type "approved" with notes on which criteria passed.</done>
</task>

</tasks>

<verification>
Final phase verification — all 5 success criteria confirmed by human smoke test:
1. Driver /start → registration → driver record in PostgreSQL with vehicle_id FK set
2. Driver links truck → dispatcher sees driver+vehicle pair in /panel/drivers
3. Receipt photo stored in R2 with retrievable URL (or noted as pending if R2 not configured yet)
4. Railway redeploy → mid-conversation bot state preserved (FSM persistence confirmed)
5. /panel/drivers requires login, unauthenticated → redirect to /panel/login
</verification>

<success_criteria>
- railway.toml created with preDeployCommand=["alembic","upgrade","head"] and startCommand with $PORT
- .env.example lists all 10 required env vars
- Railway deploy completes without error (Alembic pre-deploy + app start)
- All 5 Phase 1 success criteria verified by human smoke test:
  1. Driver registration creates PostgreSQL record with vehicle_id FK set
  2. Dispatcher sees driver+vehicle pair in web panel
  3. Receipt photo retrievable from R2 URL
  4. FSM state survives Railway redeploy
  5. /panel/drivers requires authentication
- Human checkpoint passed
</success_criteria>

<output>
After completion, create `.planning/phases/01-infrastructure-and-foundation/01-06-SUMMARY.md`
</output>
