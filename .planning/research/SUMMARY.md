# Research Summary: Freight TMS MVP

**Project:** Freight TMS — international trucking, 100+ drivers, 200+ trucks
**Domain:** Fleet management / expense control / Telegram-first driver tooling
**Researched:** 2026-03-08
**Confidence:** HIGH (stack and pitfalls) / MEDIUM (features and data model)

## Executive Summary

This is an internal operations tool for a single trucking company, not a SaaS product. Three user types with radically different contexts: drivers on phones in moving trucks (Telegram bot), dispatchers tracking a fleet all day (web dashboard), and a director watching costs and fraud signals (web dashboard). The key insight from research is that the existing fuel bot already proves the core driver UX — the MVP extends it, does not replace it. The product is architecturally simple: one FastAPI process, one PostgreSQL database, one Railway deployment. The bot and web dashboard share the same service layer and database directly. No message queue, no microservices, no mobile app.

The recommended approach is to build in four phases gated by dependency: infrastructure proof-of-concept first (webhook round-trip on Railway), then expense control (the highest pain, lowest complexity, most proven), then trip management (which makes all historical data queryable), then location and documents (independent flows that can be built in parallel). The director dashboard and CSV export round out the MVP. Everything else — background GPS tracking, route benchmarking, driver balance ledger, multi-currency per diem automation — is explicitly deferred.

The top risk is not technical complexity but driver adoption. Drivers are non-technical, on bad roads, on 2G networks, under time pressure. Every extra step in a dialog is a dropout. Every silent failure (photo upload that quietly times out, bot state lost on restart, duplicate expense confirmation) destroys trust. Pitfalls research confirms: FSM persistence, photo storage durability, and webhook idempotency must be solved in Phase 0/1, not retrofitted. The second-highest risk is alert noise from the fuel anomaly detector — a misconfigured threshold on international mountain routes will produce a false-positive storm that causes the director to ignore all alerts, defeating the fraud-detection value proposition.

---

## Key Findings

### Stack Additions

All versions verified via PyPI as of 2026-03-08. Core framework choices are team constraints (FastAPI, python-telegram-bot, PostgreSQL, Railway). The following libraries fill the gaps:

- `python-telegram-bot==22.6` — Telegram bot framework; built-in `ConversationHandler` covers all FSM dialog flows, no external FSM library needed
- `httpx==0.28.1` — async HTTP client for bot-to-API calls (PTB v22 is fully async)
- `sqlalchemy==2.0.48` + `asyncpg==0.31.0` — async ORM + fastest PostgreSQL driver; required pair for FastAPI async
- `alembic==1.18.4` — schema migrations; run as pre-deploy step, never inside app startup
- `pydantic==2.12.5` + `pydantic-settings==2.8.x` — request validation + Railway env var config via `BaseSettings`
- `python-jose[cryptography]==3.5.0` — JWT tokens for dispatcher/director web auth
- `pwdlib[bcrypt]==0.3.0` — password hashing; replaces unmaintained `passlib` (broken in Python 3.11+)
- `jinja2==3.1.6` — server-side HTML templating for web dashboard (no React, no build pipeline)
- `htmx==2.x` (CDN) — inline updates (approve/reject expense rows, map refresh) without a frontend framework
- `leaflet.js==1.x` (CDN) — truck location map using OpenStreetMap tiles; free, no API key
- `boto3==1.42.63` — S3-compatible client for Cloudflare R2 photo storage
- `APScheduler==3.11.2` — in-process async scheduler for hourly fuel anomaly checks; replaces Celery+Redis
- `Pillow>=11.0.0` — compress receipt photos to max 2MB before R2 upload

**Do not add:** Celery+Redis (APScheduler handles it), React/Vue (Jinja2+HTMX sufficient for 5 users), aiogram (team constraint is PTB), passlib (unmaintained), MinIO (use Cloudflare R2).

---

### Feature Table Stakes

**Drivers (Telegram bot):**
- Fuel expense: liters, odometer, photo, station — extends existing bot
- Per diem submission: amount + currency + city + dispatcher approval
- Fine reporting: photo + amount + reason
- Other expenses: toll, repair, border fee with category select
- Trip assignment visibility and confirmation via bot command
- On-demand location sharing (Telegram native geolocation)
- Shift start / shift end (anchors expenses to a trip)
- My expenses summary: pending, approved, total

