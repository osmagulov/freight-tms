# Roadmap: Freight TMS

## Overview

Five phases deliver a working freight management system: foundation first (Railway deploy, webhook, database, driver registration), then expense control (the highest-pain feature, partially proven by the existing fuel bot), then trip management (which connects all data into queryable business units), then location tracking (real-time fleet visibility), and finally the director dashboard (cost reporting and anomaly review). Each phase delivers a coherent capability that dispatchers or drivers can use immediately. No phase produces half-working features.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Infrastructure & Foundation** - Railway deploy, PTB webhook, PostgreSQL, driver registration, R2 storage
- [ ] **Phase 2: Expense Control** - Driver expense dialogs, dispatcher approval queue, fuel anomaly detection
- [ ] **Phase 3: Trip Management** - Dispatcher creates trips, driver opens/closes trips, trip history, fleet dashboard
- [ ] **Phase 4: Location & Map** - Driver location sharing via bot, dispatcher Leaflet map with live truck positions
- [ ] **Phase 5: Director Dashboard & Reporting** - Cost summary, CSV export, anomaly log, per-driver history

## Phase Details

### Phase 1: Infrastructure & Foundation
**Goal**: The system runs on Railway with a working Telegram webhook, a live PostgreSQL database, and drivers can register and link their truck through the bot
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, REG-01, REG-02, REG-03, REG-04
**Success Criteria** (what must be TRUE):
  1. Driver sends /start in Telegram, completes registration (name, phone), record appears in PostgreSQL
  2. Driver links a truck by plate number through the bot, dispatcher sees the linked driver-truck pair in the web panel
  3. A receipt photo sent through the bot is stored durably in Cloudflare R2 and retrievable via URL
  4. Railway redeploy does not lose a driver's in-progress bot conversation (FSM state persists)
  5. Dispatcher and director can log into the web panel with a password; unauthenticated requests are redirected to login
**Plans**: 6 plans

Plans:
- [ ] 01-PLAN.md — Database & configuration foundation (PostgreSQL URL, Settings, models, Alembic migration)
- [ ] 02-PLAN.md — FastAPI + PTB webhook integration (lifespan, /telegram route, receive_vehicle() FK fix)
- [ ] 03-PLAN.md — FSM persistence (persistent=True on all 4 remaining ConversationHandlers)
- [ ] 04-PLAN.md — Cloudflare R2 photo storage (r2.py service, expense_flow photo upload, photo_r2_url column)
- [ ] 05-PLAN.md — Web panel foundation (JWT auth, /panel/login, /panel/drivers, vehicle edit form)
- [ ] 06-PLAN.md — Railway deployment (railway.toml, .env.example, smoke test on production)

### Phase 2: Expense Control
**Goal**: Drivers can submit all expense types through the bot and dispatchers can approve or reject them inline, with automated fuel anomaly detection alerting the director
**Depends on**: Phase 1
**Requirements**: EXP-01, EXP-02, EXP-03, EXP-04, EXP-05, EXP-06, EXP-07, EXP-08, EAPPR-01, EAPPR-02, EAPPR-03, ALERT-01, ALERT-02, ALERT-03, ALERT-04, FLEET-03
**Success Criteria** (what must be TRUE):
  1. Driver submits a fuel expense (liters, odometer, photo, station) through the bot; system rejects an odometer lower than the previous reading
  2. Driver submits per diem, fine, and other expenses (repair, toll, customs) each through a dedicated bot dialog with multi-currency support (KZT, RUB, EUR, USD)
  3. Driver sees their own expense summary in the bot: pending approval, approved, and trip total
  4. Dispatcher sees the approval queue on the web panel, approves or rejects an expense inline (no page reload), and the driver receives a bot notification immediately
  5. When actual fuel consumption exceeds the truck's norm by more than 20% (after at least 2 prior fill-ups), the director receives a Telegram digest alert and the dispatcher sees the anomaly in the fleet feed with a "false alarm" button
**Plans**: 5 plans

Plans:
- [ ] 01-PLAN.md — Schema migration (new Expense columns + FuelAnomaly table + DIRECTOR_TG_ID setting)
- [ ] 02-PLAN.md — Bot expense flows refactor (FUEL with odometer validation, PER_DIEM, FINE, OTHER) + FX rates + idempotency
- [ ] 03-PLAN.md — HTMX approval queue (/panel/expenses) + bot notifications on approve/reject
- [ ] 04-PLAN.md — Anomaly detection service + APScheduler hourly digest + /panel/anomalies feed
- [ ] 05-PLAN.md — /my_expenses bot command (expense summary) + end-to-end smoke test checkpoint

### Phase 3: Trip Management
**Goal**: Dispatchers can create and assign trips, drivers receive and execute trips through the bot, and all historical trip data is searchable with full cost rollup
**Depends on**: Phase 2
**Requirements**: TRIP-01, TRIP-02, TRIP-03, TRIP-04, TRIP-05, TRIP-06, TRIP-07, FLEET-01, FLEET-02
**Success Criteria** (what must be TRUE):
  1. Dispatcher creates a trip (truck, driver, route, cargo, client, dates) on the web panel and the assigned driver receives a bot notification
  2. Driver opens the trip in the bot (confirms departure, enters starting odometer) and can attach CMR/waybill documents as photos or PDFs
  3. Driver closes the trip in the bot (final odometer, delivery status) and the trip is marked complete in the system
  4. Dispatcher searches trip history by truck or driver with filters and sees full trip details: all expenses, attached documents, and location pings
  5. Fleet dashboard shows every truck with its current status (in-trip / available / maintenance), current driver, and current trip
**Plans**: TBD

### Phase 4: Location & Map
**Goal**: Drivers can share their position with one tap in the bot, and dispatchers see all truck positions on a live map that refreshes automatically
**Depends on**: Phase 3
**Requirements**: LOC-01, LOC-02, LOC-03, LOC-04
**Success Criteria** (what must be TRUE):
  1. Driver taps the location button in the bot and their Telegram native geolocation is recorded and linked to their active trip
  2. Dispatcher opens the map and sees all trucks with their last known position, plate number, driver name, and time of last ping
  3. The map refreshes automatically every 30 seconds without a full page reload
**Plans**: TBD

### Phase 5: Director Dashboard & Reporting
**Goal**: The director can review total fleet costs by category and period, drill into per-truck and per-driver breakdowns, and export data for accounting
**Depends on**: Phase 4
**Requirements**: DIR-01, DIR-02, DIR-03, DIR-04, DIR-05
**Success Criteria** (what must be TRUE):
  1. Director sees a cost summary dashboard with totals by category (fuel, per diem, fines, repair) for any selected period
  2. Director sees per-truck cost history broken down trip by trip, filterable by period
  3. Director exports a filtered expense report to CSV (by truck, driver, or period) and opens it in a spreadsheet without errors
  4. Director sees the full anomaly history (truck, trip, overage percentage, status) and can acknowledge confirmed anomalies
  5. Director looks up a specific driver's expense history to resolve a payment dispute
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure & Foundation | 0/6 | Not started | - |
| 2. Expense Control | 0/5 | Not started | - |
| 3. Trip Management | 0/? | Not started | - |
| 4. Location & Map | 0/? | Not started | - |
| 5. Director Dashboard & Reporting | 0/? | Not started | - |
