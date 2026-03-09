---
phase: 02-expense-control
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/db/models.py
  - src/core/config.py
  - requirements.txt
  - alembic/versions/phase2_expense_control_schema.py
autonomous: true
requirements:
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

must_haves:
  truths:
    - "Expense model has status, approved_by, approved_at, rejection_comment, liters, odometer_reading, station, fx_rate, amount_kzt, idempotency_minute columns"
    - "FuelAnomaly table exists with expense_id, vehicle_id, trip_id, actual_per_100km, norm_per_100km, excess_percent, is_false_alarm, notified columns"
    - "UniqueConstraint uq_expense_idempotent exists on (trip_id, expense_type, amount, idempotency_minute)"
    - "Settings has DIRECTOR_TG_ID field"
    - "APScheduler is declared in requirements.txt"
    - "Alembic migration runs without errors against existing PostgreSQL schema"
  artifacts:
    - path: "src/db/models.py"
      provides: "Updated Expense model + new FuelAnomaly model"
      contains: "FuelAnomaly"
    - path: "src/core/config.py"
      provides: "DIRECTOR_TG_ID setting"
      contains: "DIRECTOR_TG_ID"
    - path: "alembic/versions/phase2_expense_control_schema.py"
      provides: "Migration adding all new columns and fuel_anomalies table"
      contains: "fuel_anomalies"
  key_links:
    - from: "src/db/models.py"
      to: "alembic/versions/phase2_expense_control_schema.py"
      via: "Alembic autogenerate or manual migration matching model definition"
      pattern: "uq_expense_idempotent"
    - from: "src/db/models.py Expense"
      to: "FuelAnomaly.expense_id FK"
      via: "ForeignKey('expenses.id')"
      pattern: "ForeignKey.*expenses"
---

<objective>
Add all Phase 2 schema columns to the expenses table and create the fuel_anomalies table. Add DIRECTOR_TG_ID to settings and APScheduler to requirements. This migration is the serial gate — all Wave 2 and Wave 3 plans depend on these columns existing in the database.

Purpose: Without odometer_reading, liters, status, fx_rate, idempotency_minute, and the FuelAnomaly table, none of the Phase 2 bot flows, approval queue, or anomaly detection can be built or tested end-to-end.
Output: Updated models.py, updated config.py, updated requirements.txt, new Alembic migration file.
</objective>

<execution_context>
@/Users/osmagulov/.claude/get-shit-done/workflows/execute-plan.md
@/Users/osmagulov/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/02-expense-control/02-RESEARCH.md
@src/db/models.py
@src/core/config.py
@requirements.txt
@alembic/env.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Extend Expense model and add FuelAnomaly model</name>
  <files>src/db/models.py</files>
  <action>
  Read src/db/models.py first. Then make the following additions:

  1. Add import at top of file (after existing imports):
     ```python
     from sqlalchemy import UniqueConstraint
     ```

  2. In the Expense class, add new columns after the existing `comment` column and before `created_at`:
     ```python
     # Approval workflow (EAPPR-01, EAPPR-02)
     status = Column(String, default="PENDING", nullable=False)
     approved_by = Column(String, nullable=True)          # dispatcher username from JWT
     approved_at = Column(DateTime(timezone=True), nullable=True)
     rejection_comment = Column(String, nullable=True)

     # Fuel-specific fields (EXP-01, EXP-02)
     liters = Column(Float, nullable=True)
     odometer_reading = Column(Integer, nullable=True)
     station = Column(String, nullable=True)

     # Multi-currency normalization (EXP-07)
     fx_rate = Column(Float, nullable=True)               # rate to KZT at submission time
     amount_kzt = Column(Float, nullable=True)            # normalized amount in KZT

     # Idempotency (EXP-08)
     idempotency_minute = Column(DateTime(timezone=True), nullable=True)
     ```

  3. Add `__table_args__` to the Expense class (after all column definitions, before `trip = relationship(...)`):
     ```python
     __table_args__ = (
         UniqueConstraint(
             'trip_id', 'expense_type', 'amount', 'idempotency_minute',
             name='uq_expense_idempotent'
         ),
     )
     ```

  4. Add the FuelAnomaly class as a new model after the Expense class:
     ```python
     class FuelAnomaly(Base):
         __tablename__ = "fuel_anomalies"

         id = Column(Integer, primary_key=True, index=True)
         expense_id = Column(Integer, ForeignKey("expenses.id"), nullable=False)
         vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
         trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)

         actual_per_100km = Column(Float, nullable=False)
         norm_per_100km = Column(Float, nullable=False)
         threshold_per_100km = Column(Float, nullable=False)
         excess_percent = Column(Float, nullable=False)

         is_false_alarm = Column(Boolean, default=False, nullable=False)
         notified = Column(Boolean, default=False, nullable=False)

         created_at = Column(DateTime(timezone=True), server_default=func.now())

         expense = relationship("Expense")
         vehicle = relationship("Vehicle")
         trip = relationship("Trip")
     ```

  NOTE: The existing `ExpenseType` enum already has FUEL, PER_DIEM, FINE, REPAIR, OTHER — do NOT add PARTS, FERRY, CUSTOMS (decided: use OTHER + comment field for sub-types).
  </action>
  <verify>
  Run: `python -c "from src.db.models import Expense, FuelAnomaly; e = Expense(); print(hasattr(e, 'status'), hasattr(e, 'odometer_reading'), hasattr(e, 'fx_rate'), hasattr(e, 'idempotency_minute'))"`
  Expected: True True True True

  Run: `python -c "from src.db.models import FuelAnomaly; a = FuelAnomaly(); print(hasattr(a, 'excess_percent'), hasattr(a, 'is_false_alarm'), hasattr(a, 'notified'))"`
  Expected: True True True
  </verify>
  <done>Expense model has all 10 new columns (status, approved_by, approved_at, rejection_comment, liters, odometer_reading, station, fx_rate, amount_kzt, idempotency_minute) plus __table_args__ with UniqueConstraint. FuelAnomaly model exists with all columns and relationships. No import errors.</done>
