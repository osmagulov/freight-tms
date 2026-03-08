# Codebase Concerns

**Analysis Date:** 2026-03-08

## Tech Debt

**Hardcoded Vehicle ID in Trip Opening:**
- Issue: `vehicle_id=1` is hardcoded in `antigravity_modules/trip_opening.py:112` as a temporary workaround for MVP
- Files: `antigravity_modules/trip_opening.py`
- Impact: All trips are incorrectly assigned to vehicle_id=1, making multi-vehicle trip tracking impossible. This breaks actual fleet management functionality and prevents accurate vehicle utilization tracking.
- Fix approach: Implement proper driver-to-vehicle assignment either by:
  1. Adding a driver_vehicle_assignment table linking drivers to their assigned vehicles
  2. Requesting vehicle selection from driver during trip opening with keyboard markup
  3. Retrieving the driver's last-used or primary vehicle from a vehicle_drivers relationship

**Unimplemented FastAPI Startup/Shutdown Hooks:**
- Issue: TODOs in `src/main.py:16` and `src/main.py:21` indicate bot integration is incomplete
- Files: `src/main.py`
- Impact: FastAPI application doesn't actually start the Telegram bot polling or handle cleanup. Bot is currently started separately via `run_bot.py`, creating two entry points and potential race conditions.
- Fix approach: Integrate bot startup/shutdown into FastAPI lifecycle using proper async context management

**Missing Driver-Vehicle Relationship:**
- Issue: MVP treats driver and vehicle registration separately without establishing a link
- Files: `src/db/models.py`, `src/bot/bot_app.py:113-114`, `antigravity_modules/trip_opening.py:42-45`
- Impact: Cannot track which driver owns/operates which vehicle. Registration flow asks for vehicle plate but doesn't link it to the driver. This breaks vehicle assignment and trip attribution.
- Fix approach: Add explicit vehicle_id to driver registration or create a driver_vehicles association table with a primary_vehicle_id field

**Duplicate Migration Files:**
- Issue: Multiple migrations reference the same field (e.g., `09ae23994f12_add_card_photo_file_id.py` and `18ed19dece10_add_card_photo_file_id.py`)
- Files: `alembic/versions/09ae23994f12_add_card_photo_file_id.py`, `alembic/versions/18ed19dece10_add_card_photo_file_id.py`
- Impact: Schema migrations are redundant and confusing. Could cause issues when rolling back or understanding database evolution.
- Fix approach: Clean up migration history by squashing migrations or manually removing duplicates

**String Status Fields Instead of Enums:**
- Issue: Models define Python enums (TripStatus, DriverStatus, etc. in `src/db/models.py`) but database columns store them as plain strings with `Column(String, ...)`
- Files: `src/db/models.py:38,48,61,80`
- Impact: No database-level validation. String values like "TYPO_STATUS" could be inserted, breaking application logic. Alembic migrations don't enforce enum constraints.
- Fix approach: Use SQLAlchemy's Enum column type with appropriate backend (e.g., `Column(Enum(TripStatus))`) to add database-level validation

---

## Security Considerations

**Telegram Bot Token in Environment Not Validated:**
- Risk: Bot token must be provided via .env, but missing validation could cause silent failures or hardcoded fallback to "replace_me"
- Files: `src/core/config.py:4`
- Current mitigation: Default is "replace_me" which is obvious when wrong, but no startup validation
- Recommendations:
  1. Add validation in Settings to raise error if token equals "replace_me" or is empty
  2. Add startup check in bot initialization to verify token format (should start with numbers)
  3. Log token presence confirmation (not value) on startup

**No Input Validation on User-Provided Data:**
- Risk: Driver names, phone numbers, vehicle plates, route descriptions, and comments are accepted without sanitization
- Files: `antigravity_modules/trip_opening.py:55,65`, `antigravity_modules/expense_flow.py:158`, `src/bot/bot_app.py:69,98`
- Current mitigation: None
- Recommendations:
  1. Add length limits: name max 100 chars, phone max 20 chars, plate max 10 chars, route max 500 chars
  2. Sanitize strings to prevent SQL injection (though SQLAlchemy parameterization helps)
  3. Validate phone format matches expected pattern
  4. Validate license plate format (currently uppercase only, but no length check)

**File IDs Not Validated:**
- Risk: Telegram file IDs are stored directly without validation. A malformed file ID could break recovery/retrieval
- Files: `antigravity_modules/trip_opening.py:79,81`, `antigravity_modules/trip_closing.py:73,75`, `antigravity_modules/expense_flow.py:117,119,139,141`
- Current mitigation: None
- Recommendations:
  1. Validate file IDs match expected Telegram format before storing
  2. Add try-catch around file retrieval operations
  3. Log file retrieval errors separately to identify invalid entries

