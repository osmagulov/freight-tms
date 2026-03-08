---
phase: 01-infrastructure-and-foundation
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/core/config.py
  - src/db/models.py
  - src/db/database.py
  - requirements.txt
  - alembic/versions/phase1_add_vehicle_link_and_fields.py
autonomous: true
requirements:
  - INFRA-01
  - INFRA-02

must_haves:
  truths:
    - "Application connects to PostgreSQL when DATABASE_URL is set to postgresql:// format"
    - "Alembic can run 'upgrade head' against PostgreSQL without errors"
    - "Driver model has vehicle_id FK column; Vehicle model has make, model, fuel_norm_per_100km columns"
    - "Settings loads WEBHOOK_URL, R2_*, JWT_SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD_HASH from env"
  artifacts:
    - path: "src/core/config.py"
      provides: "All Phase 1 settings including async_database_url property"
      contains: "async_database_url"
    - path: "src/db/models.py"
      provides: "Driver.vehicle_id FK + Vehicle.make/model/fuel_norm_per_100km"
      contains: "vehicle_id"
    - path: "alembic/versions/phase1_add_vehicle_link_and_fields.py"
      provides: "Migration adding vehicle_id FK to drivers, 3 fields to vehicles"
      contains: "fk_drivers_vehicle_id"
  key_links:
    - from: "src/db/database.py"
      to: "PostgreSQL via asyncpg"
      via: "settings.async_database_url property"
      pattern: "async_database_url"
    - from: "alembic/env.py"
      to: "settings.DATABASE_URL"
      via: "get_url() function"
      pattern: "DATABASE_URL"
---

<objective>
Establish PostgreSQL as the database backend with updated schema supporting driver-vehicle linking and vehicle details. Refactor settings to include all Phase 1 environment variables and add the async_database_url URL transformation needed for asyncpg.

Purpose: All subsequent Wave 2 plans depend on a stable DB connection, correct schema, and complete settings object. This plan is the foundation gate.
Output: Updated config.py, updated models.py, updated database.py using async_database_url, new Alembic migration, updated requirements.txt.
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
@src/core/config.py
@src/db/models.py
@src/db/database.py
@src/db/crud.py
@requirements.txt
@alembic/env.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Extend Settings and fix database URL transformation</name>
  <files>src/core/config.py, src/db/database.py, requirements.txt</files>
  <action>
  In src/core/config.py, replace the existing Settings class with the full Phase 1 version. Keep existing TELEGRAM_BOT_TOKEN and DATABASE_URL fields. Add:

  ```python
  from pydantic_settings import BaseSettings, SettingsConfigDict

  class Settings(BaseSettings):
      # Existing
      TELEGRAM_BOT_TOKEN: str = "replace_me"
      DATABASE_URL: str = "sqlite+aiosqlite:///./data.sqlite3"

      # New in Phase 1
      WEBHOOK_URL: str = ""  # e.g. https://myapp.up.railway.app

      # Cloudflare R2
      R2_ACCOUNT_ID: str = ""
      R2_ACCESS_KEY_ID: str = ""
      R2_SECRET_ACCESS_KEY: str = ""
      R2_BUCKET_NAME: str = "freight-tms-photos"

      # JWT Auth
      JWT_SECRET_KEY: str = "change-in-production"
      JWT_ALGORITHM: str = "HS256"
      JWT_EXPIRE_MINUTES: int = 480  # 8 hours

      # Admin credentials (env-based for Phase 1, no DB table needed)
      ADMIN_USERNAME: str = "dispatcher"
      ADMIN_PASSWORD_HASH: str = ""  # Generate with: python -c "from pwdlib import PasswordHash; print(PasswordHash.recommended().hash('yourpassword'))"

      @property
      def async_database_url(self) -> str:
          """Convert Railway's postgresql:// to postgresql+asyncpg:// for asyncpg driver."""
          url = self.DATABASE_URL
          if url.startswith("postgresql://"):
              return url.replace("postgresql://", "postgresql+asyncpg://", 1)
          return url

      model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

  settings = Settings()
  ```

  In src/db/database.py, change `create_async_engine` to use `settings.async_database_url` instead of `settings.DATABASE_URL`. This is the critical fix: Railway provides `postgresql://` but asyncpg needs `postgresql+asyncpg://`. Read the current file first to understand imports, then update only the engine creation line.

  In requirements.txt, add the following new dependencies after the existing entries:
  ```
  python-jose[cryptography]>=3.3.0
  pwdlib[bcrypt]>=0.2.0
  jinja2>=3.1.0
  python-multipart>=0.0.9
  boto3>=1.35.0
  aiosqlite>=0.20.0
  ```
  Keep all existing requirements unchanged. aiosqlite is kept for local dev fallback.
  </action>
  <verify>
  Run: `python -c "from src.core.config import settings; print(settings.async_database_url)"` — should output the URL unchanged if DATABASE_URL is sqlite format, or with +asyncpg:// if postgresql:// format.
  Run: `python -c "from src.db.database import engine; print(engine.url)"` — should not raise ImportError.
  Run: `pip install -r requirements.txt` — should complete without errors (may skip already-installed packages).
  </verify>
  <done>Settings has async_database_url property that transforms postgresql:// to postgresql+asyncpg://. All 5 new R2/JWT/admin fields are loadable from env. database.py uses async_database_url. pip install succeeds.</done>
