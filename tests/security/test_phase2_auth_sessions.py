# tests/security/test_phase2_auth_sessions.py
"""
Suite de Pruebas Automatizadas de Seguridad - Fase 2:
Reingeniería de Autenticación, Sesiones, Rotación RTR, MFA TOTP y Rate Limiting.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from jose import jwt

import app.models
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_mfa_pending_token,
    decode_token,
    generate_refresh_token_pair,
    hash_token,
    SECRET_KEY,
    ALGORITHM,
)
from app.core.totp import (
    generate_totp_secret,
    get_totp_code,
    verify_totp,
    generate_totp_uri,
)
from app.core.cache import token_cache
from app.core.rate_limiter import rate_limit_storage
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import RefreshToken
from app.modules.auth.service import AuthService
from app.modules.users.models import User as UserModel


# ============================================================================
# 1. PRUEBAS DE ACCESS TOKEN DE CORTA DURACIÓN Y JTI
# ============================================================================

def test_access_token_short_lifespan_15_minutes():
    """Valida que la expiración del Access Token esté fijada estrictamente en 15 minutos."""
    user_id = uuid4()
    tenant_id = uuid4()
    
    token = create_access_token(subject=str(user_id), tenant_id=tenant_id, roles=["DOCTOR"])
    payload = decode_token(token)
    
    assert payload["sub"] == str(user_id)
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["type"] == "access"
    assert "jti" in payload
    
    # Tolerancia de +-2 segundos en el cálculo de tiempo
    lifespan_seconds = payload["exp"] - payload["iat"]
    assert 898 <= lifespan_seconds <= 902, f"Expiración esperada ~900s (15m), obtenida: {lifespan_seconds}s"


@pytest.mark.asyncio
async def test_access_token_jti_revocation():
    """Valida que un Access Token con su JTI registrado en lista de revocación sea denegado."""
    user_id = uuid4()
    tenant_id = uuid4()
    
    token = create_access_token(subject=str(user_id), tenant_id=tenant_id)
    payload = decode_token(token)
    jti = payload["jti"]
    
    # Revocar JTI en caché distribuida
    await token_cache.revoke_token(jti, ttl_seconds=60)
    
    mock_db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=mock_db)
    
    assert exc_info.value.status_code == 401
    assert "revocado" in exc_info.value.detail.lower()


# ============================================================================
# 2. PRUEBAS DE ROTACIÓN DE REFRESH TOKEN (RTR) Y FAMILIAS
# ============================================================================

@pytest.mark.asyncio
async def test_refresh_token_creation_and_rotation_success():
    """
    Valida el ciclo de vida de RTR:
    1. Creación de sesión emite access_token y refresh_token.
    2. Rotación marca el token anterior como revocado y emite uno nuevo con el mismo family_id.
    """
    user_id = uuid4()
    tenant_id = uuid4()
    user = UserModel(
        id=user_id,
        tenant_id=tenant_id,
        full_name="Dr. Rotation Test",
        email="rotation@test.com",
        hashed_password="hash",
        roles=["DOCTOR"],
        is_active=True,
    )
    
    mock_db = AsyncMock()
    added_objects = []
    def fake_add(obj):
        added_objects.append(obj)
    mock_db.add = fake_add

    # Iniciar sesión
    access_token, raw_refresh = await AuthService.create_user_session(mock_db, user)
    assert access_token is not None
    assert raw_refresh is not None
    assert len(added_objects) == 1
    
    first_token_record: RefreshToken = added_objects[0]
    initial_family_id = first_token_record.family_id
    assert first_token_record.is_revoked is False
    
    # Simular consulta de BD devolviendo el primer token
    mock_result_token = MagicMock()
    mock_result_token.scalar_one_or_none.return_value = first_token_record
    
    mock_result_user = MagicMock()
    mock_result_user.scalar_one_or_none.return_value = user

    mock_db.execute.side_effect = [mock_result_token, mock_result_user]
    
    # Ejecutar rotación RTR
    new_access, new_refresh, returned_user = await AuthService.rotate_refresh_token(
        db=mock_db,
        raw_refresh_token=raw_refresh,
        client_ip="192.168.1.50",
    )
    
    # 1. El token anterior DEBE estar marcado como revocado
    assert first_token_record.is_revoked is True
    assert first_token_record.revoked_at is not None
    assert first_token_record.replaced_by is not None
    
    # 2. Se generó un nuevo par de tokens
    assert new_access is not None
    assert new_refresh is not None
    assert new_refresh != raw_refresh
    
    # 3. El nuevo token DEBE pertenecer a la MISMA familia de tokens
    assert len(added_objects) == 2
    second_token_record: RefreshToken = added_objects[1]
    assert second_token_record.family_id == initial_family_id
    assert second_token_record.is_revoked is False


@pytest.mark.asyncio
async def test_refresh_token_reuse_detection_triggers_family_revocation():
    """
    VECTOR DE EXPLOTACIÓN RED TEAM - REPLAY ATTACK / TOKEN REUSE:
    Si un atacante intenta utilizar un Refresh Token que ya fue consumido (is_revoked=True),
    el sistema DEBE:
    1. Rechazar con HTTP 401.
    2. Identificar el ataque como reuso.
    3. Revocar INMEDIATAMENTE toda la familia de tokens (family_id).
    """
    family_id = uuid4()
    user_id = uuid4()
    tenant_id = uuid4()
    
    raw_stolen_token = "stolen-refresh-token-xyz"
    token_hash = hash_token(raw_stolen_token)
    
    compromised_token = RefreshToken(
        id=uuid4(),
        user_id=user_id,
        tenant_id=tenant_id,
        token_hash=token_hash,
        family_id=family_id,
        is_revoked=True,  # Ya consumido previamente
        revoked_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = compromised_token
    mock_db.execute.return_value = mock_result
    
    with pytest.raises(HTTPException) as exc_info:
        await AuthService.rotate_refresh_token(
            db=mock_db,
            raw_refresh_token=raw_stolen_token,
            client_ip="10.0.0.99",
        )
        
    assert exc_info.value.status_code == 401
    assert "posible intento de robo" in exc_info.value.detail.lower() or "revocada" in exc_info.value.detail.lower()
    
    # Verificar que se llamó a la revocación de la familia en la BD
    assert mock_db.execute.called
    assert mock_db.commit.called
    
    # Verificar que la familia quedó registrada como revocada en caché
    assert await token_cache.is_family_revoked(str(family_id)) is True


# ============================================================================
# 3. PRUEBAS DE AUTENTICACIÓN MULTIFACTOR (MFA TOTP)
# ============================================================================

def test_totp_rfc6238_generation_and_validation():
    """Valida la generación de secretos Base32 y verificación de códigos TOTP de 6 dígitos."""
    secret = generate_totp_secret()
    assert len(secret) >= 32
    
    code = get_totp_code(secret)
    assert len(code) == 6
    assert code.isdigit()
    
    # Validación positiva
    assert verify_totp(secret, code) is True
    
    # Validación negativa con código incorrecto
    wrong_code = "000000" if code != "000000" else "111111"
    assert verify_totp(secret, wrong_code) is False
    
    # Formato URI para código QR
    uri = generate_totp_uri(secret, "dentist@clinica.com", issuer="Dental SaaS")
    assert uri.startswith("otpauth://totp/")
    assert "secret=" in uri


@pytest.mark.asyncio
async def test_mfa_pending_token_cannot_access_protected_endpoints():
    """
    VECTOR DE BYPASS:
    Un usuario que supera el paso 1 de login recibe un token con scope 'mfa_pending'.
    Este token temporal NO DEBE permitir el acceso a endpoints normales protegidos.
    """
    user_id = uuid4()
    tenant_id = uuid4()
    
    mfa_token = create_mfa_pending_token(user_id=user_id, tenant_id=tenant_id)
    payload = decode_token(mfa_token)
    assert payload["scope"] == "mfa_pending"
    assert payload["type"] == "mfa_challenge"
    
    mock_db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=mfa_token, db=mock_db)
        
    assert exc_info.value.status_code == 401
    assert "segundo factor" in exc_info.value.detail.lower() or "mfa" in exc_info.value.detail.lower()


# ============================================================================
# 4. PRUEBAS DE RATE LIMITING DISTRIBUIDO
# ============================================================================

@pytest.mark.asyncio
async def test_rate_limiter_sliding_window_blocks_after_threshold():
    """
    VECTOR DE FUERZA BRUTA:
    Verifica que el limitador de tasa bloquee peticiones tras alcanzar el umbral de 5 intentos.
    """
    test_key = f"test_login_limit:{uuid4()}"
    await rate_limit_storage.reset(test_key)
    
    # 5 intentos permitidos
    for i in range(5):
        allowed, remaining, retry_after = await rate_limit_storage.is_allowed(
            key=test_key,
            max_requests=5,
            window_seconds=900,
        )
        assert allowed is True, f"El intento {i+1} debió ser permitido"
        assert remaining == 5 - (i + 1)
        assert retry_after == 0

    # 6to intento DEBE ser bloqueado (Rate Limit Exceeded)
    allowed, remaining, retry_after = await rate_limit_storage.is_allowed(
        key=test_key,
        max_requests=5,
        window_seconds=900,
    )
    assert allowed is False
    assert remaining == 0
    assert retry_after > 0


# ============================================================================
# 5. PRUEBAS DE INVALIDACIÓN DE SESIONES EN RESETEO DE CONTRASEÑA
# ============================================================================

@pytest.mark.asyncio
async def test_password_reset_revokes_all_user_sessions():
    """Valida que al cambiar o resetear una contraseña se revoquen todas las sesiones del usuario."""
    user_id = uuid4()
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 3
    mock_db.execute.return_value = mock_result
    
    revoked_count = await AuthService.revoke_all_user_sessions(mock_db, user_id)
    assert revoked_count == 3
    assert mock_db.commit.called
