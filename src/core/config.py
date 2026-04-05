import logging

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


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
    ADMIN_PASSWORD: str = ""          # Plaintext — auto-hashed at startup if ADMIN_PASSWORD_HASH not set
    ADMIN_PASSWORD_HASH: str = ""     # Preferred: pre-computed bcrypt hash

    # Director Telegram ID for anomaly digest notifications (ALERT-04)
    DIRECTOR_TG_ID: int = 0  # Set to actual director's Telegram user ID in env

    # OpenAI for AI receipt parsing
    OPENAI_API_KEY: str = ""  # GPT-4 Vision for auto-parsing fuel receipts

    @property
    def async_database_url(self) -> str:
        """Convert Railway's postgresql:// to postgresql+asyncpg:// for asyncpg driver."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @model_validator(mode="after")
    def _warn_insecure_defaults(self) -> "Settings":
        if self.JWT_SECRET_KEY == "change-in-production":
            if self.DATABASE_URL.startswith("postgresql"):
                raise ValueError(
                    "SECURITY: JWT_SECRET_KEY is set to the insecure default 'change-in-production'. "
                    "Refusing to start with PostgreSQL. "
                    "Generate a key: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            logger.warning(
                "SECURITY: JWT_SECRET_KEY is set to the default value. "
                "Set a strong random secret via the JWT_SECRET_KEY env var before going to production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if self.ADMIN_PASSWORD_HASH and not self.ADMIN_PASSWORD_HASH.startswith("$2"):
            # ADMIN_PASSWORD_HASH was set to a plaintext value — auto-hash it
            from pwdlib import PasswordHash
            from pwdlib.hashers.bcrypt import BcryptHasher
            self.ADMIN_PASSWORD_HASH = PasswordHash((BcryptHasher(),)).hash(self.ADMIN_PASSWORD_HASH)
            logger.info("ADMIN_PASSWORD_HASH was plaintext — auto-hashed.")
        elif not self.ADMIN_PASSWORD_HASH and self.ADMIN_PASSWORD:
            from pwdlib import PasswordHash
            from pwdlib.hashers.bcrypt import BcryptHasher
            self.ADMIN_PASSWORD_HASH = PasswordHash((BcryptHasher(),)).hash(self.ADMIN_PASSWORD)
            logger.info("ADMIN_PASSWORD_HASH auto-generated from ADMIN_PASSWORD.")
        elif not self.ADMIN_PASSWORD_HASH and not self.ADMIN_PASSWORD:
            logger.warning(
                "SECURITY: Neither ADMIN_PASSWORD nor ADMIN_PASSWORD_HASH is set — "
                "admin panel login will be disabled. Set ADMIN_PASSWORD=yourpassword in env vars."
            )
        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