**No Authentication for Database:**
- Risk: `.env` file contains DATABASE_URL with credentials, but is version-controlled (only .gitignore lists `.env` generically)
- Files: `.env.example` shows pattern
- Current mitigation: Listed in .env, .env.example, but file system relies on .gitignore
- Recommendations:
  1. Verify .gitignore explicitly lists `.env` and `.env*.local`
  2. Add pre-commit hook to catch .env commits
  3. Use connection pooling parameters for production (pool_size, max_overflow)

**No Rate Limiting on Bot Commands:**
- Risk: Malicious users could spam `/open_trip`, `/add_expense`, `/close_trip` to DOS the bot or fill database
- Files: `src/bot/bot_app.py`, `antigravity_modules/trip_opening.py`, `antigravity_modules/expense_flow.py`, `antigravity_modules/trip_closing.py`
- Current mitigation: None
- Recommendations:
  1. Add user-level rate limiting (e.g., 1 trip open per 30 min, 10 expenses per hour)
  2. Use context.user_data to track command timestamps
  3. Add throttle decorator or middleware to ConversationHandler

---

## Performance Bottlenecks

**N+1 Query Risk in Trip Queries:**
- Problem: `get_active_trip_for_driver()` in `antigravity_modules/expense_crud.py:8-14` queries Trip but doesn't eager-load relationships (driver, vehicle, expenses)
- Files: `antigravity_modules/expense_crud.py`, used by multiple flows
- Cause: Trip object relationships are accessed later (e.g., in `trip_closing.py:92`), triggering additional database queries per access
- Improvement path:
  1. Add `.options(selectinload(Trip.expenses), selectinload(Trip.driver), selectinload(Trip.vehicle))` to query
  2. Consider caching active trips per driver if polling becomes frequent
  3. Add database query logging to identify other N+1 patterns

**No Pagination for Location Updates:**
- Problem: `LocationUpdate` table grows unbounded, no query limits
- Files: `src/db/models.py:92-103`, `antigravity_modules/location_flow.py:61-68`
- Cause: Every location share is appended. No TTL, archival, or cleanup strategy
- Improvement path:
  1. Add index on (driver_id, created_at) for efficient range queries
  2. Implement archival job to move old locations (>30 days) to separate table
  3. Add pagination to any future location retrieval endpoints

**String Formatting with format() vs f-strings:**
- Problem: Mixed use of `.format()` (newer code) and hardcoded strings in `antigravity_modules/translations.py:111-116` creates inconsistency
- Files: `antigravity_modules/translations.py`
- Cause: Minor - no perf impact, but affects maintainability
- Improvement path: Standardize on f-strings with proper escaping for translation values

---

## Fragile Areas

**Translation Key Typo/Duplication:**
- Files: `antigravity_modules/translations.py:22-23`
- Why fragile: "exp_no_trip" key is defined twice with different values (line 22 has different text than line 23). If code references one, changing it breaks the other reference.
- Safe modification:
  1. Identify all references to "exp_no_trip" in expense_flow.py
  2. Choose the correct translation and delete the duplicate
  3. Search codebase for all keys to ensure no others are duplicated
- Test coverage: Add test that validates all translation keys are used and unique

**Conversation State Not Validated:**
- Files: `antigravity_modules/trip_opening.py:102-106`, `antigravity_modules/trip_closing.py:80-82`, `antigravity_modules/expense_flow.py:162-168`
- Why fragile: Code assumes context.user_data has expected keys (driver_id, trip_id, etc.) without validation. If conversation interrupted or resumed incorrectly, KeyError could crash handler.
- Safe modification:
  1. Use `.get()` with defaults instead of direct key access
  2. Add validation at state transition boundaries
  3. Test conversation interruption scenarios (user starts new command mid-flow)
- Test coverage: Integration tests for conversation recovery

**Odometer Validation Incomplete:**
- Files: `antigravity_modules/trip_closing.py:57-58` validates end >= start, but `trip_opening.py:93-100` has no upper bound
- Why fragile: User could enter 999999999 as starting odometer, making end_odometer validation fail for legitimate trips. No range checks.
- Safe modification:
  1. Add max odometer check (e.g., 999,999 km, or 9,999,999 for exceptional cases)
  2. Add min check (e.g., >= 0)
  3. Warn user if jump is >1000km in single trip (potential data entry error)
- Test coverage: Unit tests for odometer validation with boundary values

**Bare Exception Handling in DB Operations:**
- Files: `src/db/crud.py:14,24,34`, `antigravity_modules/expense_crud.py:36` - No try-catch around `session.commit()`
- Why fragile: Database errors (integrity constraints, connection loss) will propagate unhandled, crashing handlers mid-conversation
- Safe modification:
  1. Wrap all session.commit() in try-except blocks
  2. Catch `IntegrityError` separately (duplicate driver, vehicle plate already exists)
  3. Return meaningful errors to user, not stack traces
- Test coverage: Integration tests with database errors (constraint violation, connection failure)

---

## Scaling Limits

