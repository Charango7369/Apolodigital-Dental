from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Dental SaaS"
    ENVIRONMENT: str = "development"

    DB_URL: str

    JWT_SECRET: str
    JWT_REFRESH_SECRET: str

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    CORS_ORIGINS: list[str] = ["*"]

    model_config = ConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()