</task>

<task type="auto">
  <name>Task 2: Add DIRECTOR_TG_ID to settings, APScheduler to requirements, and create Alembic migration</name>
  <files>src/core/config.py, requirements.txt, alembic/versions/phase2_expense_control_schema.py</files>
  <action>
  Step A — src/core/config.py:
  Read the file. Add one new field to the Settings class after the existing ADMIN_PASSWORD_HASH field:
  ```python
  # Director Telegram ID for anomaly digest notifications (ALERT-04)
  DIRECTOR_TG_ID: int = 0  # Set to actual director's Telegram user ID in env
  ```

  Step B — requirements.txt:
  Read the file. Add the following line after the existing entries (APScheduler is already installed in the venv as 3.11.2 but not yet declared in requirements.txt):
  ```
  APScheduler>=3.10.0
  ```

  Step C — Alembic migration:
  Run: `alembic revision -m "phase2_expense_control_schema"` to create a new migration file.
  Then edit the generated file (it will be in alembic/versions/ with a hash prefix) to contain exactly:

  ```python
  """phase2_expense_control_schema

  Revision ID: (keep generated)
  Revises: (keep generated — points to phase1 migration)
  Create Date: (keep generated)
  """
  from alembic import op
  import sqlalchemy as sa

  def upgrade() -> None:
      # Add new columns to expenses table
      op.add_column('expenses', sa.Column('status', sa.String(), nullable=False, server_default='PENDING'))
      op.add_column('expenses', sa.Column('approved_by', sa.String(), nullable=True))
      op.add_column('expenses', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
      op.add_column('expenses', sa.Column('rejection_comment', sa.String(), nullable=True))
      op.add_column('expenses', sa.Column('liters', sa.Float(), nullable=True))
      op.add_column('expenses', sa.Column('odometer_reading', sa.Integer(), nullable=True))
      op.add_column('expenses', sa.Column('station', sa.String(), nullable=True))
      op.add_column('expenses', sa.Column('fx_rate', sa.Float(), nullable=True))
      op.add_column('expenses', sa.Column('amount_kzt', sa.Float(), nullable=True))
      op.add_column('expenses', sa.Column('idempotency_minute', sa.DateTime(timezone=True), nullable=True))
      op.create_unique_constraint(
          'uq_expense_idempotent',
          'expenses',
          ['trip_id', 'expense_type', 'amount', 'idempotency_minute']
      )

      # Create fuel_anomalies table
      op.create_table(
          'fuel_anomalies',
          sa.Column('id', sa.Integer(), nullable=False),
          sa.Column('expense_id', sa.Integer(), nullable=False),
          sa.Column('vehicle_id', sa.Integer(), nullable=False),
          sa.Column('trip_id', sa.Integer(), nullable=False),
          sa.Column('actual_per_100km', sa.Float(), nullable=False),
          sa.Column('norm_per_100km', sa.Float(), nullable=False),
          sa.Column('threshold_per_100km', sa.Float(), nullable=False),
          sa.Column('excess_percent', sa.Float(), nullable=False),
          sa.Column('is_false_alarm', sa.Boolean(), nullable=False, server_default='false'),
          sa.Column('notified', sa.Boolean(), nullable=False, server_default='false'),
          sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
          sa.ForeignKeyConstraint(['expense_id'], ['expenses.id']),
          sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id']),
          sa.ForeignKeyConstraint(['trip_id'], ['trips.id']),
          sa.PrimaryKeyConstraint('id'),
      )
      op.create_index(op.f('ix_fuel_anomalies_id'), 'fuel_anomalies', ['id'], unique=False)

  def downgrade() -> None:
      op.drop_index(op.f('ix_fuel_anomalies_id'), table_name='fuel_anomalies')
      op.drop_table('fuel_anomalies')
      op.drop_constraint('uq_expense_idempotent', 'expenses', type_='unique')
      op.drop_column('expenses', 'idempotency_minute')
      op.drop_column('expenses', 'amount_kzt')
      op.drop_column('expenses', 'fx_rate')
      op.drop_column('expenses', 'station')
      op.drop_column('expenses', 'odometer_reading')
      op.drop_column('expenses', 'liters')
      op.drop_column('expenses', 'rejection_comment')
      op.drop_column('expenses', 'approved_at')
      op.drop_column('expenses', 'approved_by')
      op.drop_column('expenses', 'status')
  ```

  NOTE: Do NOT run `alembic upgrade head` locally — migration runs in Railway's pre-deploy hook. Just confirm the file is created and appears in `alembic history`.
  </action>
  <verify>
  Run: `python -c "from src.core.config import settings; print(settings.DIRECTOR_TG_ID)"` — should print 0 (default).

  Run: `grep -n "APScheduler" requirements.txt` — should show the line.

  Run: `alembic history` — new phase2_expense_control_schema migration must appear at the top of the chain, after the phase1 migration.
  </verify>
  <done>Settings has DIRECTOR_TG_ID field (default 0). requirements.txt declares APScheduler>=3.10.0. Alembic migration file exists at alembic/versions/phase2_expense_control_schema.py with correct upgrade/downgrade covering all 10 new expense columns, UniqueConstraint, and full fuel_anomalies table. Migration appears at top of alembic history chain.</done>
