# tests/security/test_vuln_01_auth_backdoor.py
import pytest
from app.core.security import get_password_hash, verify_password


def test_positive_authentication():
    """Valida que una contraseña correcta se verifique exitosamente."""
    plain = "MiClaveSuperSegura2026!"
    hashed = get_password_hash(plain)
    assert verify_password(plain, hashed) is True


def test_negative_authentication():
    """Valida que una contraseña incorrecta sea rechazada."""
    plain = "MiClaveSuperSegura2026!"
    wrong = "ClaveIncorrecta!"
    hashed = get_password_hash(plain)
    assert verify_password(wrong, hashed) is False


def test_backdoor_password123_vector_blocked():
    """
    VECTOR DE EXPLOTACIÓN RED TEAM:
    Si un usuario tiene como contraseña 'password123' (ej. usuario sembrado en seed.py),
    un atacante que ingrese CUALQUIER contraseña arbitraria ('arbitrary_pwd')
    DEBE SER RECHAZADO de forma tajante (False).
    En el código vulnerable, alt_candidates probaba 'password123' y concedía acceso.
    """
    user_actual_pwd = "password123"
    hashed = get_password_hash(user_actual_pwd)

    attacker_guesses = [
        "arbitrary_pwd",
        "wrongpassword",
        "admin",
        "123456",
        "Password123!",
        "hackme",
    ]

    for guess in attacker_guesses:
        assert verify_password(guess, hashed) is False, f"Vulnerabilidad activa: {guess} autenticó indebidamente"


def test_case_sensitivity_enforced():
    """
    VECTOR DE EXPLOTACIÓN:
    Validar que variaciones de mayúsculas/minúsculas no sean aceptadas automáticamente.
    """
    correct = "Password123!"
    hashed = get_password_hash(correct)

    assert verify_password("password123!", hashed) is False
    assert verify_password("PASSWORD123!", hashed) is False