</task>

<task type="auto">
  <name>Task 2: Update models and create Phase 1 Alembic migration</name>
  <files>src/db/models.py, src/db/crud.py, alembic/versions/phase1_add_vehicle_link_and_fields.py</files>
  <action>
  In src/db/models.py:
  1. Add `vehicle_id` FK column to the Driver class (after the `created_at` column):
     ```python
     vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
     ```
  2. Add SQLAlchemy relationship to Driver class:
     ```python
     vehicle = relationship("Vehicle", back_populates="drivers")
     ```
  3. Add three new columns to the Vehicle class (after `status`):
     ```python
     make = Column(String, nullable=True)
     model = Column(String, nullable=True)
     fuel_norm_per_100km = Column(Float, nullable=True)
     ```
  4. Add back_populates to Vehicle's drivers relationship:
     ```python
     drivers = relationship("Driver", back_populates="vehicle")
     ```

  In src/db/crud.py, add a new function after create_vehicle:
  ```python
  async def link_driver_to_vehicle(session: AsyncSession, driver_id: int, vehicle_id: int) -> None:
      """Set driver.vehicle_id = vehicle_id. Call after both driver and vehicle are created."""
      result = await session.execute(select(Driver).where(Driver.id == driver_id))
      driver = result.scalars().first()
      if driver:
          driver.vehicle_id = vehicle_id
          session.add(driver)
          await session.commit()
  ```

  Create new migration file. First run `alembic revision --autogenerate -m "phase1_add_vehicle_link_and_fields"` to generate the file, then edit it to ensure it contains exactly:

  ```python
  def upgrade() -> None:
      # Add vehicle_id FK to drivers table
      op.add_column('drivers',
          sa.Column('vehicle_id', sa.Integer(), nullable=True)
      )
      op.create_foreign_key(
          'fk_drivers_vehicle_id', 'drivers', 'vehicles',
          ['vehicle_id'], ['id']
      )
      # Add vehicle detail fields
      op.add_column('vehicles', sa.Column('make', sa.String(), nullable=True))
      op.add_column('vehicles', sa.Column('model', sa.String(), nullable=True))
      op.add_column('vehicles',
          sa.Column('fuel_norm_per_100km', sa.Float(), nullable=True)
      )

  def downgrade() -> None:
      op.drop_constraint('fk_drivers_vehicle_id', 'drivers', type_='foreignkey')
      op.drop_column('drivers', 'vehicle_id')
      op.drop_column('vehicles', 'fuel_norm_per_100km')
      op.drop_column('vehicles', 'model')
      op.drop_column('vehicles', 'make')
  ```

  If autogenerate doesn't work (e.g., no DATABASE_URL set locally), create the migration file manually using `alembic revision -m "phase1_add_vehicle_link_and_fields"` and fill in the upgrade/downgrade functions above.

  NOTE: Do NOT run `alembic upgrade head` here — that runs in Railway's pre-deploy hook, not locally unless PostgreSQL is available. Just ensure the migration file is created correctly.
  </action>
  <verify>
  Run: `python -c "from src.db.models import Driver, Vehicle; d = Driver(); print(hasattr(d, 'vehicle_id'))"` — should print True.
  Run: `python -c "from src.db.models import Vehicle; v = Vehicle(); print(hasattr(v, 'fuel_norm_per_100km'))"` — should print True.
  Run: `alembic history` — should show the new migration at the top of the chain.
  Run: `python -c "from src.db.crud import link_driver_to_vehicle; print('ok')"` — should import without error.
  </verify>
  <done>Driver model has vehicle_id FK column and vehicle relationship. Vehicle model has make, model, fuel_norm_per_100km. crud.py has link_driver_to_vehicle(). New Alembic migration file exists and appears in alembic history. Migration has correct fk_drivers_vehicle_id constraint name.</done>
</task>

</tasks>

<verification>
1. `python -c "from src.core.config import settings; print(settings.async_database_url)"` — prints database URL (transformed if postgresql://)
2. `python -c "from src.db.models import Driver, Vehicle; print(Driver.vehicle_id, Vehicle.fuel_norm_per_100km)"` — no AttributeError
3. `alembic history` — new phase1 migration appears at top
4. `python -c "from src.db.crud import link_driver_to_vehicle"` — imports cleanly
5. `pip install -r requirements.txt --dry-run` — no errors, python-jose, pwdlib, jinja2, boto3 listed
</verification>

<success_criteria>
- settings.async_database_url converts postgresql:// → postgresql+asyncpg:// correctly
- All 9 new settings fields (WEBHOOK_URL, R2_*, JWT_*, ADMIN_*) defined with defaults
- Driver.vehicle_id FK column exists in models and in new Alembic migration
- Vehicle.make, .model, .fuel_norm_per_100km columns exist in models and migration
- link_driver_to_vehicle() function exists in crud.py
- requirements.txt includes python-jose, pwdlib, jinja2, python-multipart, boto3
</success_criteria>

<output>
After completion, create `.planning/phases/01-infrastructure-and-foundation/01-01-SUMMARY.md`
</output>