**Dispatchers (web dashboard):**
- Trip/load creation: truck, driver, route, cargo, client, dates
- Driver location map (Leaflet, 30s HTMX polling)
- Expense approval queue with photo view (HTMX inline approve/reject)
- Truck fleet list with status (active / maintenance / inactive)
- Driver roster with current assignment
- Trip history, searchable
- Anomaly alert feed

**Directors (web dashboard):**
- Cost summary dashboard: total by category, by period
- Per-truck profitability: revenue vs expenses per trip
- CSV export for accounting
- Anomaly report with acknowledge button
- Driver expense ledger for dispute resolution

**Must have for international operations:**
- CMR waybill document upload and archive (legally required under UN convention)
- Border crossing log (manual via bot)
- Multi-currency expense recording (KZT, PLN, EUR, USD) with rate-at-submission storage
- Customs/duty fee expense category

**Explicitly deferred (v2+):**
- Background GPS tracking (requires native mobile app or Telegram Live Location)
- Multi-country per diem rate automation (country → rate table)
- Route benchmarking (needs 3+ months of data)
- Driver balance ledger (requires payment tracking layer)
- Automated invoicing, ELD integration, customer portal, fuel card integration

---

### Architecture Approach

Single-repository, single Railway service: FastAPI serves both the web dashboard (Jinja2+HTMX) and the Telegram webhook endpoint. PTB bot runs inside the FastAPI process via lifespan startup — no separate process, no separate port. Bot handlers and web route handlers share the same SQLAlchemy async session factory and call the same service layer. PostgreSQL is the only database (Railway managed addon). Photos and CMR documents go to Cloudflare R2 via boto3. APScheduler runs anomaly checks inside the FastAPI event loop hourly.

**Major components:**
1. `src/bot/` — PTB ConversationHandler flows (registration, expenses, location, trip commands); mounted to FastAPI via `POST /webhook/telegram`
2. `src/web/` — Jinja2+HTMX templates for `/dispatcher/*` and `/director/*`; role-guarded via JWT middleware
3. `src/api/` — JSON endpoints for HTMX partial updates and Leaflet map data
4. `src/services/` — shared business logic (ExpenseService, TripService, AnomalyService, PhotoService, NotificationService); called by both bot and web, never directly queried by handlers
5. `src/models/` — SQLAlchemy ORM models: trucks, drivers, trips, expenses, expense_photos, location_pings, trip_documents, users, alert_log

**Data model core rule:** trip is the unit of business — every expense, location ping, and document has a `trip_id` foreign key. Store monetary amounts as `NUMERIC(12,2)`, never `FLOAT`. Store original amount + currency + rate + converted USD on every expense row.

---

### Critical Pitfalls

1. **FSM state lost on Railway restart** — use `PicklePersistence` for beta, PostgreSQL-backed persistence for production; `ConversationHandler` default is in-memory and lost on any redeploy
2. **Telegram `file_id` is not permanent** — download photo bytes immediately on receipt and upload to Cloudflare R2; store both `telegram_file_id` and `storage_path`; token rotation invalidates all file_ids
3. **FastAPI + PTB event loop conflict** — do NOT call `application.run_webhook()`; instead call `application.initialize()` / `application.start()` in FastAPI lifespan and pass updates manually from the webhook route
4. **Fuel anomaly false-positive storm** — start threshold at 20-25% over norm (not 10%) for international mountain routes; require minimum 2 fill-ups before first alert; batch alerts into daily digest; add dispatcher "mark as false positive" button
5. **Alembic migration in app startup causes race condition on redeploy** — run `alembic upgrade head` as the first command in `CMD` before uvicorn starts, or as a Railway pre-deploy hook; never inside FastAPI startup event