</task>

</tasks>

<verification>
1. `python -c "from src.db.models import Expense, FuelAnomaly; print('models ok')"` — no ImportError
2. `python -c "from src.db.models import Expense; e = Expense(); print(e.status)"` — prints PENDING
3. `python -c "from src.core.config import settings; print(settings.DIRECTOR_TG_ID)"` — prints 0
4. `grep "APScheduler" requirements.txt` — shows APScheduler>=3.10.0
5. `alembic history` — phase2 migration at top of chain after phase1 migration
6. `python -c "from src.db.models import Expense; print(Expense.__table_args__)"` — shows UniqueConstraint with name uq_expense_idempotent
</verification>

<success_criteria>
- Expense model has status (default PENDING), approved_by, approved_at, rejection_comment, liters, odometer_reading, station, fx_rate, amount_kzt, idempotency_minute
- Expense.__table_args__ contains UniqueConstraint('trip_id', 'expense_type', 'amount', 'idempotency_minute', name='uq_expense_idempotent')
- FuelAnomaly model exists with all columns and FK relationships to expenses, vehicles, trips
- Settings.DIRECTOR_TG_ID field exists and defaults to 0
- requirements.txt includes APScheduler>=3.10.0
- Alembic migration file covers all schema changes with correct upgrade() and downgrade()
</success_criteria>

<output>
After completion, create `.planning/phases/02-expense-control/02-01-SUMMARY.md`
</output>
