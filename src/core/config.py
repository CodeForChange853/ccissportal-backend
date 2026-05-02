# backend-v2/src/core/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  

    # Database 
    DATABASE_URL: str

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5173"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL_ID: str = "gemini-2.0-flash"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()