# Feature Landscape: Freight TMS

**Domain:** Freight Transportation Management System — international trucking, 100+ drivers, 200+ trucks
**Researched:** 2026-03-08
**Research mode:** Ecosystem — what TMS products have, table stakes vs differentiating

---

## Context: Who This Is For

Three distinct user types with different needs:

| User | Access | Primary Job | Pain Point |
|------|--------|-------------|------------|
| Driver (100+) | Telegram bot | Report expenses, confirm delivery, share location | Too many steps, no time, driving with phone |
| Dispatcher | Web dashboard | Track trucks, assign loads, resolve issues | Calls all day, no visibility, orders lost |
| Director/Owner | Web dashboard | Control costs, see profitability, spot fraud | Expenses out of control, no data |

This distinction shapes every feature decision below. A feature must serve at least one user type completely to earn its place in MVP.

---

## Table Stakes

Features users expect in any TMS. Missing = product feels broken or incomplete. These are not differentiators — every competitor has them.

### For Drivers (Telegram bot interface)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Fuel expense reporting | Core pain — existing bot already does this | Low | Step-by-step dialog: liters, odometer, receipt photo, station name. Already proven in fuel bot |
| Daily allowance (per diem) submission | Drivers are owed this money; if bot doesn't handle it they chase dispatcher manually | Low | Driver inputs amount + date + city; dispatcher approves |
| Fine reporting | Fines happen constantly; paper trail prevents disputes | Low | Driver photos fine ticket; logs amount, reason, location |
| Other expense reporting | Tolls, parking, repairs, border fees — all cash out of pocket | Low | Category select + amount + photo |
| Trip assignment visibility | Driver needs to know where they're going and what they're carrying | Medium | Dispatcher assigns; driver confirms; bot shows current assignment |
| Location sharing (on-demand) | Dispatcher calls 20x/day to ask "where are you?" — this replaces calls | Medium | Driver sends geolocation via Telegram native location share |
| Shift start / shift end | Anchors all expenses to a specific trip/load | Low | Creates trip record that expenses attach to |
| My expenses summary | Drivers want to see their money — what's approved, what's pending | Low | Simple list: submitted today, pending approval, total approved |

### For Dispatchers (Web dashboard)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Trip/load management | Core job function — create trip, assign driver and truck | Medium | Trip has: route, cargo, client, departure, expected return |
| Driver location map | Real-time view of where all trucks are | Medium | Map with truck markers, last-known position, last update timestamp |
| Expense approval queue | Expenses come in from drivers; someone must approve or reject | Medium | List view: driver, expense type, amount, photo, approve/reject buttons |
| Truck fleet list | Know which trucks are active, in maintenance, or available | Low | Truck registry: plate, model, driver assigned, status |
| Driver roster | Know who's on shift, who's available | Low | Driver list with current assignment and status |
| Trip history | Dispatchers need to answer "what happened on trip X?" | Medium | Searchable log of all trips with attached expenses |
| Anomaly alerts | System flags suspicious fuel consumption, duplicate expenses | Medium | Alert feed: "Truck 003 consumed 42L/100km, norm is 35" |

### For Director/Owner (Web dashboard)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Cost summary dashboard | Owner's primary question: how much did we spend this week? | Medium | Total by category: fuel, per diem, fines, repairs — per period |
| Per-truck profitability | Which trucks are profitable? Which are bleeding money? | Medium | Revenue vs expenses per truck, per trip, per driver |
| Expense export | Data must leave system for accounting/tax purposes | Low | CSV export for given date range, filterable by truck/driver/category |
| Anomaly report | Fraud early warning: duplicate receipts, abnormal fuel consumption | Medium | Built on same anomaly detection as dispatcher alerts |
| Driver expense history | When driver claims something wasn't approved, owner can verify | Low | Per-driver expense ledger with approval timestamps |

---

## Differentiators

Features that separate this product from a spreadsheet or generic expense tracker. Not expected, but high value. Build these after table stakes are solid.

### Differentiator 1: Automatic Fuel Consumption Anomaly Detection

**Value proposition:** Fuel fraud is the #1 cost leak in trucking. Auto-detection catches it without manual review.

**What it does:** Compares actual fuel consumption to truck-specific norm. If actual exceeds norm by threshold (configurable, default 10%), flags as anomaly. Considers odometer continuity (is the odometer reading plausible?).

**Why differentiating:** Generic expense trackers just log numbers. This catches fraud. The existing fuel bot has basic version — extend to full TMS context.

| Metric | Complexity | Notes |
|--------|-----------|-------|
| Per-truck fuel norm configuration | Low | Set L/100km norm per truck model |
| Odometer continuity check | Low | Reject if new odometer < previous |
| Consumption alert threshold | Low | Configurable % over norm |
| Director alert via Telegram | Low | Already exists in fuel bot |

**Complexity overall:** Low — math is simple, data is already collected.

---

### Differentiator 2: Photo-Evidence Expense Audit Trail