Secondary pitfalls to address in Phase 1:
- Driver mid-flow abandonment: persist partial form data to DB after every dialog step; `conversation_timeout` must be 30+ minutes; `/continue` command to resume
- Photo upload silent failure on 2G: set `read_timeout=30, write_timeout=30`; retry once with backoff; never silently drop failed uploads
- Duplicate expense submission: idempotency key `hash(driver_id, type, amount, timestamp_floor_minute)` with DB unique constraint
- Odometer typo corruption: validate new odometer > previous and < previous + 5000 km before accepting
- N+1 queries on fleet dashboard: eager-load with `joinedload`/`selectinload`; add indexes on `driver_id`, `truck_id`, `status`, `created_at` from Day 1

---

## Implications for Roadmap

### Phase 0: Infrastructure and Proof of Concept
**Rationale:** All other phases depend on the webhook round-trip, database connection, and Railway deploy working correctly. Discover integration issues before writing any feature code.
**Delivers:** FastAPI scaffold on Railway, PTB webhook responding, driver registration end-to-end (Telegram to PostgreSQL), Alembic baseline migration, Cloudflare R2 bucket connected.
**Gate:** Driver sends `/start`, completes registration, record appears in DB. Photo upload to R2 confirmed working.
**Pitfalls addressed:** Event loop conflict, webhook URL construction, migration race condition, photo storage architecture.
**Research flag:** Standard patterns — skip additional research.

### Phase 1: Expense Control
**Rationale:** Highest business pain, lowest complexity, partially proven by existing fuel bot. Delivers immediate value to all three user types. Must establish FSM persistence, photo durability, and idempotency patterns that all later features reuse.
**Delivers:** All driver expense submission dialogs (fuel, per diem, fine, other); dispatcher expense approval queue; director cost summary dashboard; fuel anomaly detection with Telegram alert.
**Features addressed:** Full driver expense table stakes; dispatcher approval queue; director cost dashboard.
**Pitfalls addressed:** FSM persistence, photo durability, duplicate submission, odometer validation, alert threshold tuning.
**Research flag:** Standard patterns — well-documented PTB + FastAPI + HTMX; skip additional research.

### Phase 2: Trip Management
**Rationale:** Trips make all historical data queryable and are the foreign key that connects expenses, locations, and documents into meaningful business units. Cannot do profitability reporting without this entity.
**Delivers:** Trip creation (dispatcher web), driver assignment with bot notification, trip start/end commands, expense-to-trip attachment, trip detail with cost rollup, per-trip profitability if revenue entered.
**Features addressed:** Dispatcher trip management; driver trip visibility; director per-truck profitability.
**Pitfalls addressed:** Phase 2 schema migration requires expand-contract pattern — validate on copy of production DB before deploy.
**Research flag:** Standard patterns — skip additional research. Test Alembic migration on live data before deploy.

### Phase 3: Location, Map, and Documents
**Rationale:** Location and document features are independent of the expense/trip flow and can be built in parallel once Phase 2 data model is stable. These complete the dispatcher's real-time situational awareness.
**Delivers:** `/location` command, dispatcher Leaflet map with HTMX 30s polling, CMR and document upload via bot, border crossing log, multi-currency expense recording.
**Features addressed:** Dispatcher location map; international trucking requirements (CMR, border crossing, multi-currency).
**Pitfalls addressed:** Map performance with 100+ trucks — use `(truck_id, recorded_at DESC)` index; return only last ping per truck from `/api/trucks/locations`.
**Research flag:** Multi-currency FX rate source needs a decision — either a static rate table (simple, inaccurate) or an FX API call at submission time (accurate, adds dependency). Validate target countries and their per diem rate structures before implementing.

### Phase 4: Director Dashboard and Reporting
**Rationale:** Data exists from Phases 1-3; this phase surfaces it in the format the director needs for cost control and accounting handoff.
**Delivers:** Director overview KPI tiles, expense report by truck/period, anomaly log with acknowledge, CSV export, per-truck profitability view.
**Features addressed:** All director table stakes.
**Pitfalls addressed:** N+1 queries on aggregate views — use explicit GROUP BY queries, not ORM relationship traversal.
**Research flag:** Standard patterns — skip additional research.

### Phase Ordering Rationale

