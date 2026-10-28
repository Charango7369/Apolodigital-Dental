from pathlib import Path
from typing import List, Set
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, field_validator

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"

INSECURE_SECRETS_DENYLIST: Set[str] = {
    "CHANGE_ME",
    "CHANGE_ME_TOO",
    "tu_secreto_super_seguro_cambialo_en_produccion",
    "tu_otro_secreto_para_refresh",
    "SUPER_SECRET_STRING_PARA_APOLO_DENTAL_2026",
    "aeb163ae001b89509920ccdc020e21a38894a2dcff3b3ed7aebad07cd05546d7",  # Leaked in git history
    "9331be588f90bde1e76886b05e5643ebda804009705b8dbaf7f0885aa68263ac",  # Leaked in git history
    "secret",
    "supersecret",
    "admin",
    "password",
}

class Settings(BaseSettings):
    PROJECT_NAME: str = "Dental SaaS"
    ENVIRONMENT: str = "development"

    DATABASE_URL: str

    JWT_SECRET: str
    JWT_REFRESH_SECRET: str

    # FASE 2: Tokens de corta duración (15 min) y rotación RTR (7 días)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MFA_PENDING_EXPIRE_MINUTES: int = 10

    # Caché y Rate Limiting distribuido (Redis opcional con fallback en memoria)
    REDIS_URL: str = ""
    RATE_LIMIT_LOGIN_MAX: int = 5
    RATE_LIMIT_LOGIN_WINDOW_SECONDS: int = 900  # 15 minutos
    RATE_LIMIT_RESET_MAX: int = 5
    RATE_LIMIT_RESET_WINDOW_SECONDS: int = 3600  # 1 hora

    CORS_ORIGINS: List[str] = ["*"]

    # WhatsApp Cloud API (Meta Graph API)
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_API_VERSION: str = "v20.0"

    # Token para sondas CI / Healthchecks sensibles
    CI_SECRET_TOKEN: str = ""

    model_config = ConfigDict(
        env_file=[str(ENV_PATH), ".env"],
        extra="ignore"
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        clean = (v or "").strip()
        if not clean:
            raise ValueError("DATABASE_URL no puede estar vacía.")
        valid_schemes = ("postgresql", "postgresql+asyncpg", "sqlite", "sqlite+aiosqlite")
        if not any(clean.startswith(scheme) for scheme in valid_schemes):
            raise ValueError(f"DATABASE_URL inválida. Debe comenzar con uno de: {valid_schemes}")
        return clean

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        clean = (v or "").strip()
        if len(clean) < 32:
            raise ValueError("JWT_SECRET debe contener al menos 32 caracteres criptográficos (256 bits).")
        if clean in INSECURE_SECRETS_DENYLIST:
            raise ValueError("JWT_SECRET contiene un valor inseguro o filtrado en historial. Debe regenerarse.")
        return clean

    @field_validator("JWT_REFRESH_SECRET")
    @classmethod
    def validate_jwt_refresh_secret(cls, v: str) -> str:
        clean = (v or "").strip()
        if len(clean) < 32:
            raise ValueError("JWT_REFRESH_SECRET debe contener al menos 32 caracteres criptográficos (256 bits).")
        if clean in INSECURE_SECRETS_DENYLIST:
            raise ValueError("JWT_REFRESH_SECRET contiene un valor inseguro o filtrado en historial. Debe regenerarse.")
        return clean


settings = Settings()
