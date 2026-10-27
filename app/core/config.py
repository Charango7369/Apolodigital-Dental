from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"

class Settings(BaseSettings):
    PROJECT_NAME: str = "Dental SaaS"
    ENVIRONMENT: str = "development"

    DATABASE_URL: str

    JWT_SECRET: str
    JWT_REFRESH_SECRET: str

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    CORS_ORIGINS: list[str] = ["*"]

    # WhatsApp Cloud API (Meta Graph API)
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_API_VERSION: str = "v20.0"

    model_config = ConfigDict(
        env_file=[str(ENV_PATH), ".env"],
        extra="ignore"
    )


settings = Settings()