**SQLite Default Choice:**
- Current capacity: SQLite handles ~100 concurrent writes poorly, suitable for <10 drivers, ~100 trips/day
- Limit: Becomes problematic with 20+ active drivers or 1000+ daily trips
- Scaling path:
  1. Production `.env` should use `DATABASE_URL=postgresql+asyncpg://...` (already in .env.example)
  2. Verify asyncpg dependency is used correctly for PostgreSQL
  3. Add database pooling configuration for production

**No Async Batch Operations:**
- Current capacity: Creates individual database records one at a time in sync context
- Limit: For bulk operations (multi-expense days, location history export), could be slow
- Scaling path:
  1. Implement `create_expenses_batch()` for multiple expenses if UI adds bulk features
  2. Add executemany() for batch inserts in CRUD layer
  3. Consider location archival batch job to prevent table bloat

**Single-Process Bot:**
- Current capacity: One bot instance handles all users sequentially within handlers
- Limit: With 50+ active users submitting photos/documents, response lag increases significantly
- Scaling path:
  1. Consider task queue (Celery + Redis) for async photo processing and DB writes
  2. Use `apt-get install redis-server` + create worker processes
  3. Implement job-queue from python-telegram-bot library for scheduled tasks

---

## Dependencies at Risk

**python-telegram-bot [job-queue]:**
- Risk: This is a heavy feature dependency that enables scheduled tasks, but not currently used in code
- Impact: Bloats requirements; if job-queue feature breaks in a minor update, could cause unnecessary conflicts
- Migration plan:
  1. Remove `[job-queue]` extra if scheduling isn't planned soon
  2. If needed later, add dependency explicitly for scheduled cleanup tasks (e.g., trip auto-timeout)

**No Direct asyncpg Usage Check:**
- Risk: asyncpg is listed in requirements.txt but not directly imported in codebase
- Impact: SQLAlchemy is responsible for using it. If SQLAlchemy + asyncpg integration breaks, app fails silently
- Migration plan:
  1. Verify in startup that asyncpg driver is properly loaded
  2. Add explicit test for PostgreSQL connection using asyncpg directly
  3. Document that asyncpg is required for production (SQLite doesn't need it)

---

## Missing Critical Features

**No Error Recovery for Failed Trips:**
- Problem: If user's phone dies mid-trip, no mechanism to resume from checkpoint
- Blocks: Cannot continue tracking trip state, expenses logged to orphaned trip
- Impact: High - drivers could lose trip history or have duplicate trips for same journey

**No Audit Trail for Data Changes:**
- Problem: Who edited what and when is not tracked
- Blocks: Cannot dispute expense claims or verify data integrity
- Impact: Medium - important for fraud prevention and reconciliation

**No Offline Support:**
- Problem: All operations require real-time database connection; no local caching
- Blocks: Cannot collect data in areas with poor connectivity
- Impact: High for regions with spotty coverage

**No Webhook Validation:**
- Problem: If implementing webhook-based bot (vs polling), no CSRF/signature verification
- Blocks: Bot could be hijacked by malicious requests
- Impact: Medium - relevant if deployment changes to webhook mode

---

## Test Coverage Gaps

**No Unit Tests for CRUD Operations:**
- What's not tested: `src/db/crud.py` functions (create_driver, create_vehicle, get_driver_by_tg_id) have no assertions
- Files: `src/db/crud.py`
- Risk: Regressions in database layer go unnoticed; constraints might not work as expected
- Priority: High

**No Integration Tests for Conversation Flows:**
- What's not tested: Multi-step conversation handlers (trip opening, expense flow) are not tested end-to-end
- Files: `antigravity_modules/trip_opening.py`, `antigravity_modules/expense_flow.py`, `antigravity_modules/trip_closing.py`, `antigravity_modules/location_flow.py`
- Risk: State machine bugs, data corruption from partial entries, race conditions between flows
- Priority: High

**No Validation Tests:**
- What's not tested: Odometer validation (`trip_opening.py:93-100`, `trip_closing.py:54-61`), amount parsing (`expense_flow.py:84-89`), currency code validation
- Files: `antigravity_modules/trip_opening.py`, `antigravity_modules/expense_flow.py`, `antigravity_modules/trip_closing.py`
- Risk: Invalid data (negative odometer, non-numeric amounts) could be stored
- Priority: High

**No Database Migration Tests:**
- What's not tested: Alembic migration files are not validated to run successfully on clean schemas
- Files: `alembic/versions/*.py`
- Risk: Duplicate migrations or broken upgrade paths could silently fail in production
- Priority: Medium

**No Error Scenario Tests:**
- What's not tested: What happens when database connection fails, Telegram API fails, or file upload fails mid-conversation
- Files: All handler files in `antigravity_modules/` and `src/bot/`
- Risk: Unhandled exceptions crash handlers, leaving conversations in inconsistent state
- Priority: Medium

---

*Concerns audit: 2026-03-08*
