---
phase: 01-infrastructure-and-foundation
plan: 04
type: execute
wave: 2
depends_on:
  - "01-01"
files_modified:
  - src/services/r2.py
  - antigravity_modules/expense_flow.py
  - src/db/models.py
  - alembic/versions/phase1_add_photo_r2_url.py
autonomous: true
requirements:
  - INFRA-03
user_setup:
  - service: cloudflare-r2
    why: "Durable photo storage for expense receipts"
    env_vars:
      - name: R2_ACCOUNT_ID
        source: "Cloudflare Dashboard -> R2 -> Overview -> Account ID (top right)"
      - name: R2_ACCESS_KEY_ID
        source: "Cloudflare Dashboard -> R2 -> Manage R2 API Tokens -> Create API Token -> R2 Token (read+write)"
      - name: R2_SECRET_ACCESS_KEY
        source: "Same token creation page — shown once at creation"
      - name: R2_BUCKET_NAME
        source: "Set to the bucket name you create (see dashboard_config below)"
    dashboard_config:
      - task: "Create R2 bucket"
        location: "Cloudflare Dashboard -> R2 -> Create Bucket -> name: freight-tms-photos (or your choice), region: auto"

must_haves:
  truths:
    - "A receipt photo sent through the bot is uploaded to Cloudflare R2 and stored as a URL (not Telegram file_id)"
    - "The R2 URL is stored in Expense.photo_r2_url column (not the old photo_file_id)"
    - "Photo upload runs in a thread executor so it does not block the asyncio event loop"
    - "If R2 credentials are not set, photo upload logs a warning and stores None (no crash)"
  artifacts:
    - path: "src/services/r2.py"
      provides: "get_r2_client() and upload_photo_to_r2() using boto3"
      contains: "upload_fileobj"
    - path: "antigravity_modules/expense_flow.py"
      provides: "receive_expense_photo() downloads from Telegram and uploads to R2"
      contains: "upload_photo_to_r2"
    - path: "src/db/models.py"
      provides: "Expense.photo_r2_url String column"
      contains: "photo_r2_url"
    - path: "alembic/versions/phase1_add_photo_r2_url.py"
      provides: "Migration adding photo_r2_url column to expenses table"
      contains: "photo_r2_url"
  key_links:
    - from: "antigravity_modules/expense_flow.py receive_expense_photo()"
      to: "src/services/r2.py upload_photo_to_r2()"
      via: "asyncio.get_event_loop().run_in_executor(None, upload_sync)"
      pattern: "run_in_executor"
    - from: "src/services/r2.py get_r2_client()"
      to: "Cloudflare R2 endpoint"
      via: "boto3 s3 client with endpoint_url=https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
      pattern: "r2.cloudflarestorage.com"
---

<objective>
Create the Cloudflare R2 upload service and wire it into the expense flow so receipt photos are stored durably in R2 rather than as ephemeral Telegram file IDs.

