# Testing Patterns

**Analysis Date:** 2026-03-08

## Test Framework

**Status:** Not detected

- No test framework installed (pytest, unittest, or equivalent not in requirements.txt)
- No test directories found (`tests/`, `test/`, `*_test.py`, `test_*.py`)
- No test configuration files (pytest.ini, setup.cfg, tox.ini, .coveragerc)
- **Testing currently not implemented in this codebase**

**Current Dependencies (from requirements.txt):**
```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
python-telegram-bot[job-queue]>=21.6
SQLAlchemy>=2.0.30
alembic>=1.13.1
asyncpg>=0.30.0
python-dotenv>=1.0.1
pydantic>=2.9.0
pydantic-settings>=2.5.0
```

## Recommended Framework

**For this codebase, recommended testing setup:**

- **Test Runner:** `pytest` with `pytest-asyncio` for async support
- **Assertion Library:** `pytest` built-in assertions
- **Mocking:** `unittest.mock` or `pytest-mock`
- **Database Testing:** `SQLAlchemy` test fixtures with in-memory SQLite
- **Telegram Bot Testing:** `python-telegram-bot` TestClient or mock telegram modules

## Test File Organization

**Recommended Structure:**
```
project-root/
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Shared fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_crud.py            # Database CRUD operations
│   │   ├── test_models.py          # Model validation
│   │   └── test_translations.py    # Translation helper functions
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_expense_flow.py    # Conversation handler workflows
│   │   ├── test_trip_flow.py
│   │   └── test_location_flow.py
│   └── fixtures/
│       ├── __init__.py
│       └── factories.py            # Test data factories
```

**Naming Convention (to be adopted):**
- Test files: `test_{module_name}.py`
- Test functions: `test_{function_name}_{scenario}`
- Example: `test_get_driver_by_tg_id_returns_driver_when_found()`
- Example: `test_get_driver_by_tg_id_returns_none_when_not_found()`

## Test Structure (Recommended Pattern)

**Async Test Pattern (for this codebase):**

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_get_driver_by_tg_id_returns_driver():
    """Should return Driver object when found in database."""
    # Arrange
    mock_session = AsyncMock()
    test_tg_id = 12345

    # Act
    result = await get_driver_by_tg_id(mock_session, test_tg_id)

    # Assert
    mock_session.execute.assert_called_once()
```

**Conversation Handler Test Pattern:**

```python
@pytest.mark.asyncio
async def test_start_handler_returns_awaiting_language_state():
    """Should prompt for language selection on /start."""
    # Arrange
    update = Mock(spec=Update)
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    # Act
    state = await start_handler(update, context)

    # Assert
    assert state == AWAITING_LANGUAGE
    update.message.reply_text.assert_called_once()
```

**Arrange-Act-Assert Pattern:**
- Arrange: Set up test data, mocks, fixtures
- Act: Call the function under test
- Assert: Verify behavior and side effects

## Fixtures and Factories (Recommended Structure)

**Test Data Factory Pattern:**

```python
# tests/fixtures/factories.py
import factory
from src.db.models import Driver, Vehicle, Trip

class DriverFactory(factory.Factory):
    class Meta:
        model = Driver

    id = factory.Sequence(lambda n: n)
    tg_id = factory.Sequence(lambda n: 100000 + n)
    name = "Test Driver"
    phone = "+1234567890"
    language = "ru"
    status = "ACTIVE"

class VehicleFactory(factory.Factory):
    class Meta:
        model = Vehicle

    id = factory.Sequence(lambda n: n)
    license_plate = factory.Sequence(lambda n: f"ABC{100+n}")
    status = "AVAILABLE"

class TripFactory(factory.Factory):
    class Meta:
        model = Trip

    id = factory.Sequence(lambda n: n)
    driver_id = factory.SubFactory(DriverFactory)
    vehicle_id = factory.SubFactory(VehicleFactory)
    status = "ACTIVE"
    start_odometer = 1000
```

**Database Fixture Pattern:**

```python
# tests/conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.db.models import Base