- Phase 0 before everything: webhook + database must be proven on real Railway infrastructure before any feature code is written
- Phase 1 before Phase 2: expenses are the highest-pain feature and their patterns (FSM, photo, idempotency) must be right before the data model expands
- Phase 2 before Phase 3: `trip_id` foreign key on expenses and location_pings requires the trips table to exist; cannot add it after the fact without a risky migration
- Phase 3 and Phase 4 can partially overlap: location map and document upload do not depend on director reporting
- Feature dependency chain from FEATURES.md: `driver registration → truck assignment → trip creation → expense submission → expense approval → cost reports → anomaly detection`

### Research Flags

Needs a decision during Phase 3 planning:
- **FX rate source** — static table vs live API; affects accuracy of multi-currency cost reports
- **Per diem country rates** — need actual rate values for Kazakhstan, EU countries on typical routes

Standard patterns (no additional research needed):
- Phase 0, 1, 2, 4 — all use well-documented FastAPI + PTB + SQLAlchemy patterns with multiple production references

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All library versions verified via PyPI; all integration patterns verified via official docs or high-credibility community sources |
| Features | HIGH (core) / MEDIUM (international) | Table stakes verified via multiple TMS sources and existing fuel bot; CMR verified via IRU; country-specific per diem rates need validation per target routes |
| Architecture | HIGH (patterns) / MEDIUM (data model) | FastAPI+PTB webhook integration verified; data model is domain-reasoned from TMS standards, not copied from reference implementation |
| Pitfalls | HIGH (bot/deployment) / MEDIUM (UX/fleet) | Bot and Railway pitfalls sourced from official docs and confirmed GitHub issues; UX and fleet pitfalls from domain research + industry sources |

**Overall confidence:** HIGH for build approach; MEDIUM for international-specific details.

### Gaps to Address

- **FX rate source**: decide before Phase 3 implementation whether to use a static exchange rate table or a live FX API (e.g., exchangerate.host or OpenExchangeRates); this affects data model for `exchange_rate` column and adds an external dependency
- **Per diem rates by country**: obtain actual daily allowance rates for KZ, PL, DE, NL, and other countries on typical routes; needed to implement `multi_country_per_diem` configuration table
- **Railway plan tier**: confirm whether Hobby ($5/month) is sufficient or Pro ($20/month) is needed before launch; cold start behavior differs and affects bot reliability at 100 drivers
- **PTB persistence backend**: `PicklePersistence` is acceptable for beta but breaks across major PTB version upgrades; plan migration to PostgreSQL-backed `BasePersistence` before production launch
- **Photo mandatory vs optional in beta**: PITFALLS.md recommends making photo optional in MVP beta until upload reliability on 2G is confirmed; decide before Phase 1 UX copy is written

---

## Sources

### Primary (HIGH confidence)
- python-telegram-bot v22.6 official docs + PyPI
- FastAPI 0.135.1 official docs + PyPI
- SQLAlchemy 2.0 official docs + PyPI (asyncpg, alembic)
- Cloudflare R2 official docs (boto3 S3-compatible pattern)
- Railway official docs (PostgreSQL addon, volumes, Nixpacks)
- Telegram Bot API official docs (webhook, file_id, secret_token)
- IRU official docs (CMR convention requirements)
- python-telegram-bot GitHub wiki (concurrency, persistence, network errors)

### Secondary (MEDIUM confidence)
- FastAPI best practices — zhanymkanov/fastapi-best-practices (5k+ stars)
- FastAPI + PTB webhook integration — FreeCodeCamp guide (verified against official PTB)
- Async SQLAlchemy 2.0 + Alembic + FastAPI — Berk Karaal 2024
- FastAPI + HTMX dashboard patterns — testdriven.io
- VektorTMS, FleetOwner, Upper Inc — TMS feature landscape
- Omniful — cross-border / multi-currency TMS specifics
- Alembic migrations without downtime — Exness Tech Blog
- Existing fuel bot codebase (ДНЕВНИК.md) — proven driver UX patterns

### Tertiary (LOW confidence)
- EmpwrTrucking — small fleet software comparison (single source)
- Dreamix TMS guide (page did not fully render)

---
*Research completed: 2026-03-08*
*Ready for roadmap: yes*