Purpose: Phase 1 success criterion 3 explicitly requires photos retrievable by URL from durable storage. Telegram file_ids expire; R2 URLs do not.
Output: src/services/r2.py with boto3 client; expense_flow.py updated to download+upload photos; new Expense.photo_r2_url DB column with migration.
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
@.planning/phases/01-infrastructure-and-foundation/01-01-SUMMARY.md
@src/services/r2.py
@antigravity_modules/expense_flow.py
@src/db/models.py
@antigravity_modules/expense_crud.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create R2 upload service and add photo_r2_url to Expense model</name>
  <files>src/services/r2.py, src/db/models.py, alembic/versions/phase1_add_photo_r2_url.py</files>
  <action>
  Create the directory src/services/ if it doesn't exist, then create src/services/__init__.py (empty) and src/services/r2.py:

  ```python
  # src/services/r2.py
  import io
  import logging
  from functools import partial
  from typing import Optional

  import boto3
  from botocore.config import Config
  from botocore.exceptions import BotoCoreError, ClientError

  from src.core.config import settings

  logger = logging.getLogger(__name__)


  def _get_r2_client():
      """Create a synchronous boto3 S3 client configured for Cloudflare R2."""
      return boto3.client(
          service_name="s3",
          endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
          aws_access_key_id=settings.R2_ACCESS_KEY_ID,
          aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
          region_name="auto",  # Required by SDK, ignored by R2
          config=Config(signature_version="s3v4"),
      )


  def _upload_sync(file_bytes: bytes, key: str) -> str:
      """Synchronous upload — runs in thread executor to avoid blocking asyncio."""
      client = _get_r2_client()
      client.upload_fileobj(
          io.BytesIO(file_bytes),
          settings.R2_BUCKET_NAME,
          key,
          ExtraArgs={"ContentType": "image/jpeg"},
      )
      return f"https://{settings.R2_BUCKET_NAME}.{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com/{key}"


  async def upload_photo_to_r2(file_bytes: bytes, key: str) -> Optional[str]:
      """Upload photo bytes to R2. Returns public URL or None if R2 not configured.

      IMPORTANT: boto3 is synchronous. This function uses run_in_executor to avoid
      blocking the asyncio event loop during upload.
      """
      if not settings.R2_ACCOUNT_ID or not settings.R2_ACCESS_KEY_ID or not settings.R2_SECRET_ACCESS_KEY:
          logger.warning("R2 credentials not configured — skipping photo upload, storing None.")
          return None

      import asyncio
      loop = asyncio.get_event_loop()
      try:
          url = await loop.run_in_executor(None, partial(_upload_sync, file_bytes, key))
          logger.info(f"Photo uploaded to R2: {url}")
          return url
      except (BotoCoreError, ClientError) as e:
          logger.error(f"R2 upload failed for key {key}: {e}")
          return None
  ```

  In src/db/models.py, add `photo_r2_url` column to the Expense class. Find the existing `photo_file_id` line and add after it:
  ```python
  photo_r2_url = Column(String, nullable=True)  # R2 durable storage URL (replaces Telegram file_id for receipts)
  ```
  Keep `photo_file_id` column — do not remove it (backward compatibility with existing data if any).

  Create the Alembic migration. Run:
  ```bash
  alembic revision -m "phase1_add_photo_r2_url"
  ```
  Then edit the generated file to contain:
  ```python
  def upgrade() -> None:
      op.add_column('expenses',
          sa.Column('photo_r2_url', sa.String(), nullable=True)
      )

  def downgrade() -> None:
      op.drop_column('expenses', 'photo_r2_url')
  ```
  </action>
  <verify>
  Run: `python -c "from src.services.r2 import upload_photo_to_r2; print('ok')"` — imports without error.
  Run: `python -c "from src.db.models import Expense; e = Expense(); print(hasattr(e, 'photo_r2_url'))"` — prints True.
  Run: `alembic history` — new phase1_add_photo_r2_url migration appears after phase1_add_vehicle_link migration.
  Run: `python -c "from src.services.r2 import upload_photo_to_r2; import inspect; src = inspect.getsource(upload_photo_to_r2); print('run_in_executor' in src)"` — prints True.
  </verify>
  <done>src/services/r2.py exists with upload_photo_to_r2() that uses run_in_executor. Expense model has photo_r2_url column. Alembic migration for photo_r2_url exists in history chain.</done>
</task>

