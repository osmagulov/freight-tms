# Coding Conventions

**Analysis Date:** 2026-03-08

## Naming Patterns

**Files:**
- Snake case for module files: `bot_app.py`, `expense_flow.py`, `trip_opening.py`, `trip_closing.py`
- Package/folder names: snake case: `antigravity_modules/`, `src/db/`, `src/core/`, `src/bot/`

**Functions:**
- Snake case for all functions: `get_driver_by_tg_id()`, `create_driver()`, `receive_language()`, `add_expense_handler()`
- Handler functions: Follow pattern `{action}_handler()` for Telegram command handlers (e.g., `start_handler()`, `menu_command_handler()`, `close_trip_handler()`)
- State transition functions: Follow pattern `receive_{state_name}()` for conversation state handlers (e.g., `receive_language()`, `receive_expense_type()`, `receive_route()`)
- Getter/query functions: Prefix with `get_` (e.g., `get_driver_by_tg_id()`, `get_active_trip_for_driver()`)
- Creator/insert functions: Prefix with `create_` (e.g., `create_driver()`, `create_vehicle()`, `create_expense()`)
- Handler factory functions: Prefix with `get_` and suffix with `_handler()` or `_conversation_handler()` (e.g., `get_expense_conversation_handler()`, `get_trip_conversation_handler()`)

**Variables:**
- Snake case for all variables: `tg_id`, `lang_code`, `context.user_data`, `async_session`, `reply_markup`
- Boolean variables: Use descriptive names: `has_active_trip`, `has_trip`, `driver_exists`
- Constants: UPPER_SNAKE_CASE for module-level constants: `AWAITING_LANGUAGE`, `AWAITING_EXPENSE_TYPE`, `AWAITING_ROUTE`

**Types/Classes:**
- PascalCase for class names: `Driver`, `Vehicle`, `Trip`, `Expense`, `LocationUpdate`
- Enum classes: PascalCase for class names, UPPER_SNAKE_CASE for values
  - Example: `TripStatus.ACTIVE`, `ExpenseType.FUEL`, `DriverStatus.PENDING`

## Code Style

**Formatting:**
- No explicit formatter configured (no `.prettierrc`, `.isort.cfg`, or Black config present)
- Lines wrap naturally; code uses reasonable line lengths
- Imports at top of file, organized logically
- Two blank lines between top-level function definitions
- One blank line between methods/logic blocks within functions
- Inline comments used sparingly, mainly for notes/TODOs

**Linting:**
- No linting configuration detected (no `.eslintrc` or `.flake8` present)
- Code follows general PEP 8 conventions:
  - Proper indentation (4 spaces)
  - Meaningful variable names
  - No unused imports
  - Functions have clear responsibilities

## Import Organization

**Order:**
1. Standard library imports (`logging`, `datetime`, `re`, `enum`)
2. Third-party imports (`sqlalchemy`, `telegram`, `pydantic`)
3. Local imports (relative imports from `src` and `antigravity_modules`)

**Examples from codebase:**

```python
# From src/bot/bot_app.py
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from src.core.config import settings
from src.db.database import async_session
from src.db.crud import get_driver_by_tg_id, create_driver, get_vehicle_by_plate, create_vehicle, update_driver_language
from antigravity_modules.trip_opening import get_trip_conversation_handler, open_trip_handler
from antigravity_modules.expense_flow import get_expense_conversation_handler, add_expense_handler
```

**Path Aliases:**
- Absolute imports used consistently: `from src.db.crud import ...`, `from antigravity_modules.translations import ...`
- No alias shortcuts detected; full module paths used throughout

## Error Handling

**Patterns:**
- Try-except blocks for conversion errors (user input parsing)
  - Used in `receive_expense_amount()`: `float(update.message.text.replace(',', '.'))`
  - Used in `receive_start_odometer()` and `receive_end_odometer()`: `int(odometer_text)`
- ValueError exceptions caught when parsing numeric input from Telegram messages
- Graceful fallback: On parse error, re-prompt user with same question state
- Conditional checks for existence before proceeding:
  - Example: `if driver:` before processing; if not found, send "need registration" message
  - Example: `if trip:` before allowing expense/close trip operations

**Error Response Pattern:**
```python
# From receive_expense_amount()
try:
    amount = float(update.message.text.replace(',', '.'))
    context.user_data['amount'] = amount
except ValueError:
    await update.message.reply_text(get_text(lang, "exp_ask_amount"))
    return AWAITING_EXPENSE_AMOUNT  # Stay in same state
```