@pytest.fixture
async def test_db():
    """Create in-memory SQLite database for tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession)

    async with async_session() as session:
        yield session

    await engine.dispose()
```

## Mocking

**Framework:** `unittest.mock` and `pytest-mock` (recommended)

**What to Mock:**
- Telegram `Update` and `ContextTypes` objects (external Telegram API)
- Database sessions in unit tests (test CRUD logic in isolation)
- `async_session` factory when testing handlers (avoid real DB operations)
- External API calls (if future integrations added)

**What NOT to Mock:**
- SQLAlchemy model classes themselves
- Translation helper functions (test with real translation data)
- Application configuration/settings (use test config instead)
- Internal async/await patterns (use `pytest-asyncio` instead)

**Mocking Pattern Examples:**

```python
# Mock Telegram update
from unittest.mock import Mock
from telegram import Update

update = Mock(spec=Update)
update.effective_user.id = 12345
update.message.text = "Test input"
update.message.reply_text = AsyncMock()

# Mock async session
mock_session = AsyncMock()
mock_result = Mock()
mock_result.scalars().first.return_value = driver_instance
mock_session.execute.return_value = mock_result
```

## Coverage

**Requirements:** Not enforced currently

**When tests are added, target:**
- Unit test coverage: 80%+ for `src/db/crud.py` (database operations)
- Integration test coverage: 70%+ for conversation handlers
- Critical paths: 100% (registration, trip open/close, expense creation)

**View Coverage (once pytest installed):**
```bash
pip install pytest-cov
pytest --cov=src --cov=antigravity_modules --cov-report=html
open htmlcov/index.html
```

## Test Types (When Implemented)

**Unit Tests:**
- Scope: Individual functions in isolation
- Files affected: `src/db/crud.py`, translation helper functions
- Mock external dependencies: Database, Telegram
- Example: Test `create_driver()` with mocked session

**Integration Tests:**
- Scope: Multi-step flows and handler chains
- Files affected: `antigravity_modules/` conversation handlers
- Use: Test fixtures with real models
- Example: Test full expense flow from /add_expense to completion

**End-to-End Tests (Not implemented):**
- Scope: Full user journeys through bot
- Would require: Test Telegram client or mock bot dispatcher
- Examples: Registration → Open Trip → Add Expense → Close Trip

## Async Testing Pattern

**Key Pattern for this codebase:**

All database operations and Telegram handlers are async. Tests must handle this:

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_create_driver_saves_to_database():
    """Should save driver and return with id."""
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    result = await create_driver(
        mock_session,
        tg_id=123,
        name="John",
        phone="123456"
    )

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once()
    assert result.tg_id == 123
```

**pytest-asyncio Configuration:**

```python
# pyproject.toml or pytest.ini (when created)
[tool:pytest]
asyncio_mode = auto
addopts = -v --strict-markers
markers =
    asyncio: marks tests as async
```

## Error Testing Pattern

**Testing validation errors:**

```python
@pytest.mark.asyncio
async def test_receive_expense_amount_returns_same_state_on_invalid_amount():
    """Should re-prompt for amount if input is not numeric."""
    update = Mock(spec=Update)
    update.message.text = "not_a_number"

    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {'lang': 'ru'}

    result = await receive_expense_amount(update, context)

    assert result == AWAITING_EXPENSE_AMOUNT
    update.message.reply_text.assert_called_once()
```

**Testing missing preconditions:**

```python
@pytest.mark.asyncio
async def test_add_expense_handler_returns_end_if_no_active_trip():
    """Should end conversation if driver has no active trip."""
    # Mock: driver exists, but no active trip
    mock_session = AsyncMock()

    update = Mock(spec=Update)
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}

    result = await add_expense_handler(update, context)

    assert result == ConversationHandler.END
    update.message.reply_text.assert_called_once()
```

## Current Code Testability Assessment

**Easy to Test:**
- `src/db/crud.py`: Pure async functions with simple signatures, easy to mock session
- `src/db/models.py`: SQLAlchemy ORM models (structural, not behavioral)
- `antigravity_modules/translations.py`: Pure functions, no I/O

**Moderate to Test:**
- Conversation handlers in `antigravity_modules/`: Require Update/Context mocks, async patterns
- State transitions: Need to verify conversation handler configuration

**Hard to Test (Currently):**
- Full handler chains: Would need comprehensive mock setup
- Photo/document file handling: Requires mocking Telegram file objects

## Recommended Priority for Tests (When Adding)

1. **High Priority - CRUD Operations** (`src/db/crud.py`)
   - `test_get_driver_by_tg_id_*` - 2 tests (found, not found)
   - `test_create_driver_*` - 2 tests (success, with defaults)
   - `test_get_vehicle_by_plate_*` - 2 tests
   - `test_create_vehicle_*` - 1 test
   - Estimated: 7 tests

2. **High Priority - Translation Helper** (`antigravity_modules/translations.py`)
   - `test_get_text_returns_translation_for_valid_key` - 1 test
   - `test_get_text_formats_with_kwargs` - 1 test
   - `test_get_text_defaults_to_russian` - 1 test
   - `test_get_main_menu_includes_trip_actions_when_active` - 2 tests
   - Estimated: 5 tests

3. **Medium Priority - Handler Entry Points** (`antigravity_modules/expense_flow.py`, etc.)
   - `test_{handler}_returns_end_without_registration` - per handler
   - `test_{handler}_returns_end_without_active_trip` - per handler
   - Estimated: 6 tests (one per conversation flow)

4. **Medium Priority - State Transitions**
   - `test_conversation_handler_configuration` - verify states are correct
   - Estimated: 4 tests (one per flow)

---

*Testing analysis: 2026-03-08*