**Value proposition:** Every expense has a photo of the receipt/ticket/document. Disputes become impossible.

**What it does:** Driver cannot submit expense without photo. Photos stored server-side (not just Telegram file_id). Exportable audit report shows every expense with its photo.

**Why differentiating:** Most small-fleet solutions accept text-only entries. Photo evidence is the difference between "he said/she said" and "here's the receipt."

**Complexity:** Low-Medium — storage integration needed, but Telegram already handles photo upload.

---

### Differentiator 3: Trip-Scoped Expense Rollup

**Value proposition:** See all costs for trip X in one view: fuel, per diem, fines, tolls, border fees.

**What it does:** Every expense attaches to a trip. Trip view shows: total cost, breakdown by category, per-day burn rate, final profitability vs revenue.

**Why differentiating:** Generic expense apps track expenses by date/person, not by trip. For trucking, trip is the unit of business.

**Complexity:** Medium — requires trip entity and foreign key on all expenses.

---

### Differentiator 4: Background GPS Tracking (Passive)

**Value proposition:** Truck location updates automatically without driver interaction.

**What it does:** Driver app (or Telegram bot with location sharing enabled) sends GPS coordinates every N minutes. Map shows truck path, not just last known position.

**Why differentiating:** On-demand location sharing requires driver action. Background tracking is invisible to driver — they can't forget.

**Complexity:** High — requires mobile app or Telegram bot with deep location integration. Telegram's background location sharing has limitations. May require separate driver app.

**Recommendation:** Start with on-demand location (table stakes, low complexity). Add background tracking in Phase 2+ as a differentiator.

---

### Differentiator 5: International Route Cost Benchmarking

**Value proposition:** For a given route (e.g., Almaty to Warsaw), show historical cost data: average fuel spend, average per diem, typical crossing times.

**What it does:** Aggregates trip data by route corridor. After 10+ trips on same route, surfaces benchmarks: "This trip typically costs $X in fuel, $Y in per diem."

**Why differentiating:** No spreadsheet can do this automatically. Gives owner data to negotiate driver rates and detect above-average expense trips.

**Complexity:** Medium-High — requires route normalization (cities, not exact coordinates), sufficient data volume.

**Recommendation:** Phase 3+ feature. Needs data first.

---

### Differentiator 6: Driver Balance Ledger

**Value proposition:** Driver knows exactly how much the company owes them (approved expenses not yet paid).

**What it does:** Running balance per driver: expenses approved but not reimbursed, advances issued, net payable. Driver sees this in Telegram bot without calling accounting.

**Why differentiating:** Most trucking companies handle this via WhatsApp/phone calls. A ledger view eliminates 20% of driver-dispatcher calls.

**Complexity:** Medium — requires payment/reimbursement tracking on top of expense tracking.

---

## International Trucking Specifics

These are domain-specific requirements for cross-border operations. Research confirms these are table stakes for international TMS but often absent from domestic fleet tools.

| Feature | Required For | Complexity | Notes |
|---------|-------------|------------|-------|
| CMR waybill document storage | Every international shipment — CMR is legally required under UN convention | Low | Upload scan/photo, attach to trip, searchable archive |
| Border crossing log | Audit trail of border entry/exit times and checkpoints | Low | Driver manually logs border crossing via bot |
| Currency tracking for expenses | Fuel in Kazakhstan (KZT), fines in Poland (PLN) — must convert to base currency | Medium | Driver selects currency when submitting; system stores original + converted |
| Multi-country per diem rates | Per diem differs by country — Kazakhstan rates vs EU rates | Medium | Configuration table: country → daily rate; auto-apply based on trip route |
| Customs fee / duty logging | Border fees are real costs; must be tracked separately | Low | Expense category: "Border/Customs Fee" |
| Transit country tracking | For each trip: which countries was truck in, how many days? | Medium | Required for per diem calculation and fuel tax reporting |

**Confidence:** MEDIUM — CMR and multi-currency requirements verified via multiple sources. Country-specific per diem rate tables are a known complexity but implementation details need validation per target countries.

---

## Anti-Features

Features to explicitly NOT build for MVP. They add scope, complexity, and maintenance burden without proportional value at this stage.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| AI route optimization | Requires map API integration, complex logistics algorithms, significant compute — not the bottleneck. Dispatchers already know routes. | Use Google Maps link in trip view for navigation |
| Carrier/broker marketplace | Multi-sided marketplace is a separate business, not a TMS feature | Out of scope entirely |
| ELD (Electronic Logging Device) integration | ELD is a US regulatory requirement — not applicable to CIS/EU trucking context | Track hours manually via shift start/end |
| Customer portal (shipper-facing) | Adds a third user type, doubles scope, requires separate auth system | Export delivery confirmations as PDFs for customers |
| Automated invoicing to clients | Invoicing requires accounting integration (1C, SAP, etc.) — deep rabbit hole | Export trip data as CSV for accountant |
| Fuel card integration | Fuel cards are market-specific (US: AtoB, EU: DKV/AS24) — integration complexity high, limited to card providers | Continue photo-based receipt capture |
| Predictive maintenance | Requires telematics hardware integration, IoT platform — separate product domain | Track maintenance records manually; alert on mileage/date |
| Mobile native app (iOS/Android) | Telegram bot covers driver needs at fraction of development cost | Telegram bot is the driver interface |
| Cargo tracking for customers | Real-time cargo visibility for shippers is a separate SaaS product | Not in scope |
| Multi-tenant SaaS architecture | Adds auth complexity, data isolation requirements — premature optimization | Single-tenant, one company |

