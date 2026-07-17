# backend-v2/src/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # JWT — actual per-role expiry is enforced in security.py; this is the fallback default
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60   # was 1440; role-based overrides in security.py

    # Database
    DATABASE_URL: str

    # CORS — add the production Vercel URL here instead of hardcoding it in main.py
    ALLOWED_ORIGINS: str = "http://localhost:5173"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL_ID: str = "gemini-2.0-flash"

    # One-time DB init endpoint secret — set in .env to enable, leave empty to disable
    INIT_SECRET: str = ""

    # Timezone used by the audit tripwire for off-hours detection
    SYSTEM_TIMEZONE: str = "Asia/Manila"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()