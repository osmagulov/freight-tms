---
phase: 01-infrastructure-and-foundation
plan: 04
subsystem: infra
tags: [cloudflare-r2, boto3, s3, alembic, sqlalchemy, telegram-bot]

# Dependency graph
requires:
  - phase: 01-01
    provides: "Settings with R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME env vars"
  - phase: 01-03
    provides: "expense_flow.py with persistent ConversationHandler and photo receipt step"
provides:
  - "src/services/r2.py: async upload_photo_to_r2() using boto3 in thread executor"
  - "Expense.photo_r2_url column for durable R2 URL storage"
  - "Alembic migration a1b2c3d4e5f6 adding photo_r2_url to expenses table"
  - "expense_flow.py receive_expense_photo() downloads from Telegram and uploads to R2"
  - "create_expense() accepts and stores photo_r2_url"
affects:
  - "02-expense-reporting"
  - "expense photo retrieval"
  - "receipt URL generation"

# Tech tracking
tech-stack:
  added: [boto3, botocore, cloudflare-r2]
  patterns:
    - "run_in_executor for synchronous boto3 calls within asyncio event loop"
    - "Graceful fallback: log warning and return None when credentials absent"
    - "Dual-track storage: photo_r2_url (durable) + photo_file_id (backward compat)"

key-files:
  created:
    - src/services/__init__.py
    - src/services/r2.py
    - alembic/versions/a1b2c3d4e5f6_phase1_add_photo_r2_url.py
  modified:
    - src/db/models.py
    - antigravity_modules/expense_flow.py
    - antigravity_modules/expense_crud.py

key-decisions:
  - "boto3 is synchronous — wrapped in asyncio.get_event_loop().run_in_executor(None, partial(...)) to avoid blocking event loop"
  - "photo_file_id retained alongside photo_r2_url for backward compatibility with any existing data"
  - "R2 key pattern: receipts/{trip_id}/{uuid}.jpg for logical partitioning by trip"
  - "Graceful degradation: if R2 credentials absent, upload_photo_to_r2() returns None with warning (no crash)"

patterns-established:
  - "Thread executor pattern: use functools.partial + loop.run_in_executor for sync IO in async handlers"
  - "R2 client creation: boto3 s3 client with endpoint_url=https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com and s3v4 signature"

requirements-completed: [INFRA-03]

# Metrics
duration: 8min
completed: 2026-03-09
---

# Phase 1 Plan 4: R2 Photo Storage Integration Summary

**Cloudflare R2 receipt storage via boto3 in thread executor with Alembic migration, wired into Telegram expense flow for durable photo URLs**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-09T12:00:00Z
- **Completed:** 2026-03-09T12:08:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Created `src/services/r2.py` with `upload_photo_to_r2()` — async wrapper around synchronous boto3 using `run_in_executor` so uploads never block the Telegram bot event loop
- Added `photo_r2_url` column to `Expense` model and created Alembic migration `a1b2c3d4e5f6` chained after the phase1_add_vehicle_link migration
- Rewired `receive_expense_photo()` to download photo bytes from Telegram via `get_file().download_as_bytearray()` and upload to R2, storing the resulting public URL in `photo_r2_url` — `photo_file_id` kept for backward compatibility
- `create_expense()` in `expense_crud.py` now accepts and persists `photo_r2_url`; `skip_photo()` sets `photo_r2_url = None`

## Task Commits

Each task was committed atomically:

1. **Task 1: Create R2 upload service and add photo_r2_url to Expense model** - `bfddd0c` (feat)
2. **Task 2: Wire R2 upload into expense_flow photo receipt step** - `6e45a8a` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `src/services/__init__.py` - Package init for services module
- `src/services/r2.py` - `_get_r2_client()`, `_upload_sync()`, and async `upload_photo_to_r2()` with graceful fallback
- `src/db/models.py` - Added `photo_r2_url = Column(String, nullable=True)` to Expense class
- `alembic/versions/a1b2c3d4e5f6_phase1_add_photo_r2_url.py` - Migration: `op.add_column('expenses', 'photo_r2_url')`
- `antigravity_modules/expense_flow.py` - Added `uuid`, `upload_photo_to_r2` imports; rewrote `receive_expense_photo()`; updated `skip_photo()` and `process_final_expense()`
- `antigravity_modules/expense_crud.py` - Added `photo_r2_url: str = None` parameter to `create_expense()` and included in `Expense()` constructor

## Decisions Made
- boto3 is synchronous — wrapped in `asyncio.get_event_loop().run_in_executor(None, partial(...))` to avoid blocking the asyncio event loop
- `photo_file_id` retained alongside `photo_r2_url` for backward compatibility with any existing data
- R2 key pattern: `receipts/{trip_id}/{uuid.uuid4()}.jpg` for logical partitioning by trip
- Graceful degradation: if any R2 credential is absent, `upload_photo_to_r2()` returns `None` with `logger.warning` (no crash, no exception propagation)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

**External services require manual configuration.** Cloudflare R2 credentials must be set before photo upload is active:

| Env Var | Source |
|---------|--------|
| `R2_ACCOUNT_ID` | Cloudflare Dashboard -> R2 -> Overview -> Account ID (top right) |
| `R2_ACCESS_KEY_ID` | Cloudflare Dashboard -> R2 -> Manage R2 API Tokens -> Create API Token (R2 read+write) |
| `R2_SECRET_ACCESS_KEY` | Same token creation page — shown once at creation |
| `R2_BUCKET_NAME` | Set to bucket name created in dashboard (recommended: `freight-tms-photos`) |

**Dashboard config:** Create R2 bucket at Cloudflare Dashboard -> R2 -> Create Bucket (name: `freight-tms-photos`, region: auto).

If credentials are absent, the bot still works — photos are skipped (stored as `None`) with a warning log. No crash.

## Next Phase Readiness
- R2 upload service is ready for Phase 2 expense reporting and photo retrieval by URL
- Migration `a1b2c3d4e5f6` must be applied on Railway before photo uploads will persist: `alembic upgrade head`
- boto3 must be in requirements.txt — verify it is present before deploying

## Self-Check

- [x] `src/services/r2.py` — created, contains `upload_photo_to_r2` and `run_in_executor`
- [x] `src/db/models.py` — `photo_r2_url` column in Expense class
- [x] `alembic/versions/a1b2c3d4e5f6_phase1_add_photo_r2_url.py` — migration file exists, chains from `4d9175cac075`
- [x] `antigravity_modules/expense_flow.py` — imports `upload_photo_to_r2`, uses it in `receive_expense_photo()`, sets `photo_r2_url` in `skip_photo()` and `process_final_expense()`
- [x] `antigravity_modules/expense_crud.py` — `create_expense()` accepts and stores `photo_r2_url`
- [x] Task commits: `bfddd0c` (Task 1), `6e45a8a` (Task 2)

## Self-Check: PASSED

---
*Phase: 01-infrastructure-and-foundation*
*Completed: 2026-03-09*