---

## Feature Dependencies

```
Driver registration → All other driver features
  ↓
Truck assignment → Expenses attached to truck
  ↓
Trip creation (dispatcher) → Trip-scoped expenses
  ↓
Expense submission (driver) → Expense approval (dispatcher) → Cost reports (director)
  ↓
Anomaly detection → Director alerts
  ↓
Trip close → Trip profitability calculation
```

Location features are independent:
```
Driver location sharing → Dispatcher map view
```

Document features are independent:
```
CMR upload → Document archive → Trip document view
```

---

## MVP Recommendation

**MVP = make the pain go away, nothing more.**

The three stated pains:
1. Expenses out of control (fuel, per diem, fines) → expense tracking with photo evidence
2. No real-time tracking → on-demand location sharing
3. Orders lost between trips, no history → trip management with searchable history

**Build in this order:**

### Phase 1: Expense Control (highest pain, lowest complexity)
1. Driver Telegram bot: fuel reporting (extend existing bot)
2. Driver Telegram bot: per diem submission
3. Driver Telegram bot: fine submission
4. Driver Telegram bot: other expense submission
5. Dispatcher web: expense approval queue
6. Director web: cost summary dashboard
7. Basic anomaly detection (fuel consumption vs norm)

### Phase 2: Trip Management (unlocks all historical tracking)
1. Trip entity: route, cargo, client, dates
2. Trip assignment to driver + truck
3. Expense-to-trip attachment
4. Trip history with expense rollup
5. Trip profitability view

### Phase 3: Location + Documents
1. On-demand driver location sharing → dispatcher map
2. CMR and document upload/archive
3. Border crossing log
4. Multi-currency expense recording

### Defer to Phase 4+
- Background GPS tracking (requires driver app or native mobile)
- Route benchmarking (needs data volume)
- Driver balance ledger
- Multi-country per diem automation
- CSV exports and reporting

**Complexity budget for MVP:** Keep it simple. The dispatcher web is a CRUD app with a map. The director view is aggregated numbers. The Telegram bot is a series of dialogs. Don't overbuild Phase 1.

---

## Confidence Assessment

| Area | Confidence | Source | Notes |
|------|------------|--------|-------|
| Table stakes (expense tracking) | HIGH | Existing fuel bot + multiple TMS sources | Already partially built and validated |
| Table stakes (trip management) | HIGH | Multiple TMS product comparisons | Industry standard |
| Table stakes (dispatcher map) | HIGH | Verified in fleet management research | GPS tracking universally required |
| Differentiators | MEDIUM | Market research + domain logic | Anomaly detection and photo audit proven; others are reasoned recommendations |
| International / CMR specifics | MEDIUM | CMR verified via IRU/international trucking sources | Country-specific per diem rates need validation per target routes |
| Anti-features rationale | MEDIUM | Market research + scope reasoning | Some anti-features may move in scope if client requests |

---

## Sources

- [VektorTMS — Top TMS Features Trucking Carriers Need in 2025](https://vektortms.com/blog/top-tms-features-trucking-carriers-need-in-2025) — MEDIUM confidence (industry blog, multiple features verified)
- [Upper Inc — 12 Must-Have Fleet Management Software Features](https://www.upperinc.com/blog/fleet-management-software-features/) — MEDIUM confidence (verified multiple points)
- [Omniful — TMS for Cross-Border Logistics: Customs, Multi-Currency](https://www.omniful.ai/blog/tms-cross-border-logistics-customs-multi-currency) — MEDIUM confidence (cross-border specifics)
- [IRU — CMR Convention Overview](https://www.iru.org/what-we-do/facilitating-trade-and-transit/cmr) — HIGH confidence (official international road transport organization)
- [FleetOwner — TMS Solutions for 2026](https://www.fleetowner.com/product-spotlight/article/55325608/product-spotlight-tms-solutions-for-2026) — MEDIUM confidence (industry publication)
- [EmpwrTrucking — Best Trucking Software for Small Fleets](https://www.empwrtrucking.com/trucking-industry/best-trucking-software-of-2025-top-3-picks-for-small-fleets/) — LOW confidence (single source, useful for small fleet context)
- [Dreamix — Transportation Management System Guide 2026](https://dreamix.eu/insights/transportation-management-system-guide/) — LOW confidence (page did not render usable content)
- Existing fuel bot codebase (ДНЕВНИК.md) — HIGH confidence for driver UX patterns and proven workflows
