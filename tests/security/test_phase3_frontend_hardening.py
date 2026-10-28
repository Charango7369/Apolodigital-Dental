# tests/security/test_phase3_frontend_hardening.py
"""
Suite de Pruebas Automatizadas de Seguridad - Fase 3:
Blindaje de Frontend, Almacenamiento Seguro (HttpOnly Cookies), Protección Anti-CSRF
y Rehidratación de Sesión en Memoria.
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.csrf import generate_csrf_token, verify_csrf_token
from app.middlewares.csrf_middleware import CSRFMiddleware
from app.modules.auth.router import _set_auth_cookies, _clear_auth_cookies
from app.modules.users.models import User as UserModel


def test_csrf_token_generation_and_validation():
    """Valida la generación de tokens CSRF de alta entropía y su comparación constante."""
    token = generate_csrf_token()
    assert len(token) >= 32
    
    # Verificación positiva
    assert verify_csrf_token(token, token) is True
    
    # Verificación negativa (token alterado o diferente)
    assert verify_csrf_token("invalid-token-1234567890", token) is False
    assert verify_csrf_token(None, token) is False
    assert verify_csrf_token(token, None) is False
    assert verify_csrf_token("", "") is False


@pytest.mark.asyncio
async def test_csrf_middleware_blocks_mutating_request_without_token():
    """
    VECTOR DE EXPLOTACIÓN CSRF:
    Una petición mutating (POST, PUT, DELETE) con cookies de sesión activas pero SIN
    la cabecera X-CSRF-Token DEBE ser bloqueada inmediatamente con HTTP 403 Forbidden.
    """
    middleware = CSRFMiddleware(app=None)
    
    # Simula petición POST con cookie de sesión pero sin header CSRF
    mock_request = MagicMock()
    mock_request.method = "POST"
    mock_request.url.path = "/patients"
    mock_request.cookies = {"refresh_token": "valid_cookie_session", "csrf_token": "csrf1234567890abcdef"}
    mock_request.headers = {}  # Falta x-csrf-token

    call_next = AsyncMock()

    response = await middleware.dispatch(mock_request, call_next)
    
    assert response.status_code == 403
    assert call_next.called is False


@pytest.mark.asyncio
async def test_csrf_middleware_allows_mutating_request_with_valid_matching_token():
    """
    Valida que una petición POST legítima con cabecera X-CSRF-Token coincidente
    con la cookie csrf_token sea procesada exitosamente.
    """
    middleware = CSRFMiddleware(app=None)
    csrf_val = "valid-csrf-token-1234567890abcdef"
    
    mock_request = MagicMock()
    mock_request.method = "POST"
    mock_request.url.path = "/patients"
    mock_request.cookies = {"refresh_token": "valid_cookie_session", "csrf_token": csrf_val}
    mock_request.headers = {"x-csrf-token": csrf_val}

    call_next = AsyncMock(return_value=JSONResponse(status_code=200, content={"status": "ok"}))

    response = await middleware.dispatch(mock_request, call_next)
    
    assert response.status_code == 200
    assert call_next.called is True


@pytest.mark.asyncio
async def test_csrf_middleware_allows_safe_methods_without_csrf_token():
    """Valida que los métodos seguros de lectura (GET, HEAD, OPTIONS) no requieran token CSRF."""
    middleware = CSRFMiddleware(app=None)
    
    mock_request = MagicMock()
    mock_request.method = "GET"
    mock_request.url.path = "/patients"
    mock_request.cookies = {"refresh_token": "session"}
    mock_request.headers = {}

    call_next = AsyncMock(return_value=JSONResponse(status_code=200, content={"status": "ok"}))

    response = await middleware.dispatch(mock_request, call_next)
    
    assert response.status_code == 200
    assert call_next.called is True


def test_auth_cookies_security_flags():
    """
    Valida que las cookies de sesión se emitan con los flags de seguridad obligatorios:
    - refresh_token: HttpOnly=True, Secure=True, SameSite=none.
    - csrf_token: HttpOnly=False (legible por cliente para Double Submit), Secure=True, SameSite=none.
    """
    mock_response = MagicMock()
    refresh_token = "rt_secret_123456"
    csrf_token = "csrf_token_abcdef"
    
    _set_auth_cookies(mock_response, refresh_token, csrf_token)
    
    # Comprobar llamadas a set_cookie
    assert mock_response.set_cookie.call_count == 2
    
    calls = mock_response.set_cookie.call_args_list
    rt_call = [c for c in calls if c.kwargs.get("key") == "refresh_token"][0]
    csrf_call = [c for c in calls if c.kwargs.get("key") == "csrf_token"][0]
    
    # Flags de Refresh Token
    assert rt_call.kwargs["httponly"] is True, "El refresh token DEBE ser HttpOnly para evitar XSS"
    assert rt_call.kwargs["secure"] is True
    assert rt_call.kwargs["samesite"] == "none"
    
    # Flags de CSRF Token
    assert csrf_call.kwargs["httponly"] is False, "El CSRF token debe ser legible por JavaScript para la cabecera"
    assert csrf_call.kwargs["secure"] is True
    assert csrf_call.kwargs["samesite"] == "none"