<task type="auto">
  <name>Task 2: Wire R2 upload into expense_flow photo receipt step</name>
  <files>antigravity_modules/expense_flow.py</files>
  <action>
  Update antigravity_modules/expense_flow.py to download the photo from Telegram and upload it to R2.

  **Step 1: Add import at top of file** (after existing imports):
  ```python
  import uuid
  from src.services.r2 import upload_photo_to_r2
  ```

  **Step 2: Replace receive_expense_photo() function body**

  Current version stores `context.user_data['photo_id'] = update.message.photo[-1].file_id` (Telegram file ID).

  Replace the entire `receive_expense_photo()` function with:
  ```python
  async def receive_expense_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
      lang = context.user_data.get('lang', 'ru')

      if update.message.photo:
          tg_file = await update.message.photo[-1].get_file()
      elif update.message.document:
          tg_file = await update.message.document.get_file()
      else:
          await update.message.reply_text(get_text(lang, "exp_ask_photo"))
          return AWAITING_EXPENSE_PHOTO

      # Download photo bytes from Telegram servers
      file_bytes = await tg_file.download_as_bytearray()

      # Generate unique R2 key: receipts/{trip_id}/{uuid}.jpg
      trip_id = context.user_data.get('trip_id', 'unknown')
      key = f"receipts/{trip_id}/{uuid.uuid4()}.jpg"

      # Upload to R2 (runs in thread executor, non-blocking)
      r2_url = await upload_photo_to_r2(bytes(file_bytes), key)
      context.user_data['photo_r2_url'] = r2_url
      # Keep legacy photo_id for backward compat during transition
      context.user_data['photo_id'] = tg_file.file_id

      await update.message.reply_text(
          get_text(lang, "exp_ask_card_photo")
      )
      return AWAITING_EXPENSE_CARD_PHOTO
  ```

  **Step 3: Update skip_photo() to set photo_r2_url = None**
  Add to skip_photo():
  ```python
  context.user_data['photo_r2_url'] = None
  ```
  (Add after `context.user_data['photo_id'] = None`)

  **Step 4: Update process_final_expense() to pass photo_r2_url to create_expense()**

  Find the `await create_expense(...)` call in `process_final_expense()`. Add `photo_r2_url` to the call:
  ```python
  photo_r2_url = context.user_data.get('photo_r2_url')

  async with async_session() as session:
      await create_expense(
          session=session,
          trip_id=trip_id,
          expense_type=expense_type,
          amount=amount,
          currency=currency,
          photo_file_id=photo_id,
          card_photo_file_id=card_photo_id,
          comment=comment,
          photo_r2_url=photo_r2_url,  # New R2 URL field
      )
  ```

  **Step 5: Update create_expense() in expense_crud.py to accept and store photo_r2_url**

  Read antigravity_modules/expense_crud.py and add `photo_r2_url: str = None` parameter to `create_expense()`, then include it in the `Expense(...)` constructor call:
  ```python
  expense = Expense(
      trip_id=trip_id,
      expense_type=expense_type,
      amount=amount,
      currency=currency,
      photo_file_id=photo_file_id,
      card_photo_file_id=card_photo_file_id,
      comment=comment,
      photo_r2_url=photo_r2_url,  # Add this
  )
  ```
  </action>
  <verify>
  Run: `python -c "from antigravity_modules.expense_flow import receive_expense_photo; import inspect; src = inspect.getsource(receive_expense_photo); print('upload_photo_to_r2' in src)"` — prints True.
  Run: `python -c "from antigravity_modules.expense_flow import get_expense_conversation_handler; h = get_expense_conversation_handler(); print('ok')"` — no error.
  Grep: `grep -n "photo_r2_url" antigravity_modules/expense_flow.py` — matches in receive_expense_photo, skip_photo, process_final_expense.
  Grep: `grep -n "run_in_executor\|upload_photo_to_r2" antigravity_modules/expense_flow.py` — matches (via import and usage).
  </verify>
  <done>expense_flow.py imports upload_photo_to_r2. receive_expense_photo() downloads photo bytes from Telegram then calls upload_photo_to_r2(). photo_r2_url stored in user_data and passed to create_expense(). expense_crud.py create_expense() accepts and stores photo_r2_url in Expense model.</done>
</task>

</tasks>

<verification>
1. `python -c "from src.services.r2 import upload_photo_to_r2"` — no ImportError
2. `python -c "from src.db.models import Expense; print(Expense.photo_r2_url)"` — Column attribute exists
3. `alembic history` — phase1_add_photo_r2_url migration in chain
4. `grep "run_in_executor" src/services/r2.py` — matches (confirms non-blocking upload)
5. `grep "upload_photo_to_r2" antigravity_modules/expense_flow.py` — matches (import + usage)
6. `grep "photo_r2_url" antigravity_modules/expense_crud.py` — matches in create_expense signature and Expense() constructor
</verification>

<success_criteria>
- src/services/r2.py created with upload_photo_to_r2() using run_in_executor for non-blocking boto3 calls
- Expense.photo_r2_url column added to model and Alembic migration created
- receive_expense_photo() downloads bytes from Telegram via get_file().download_as_bytearray() and uploads to R2
- R2 URL (or None if credentials missing) stored in Expense record, not just Telegram file_id
- No crash if R2 credentials absent — graceful fallback with warning log
</success_criteria>

<output>
After completion, create `.planning/phases/01-infrastructure-and-foundation/01-04-SUMMARY.md`
</output>