- Validation errors return user to same conversation state (don't advance)
- All error messages use translation system: `get_text(lang, "key")`
- Missing resources handled via message replies; no exceptions propagate to user

## Logging

**Framework:** `logging` module (Python standard library)

**Patterns:**
- Logger initialized at module top: `logger = logging.getLogger(__name__)`
- Logger declared in every module that performs database or async operations
- Minimal actual logging: logger instances created but rarely used in current code
- Future logging opportunity: database operations, async task completion, error tracking

**Current usage:**
- `src/db/crud.py` line 6: `logger = logging.getLogger(__name__)`
- `src/bot/bot_app.py` line 21: `logger = logging.getLogger(__name__)`
- `antigravity_modules/expense_flow.py` line 18: `logger = logging.getLogger(__name__)`
- Loggers defined but not actively used in MVP

## Comments

**When to Comment:**
- Used for MVP/temporary decisions: "NOTE: MVP doesn't have rigid driver->vehicle relationship yet"
- Used for TODO items marking unfinished work: "TODO: Connect actual vehicle id here correctly"
- Minimal docstring usage; single-line comments preferred for clarifications

**Examples from codebase:**

```python
# From src/bot/bot_app.py line 113
# Note: In a complete flow, we'll want to link Driver and Vehicle.
# But MVP just registers them.

# From antigravity_modules/trip_opening.py line 42
# NOTE: MVP doesn't have a rigid driver->vehicle relationship link in the db yet,
# so we'll just link the new trip to whatever vehicle we can query or ask.
# For now let's just use driver_id=1, vehicle_id=1 for testing if needed
```

**JSDoc/TSDoc:**
- Not used; Python codebase with no type hints or formal docstrings
- Function signatures serve as documentation
- Parameter types can be inferred from usage and SQLAlchemy/Telegram type hints

## Function Design

**Size:**
- Handler functions: 10-30 lines typical (focused on single state transition)
- Conversation factory functions: 10-20 lines (return ConversationHandler with configuration)
- Database functions: 3-10 lines (single query or mutation)
- Main handler chains: 30-50 lines when managing complex workflows

**Parameters:**
- Telegram handlers: Standard pattern `(update: Update, context: ContextTypes.DEFAULT_TYPE)`
- Database queries: `(session: AsyncSession, identifier: type, ...)`
- Pure data functions: Named parameters with type hints (used in SQLAlchemy models)

**Return Values:**
- Handler functions: Return conversation state constant (integer) or `ConversationHandler.END`
- Database functions: Return model instance (e.g., `Driver`), list of models, or `None`
- Query functions: Return single result or `None` (e.g., `get_driver_by_tg_id()` returns `Driver | None`)

## Module Design

**Exports:**
- No explicit `__all__` defined
- Modules export handler factories as public API (e.g., `get_trip_conversation_handler()`)
- CRUD modules export query and mutation functions
- Translation module exports `get_text()` and `get_main_menu()` functions

**Barrel Files:**
- `antigravity_modules/__init__.py` is empty (no re-exports)
- No barrel pattern used; imports are direct from specific modules
- Example direct import: `from antigravity_modules.expense_flow import get_expense_conversation_handler`

## State Management Pattern

**Conversation Handler Usage:**
- ConversationHandler from `python-telegram-bot` manages multi-step flows
- Entry points: Commands or regex message matches
- States: Integer constants (AWAITING_LANGUAGE = 1, etc.)
- Context data: `context.user_data` dictionary stores ephemeral flow state (language, temp form data)
- State transitions: Handler returns next state constant or END
- Cleanup: `context.user_data.clear()` called before returning `ConversationHandler.END`

**Example from expense_flow.py:**
```python
AWAITING_EXPENSE_TYPE = 1
AWAITING_EXPENSE_AMOUNT = 2
AWAITING_EXPENSE_CURRENCY = 3
AWAITING_EXPENSE_PHOTO = 4
AWAITING_EXPENSE_CARD_PHOTO = 5
AWAITING_EXPENSE_COMMENT = 6
```

## Database Access Pattern

**Session Management:**
- Async context manager: `async with async_session() as session:`
- Session imported from `src.db.database`
- Every database operation scoped to `async with` block
- Automatic commit/rollback via context manager

**Query Pattern:**
```python
from sqlalchemy.future import select
result = await session.execute(select(Model).where(condition))
instance = result.scalars().first()  # Single result
```

**Create/Update Pattern:**
```python
model = Model(field=value)
session.add(model)
await session.commit()
await session.refresh(model)  # Reload to get id/defaults
return model
```

## Multilingual Support Pattern

**Translation System:**
- All user-facing strings in `antigravity_modules/translations.py`
- `get_text(lang, key, **kwargs)` function: looks up translated string, formats with kwargs
- Language codes: "ru" (Russian), "kk" (Kazakh)
- Fallback: If language not found, defaults to Russian

**Usage:**
```python
get_text(lang, "exp_ask_type")
get_text(lang, "reg_success", name=name, phone=phone, plate=plate)
```

---

*Convention analysis: 2026-03-08*
