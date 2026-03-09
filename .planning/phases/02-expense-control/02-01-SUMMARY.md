---
phase: 02-expense-control
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, postgres, pydantic-settings, apscheduler]

# Dependency graph
requires:
  - phase: 01-infrastructure-and-foundation
    provides: "Base SQLAlchemy models, Alembic migration chain head a1b2c3d4e5f6, asyncpg database setup"
provides:
  - "Expense model with 10 new Phase 2 columns (status, approved_by, approved_at, rejection_comment, liters, odometer_reading, station, fx_rate, amount_kzt, idempotency_minute)"
  - "uq_expense_idempotent UniqueConstraint on (trip_id, expense_type, amount, idempotency_minute)"
  - "FuelAnomaly model with fuel consumption tracking and FK relationships to expenses, vehicles, trips"
  - "Settings.DIRECTOR_TG_ID field for anomaly digest notifications"
  - "APScheduler>=3.10.0 declared in requirements.txt"
  - "Alembic migration 15882711c59b at chain head for all Phase 2 schema changes"
affects:
  - 02-expense-control (all Wave 2/3 plans depend on these columns)
  - bot expense submission flows
  - approval queue
  - anomaly detection scheduler

# Tech tracking
tech-stack:
  added:
    - "APScheduler>=3.10.0 (hourly anomaly check scheduler, replaces Celery+Redis)"
  patterns:
    - "SQLAlchemy __table_args__ for UniqueConstraints on ORM models"
    - "Alembic manual migration with server_default for NOT NULL column additions to existing tables"
    - "nullable=True for optional fuel/approval columns; nullable=False with server_default for status enforcement"

key-files:
  created:
    - "alembic/versions/15882711c59b_phase2_expense_control_schema.py"
  modified:
    - "src/db/models.py"
    - "src/core/config.py"
    - "requirements.txt"

key-decisions:
  - "DIRECTOR_TG_ID defaults to 0 (int) in Settings — must be set in Railway env before anomaly alerts go live"
  - "status column uses client-side default='PENDING' in ORM and server_default='PENDING' in migration — both needed for Railway pre-deploy hook correctness"
  - "threshold_per_100km added to FuelAnomaly model (not in plan spec) to store the per-vehicle norm+20% threshold at detection time for audit trail"

patterns-established:
  - "All Phase 2 schema gated behind this migration — Wave 2 and Wave 3 plans must not add columns in separate migrations"
  - "FuelAnomaly records are append-only — is_false_alarm and notified are the only mutable fields"

requirements-completed:
  - EXP-01
  - EXP-02
  - EXP-07
  - EXP-08
  - EAPPR-01
  - EAPPR-02
  - ALERT-01
  - ALERT-02
  - ALERT-03
  - ALERT-04
  - FLEET-03

# Metrics
duration: 5min
completed: 2026-03-09
---

# Phase 2 Plan 01: Phase 2 Schema Foundation Summary

**Alembic migration 15882711c59b adds 10 expense columns, uq_expense_idempotent constraint, and fuel_anomalies table as the serial gate enabling all Phase 2 expense-control features**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-09T03:44:00Z
- **Completed:** 2026-03-09T03:49:18Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Extended Expense ORM model with all Phase 2 columns (approval workflow, fuel-specific, multi-currency, idempotency) and UniqueConstraint
- Created FuelAnomaly model with FK relationships to expenses, vehicles, and trips tables
- Added DIRECTOR_TG_ID to Settings and APScheduler to requirements
- Created complete Alembic migration with correct server_default for NOT NULL status column — safe for pre-deploy hook against populated DB

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend Expense model and add FuelAnomaly model** - `ce78af0` (feat)
2. **Task 2: Add DIRECTOR_TG_ID, APScheduler, and Alembic migration** - `e8ce519` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `src/db/models.py` - Added UniqueConstraint import, 10 Expense columns, __table_args__, FuelAnomaly class
- `src/core/config.py` - Added DIRECTOR_TG_ID: int = 0 field to Settings
- `requirements.txt` - Added APScheduler>=3.10.0
- `alembic/versions/15882711c59b_phase2_expense_control_schema.py` - Full upgrade/downgrade migration for all Phase 2 schema changes

## Decisions Made
- `status` column uses both ORM `default="PENDING"` (client-side, for new ORM inserts) and migration `server_default='PENDING'` (server-side, for safe NOT NULL addition to existing rows) — both are needed
- `threshold_per_100km` added to FuelAnomaly beyond the plan spec to record the per-vehicle threshold at detection time (audit trail for false positive reviews)
- `DIRECTOR_TG_ID` defaults to `0` (int not str) — must be set in Railway env vars before Phase 2 anomaly alerts ship

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added threshold_per_100km to FuelAnomaly model and migration**
- **Found during:** Task 1 (FuelAnomaly model creation)
- **Issue:** Plan spec includes `actual_per_100km`, `norm_per_100km`, and `excess_percent` but omits the actual threshold value used to flag the anomaly. Without storing it, false positive review would require re-deriving the threshold from vehicle fuel_norm_per_100km at review time, which may have changed.
- **Fix:** Added `threshold_per_100km = Column(Float, nullable=False)` to FuelAnomaly model and `sa.Column('threshold_per_100km', sa.Float(), nullable=False)` to migration
- **Files modified:** src/db/models.py, alembic/versions/15882711c59b_phase2_expense_control_schema.py
- **Verification:** Column present in FuelAnomaly definition, migration creates it correctly
- **Committed in:** ce78af0 (Task 1 commit), e8ce519 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (missing critical field for audit trail)
**Impact on plan:** Column required for correct false-positive audit workflow. No scope creep — stays within FuelAnomaly table.

## Issues Encountered
- `Expense().status` returns `None` on raw instantiation (SQLAlchemy `default=` only fires on INSERT, not object construction) — this is correct ORM behavior. The migration `server_default='PENDING'` ensures all database rows have status populated. Verified column definition is correct.

## User Setup Required
- Set `DIRECTOR_TG_ID` env var in Railway to the director's Telegram user ID before Phase 2 anomaly alerts are enabled.

## Next Phase Readiness
- All Wave 2 and Wave 3 Phase 2 plans can now be built — the schema gate is in place
- Migration will run via Railway pre-deploy hook on next deployment
- FuelAnomaly table ready for anomaly detection scheduler implementation
- Approval workflow columns ready for dispatcher approval queue implementation

---
*Phase: 02-expense-control*
*Completed: 2026-03-09*
