# tests/security/test_vuln_02_secrets_validation.py
import pytest
from pydantic import ValidationError
from app.core.config import Settings


def test_reject_short_jwt_secret():
    """Valida que un secreto menor a 32 caracteres provoque error en startup."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/dental_db",
            JWT_SECRET="short_secret_under_32_chars",
            JWT_REFRESH_SECRET="a" * 64
        )
    assert "JWT_SECRET debe contener al menos 32 caracteres" in str(exc.value)


def test_reject_denylisted_insecure_secrets():
    """Valida que valores conocidos o filtrados en Git sean bloqueados."""
    long_denylisted = [
        "tu_secreto_super_seguro_cambialo_en_produccion",
        "SUPER_SECRET_STRING_PARA_APOLO_DENTAL_2026",
        "aeb163ae001b89509920ccdc020e21a38894a2dcff3b3ed7aebad07cd05546d7", # Leaked in git
    ]
    for bad_secret in long_denylisted:
        with pytest.raises(ValidationError) as exc:
            Settings(
                DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/dental_db",
                JWT_SECRET=bad_secret,
                JWT_REFRESH_SECRET="valid_refresh_secret_" + "a" * 40
            )
        assert "inseguro o filtrado en historial" in str(exc.value)


def test_accept_strong_cryptographic_secrets():
    """Valida que secretos con suficiente entropía sean aceptados normalmente."""
    cfg = Settings(
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/dental_db",
        JWT_SECRET="a" * 64,
        JWT_REFRESH_SECRET="b" * 64
    )
    assert len(cfg.JWT_SECRET) == 64
    assert len(cfg.JWT_REFRESH_SECRET) == 64
