# app/middlewares/csrf_middleware.py
"""
Middleware Anti-CSRF para FastAPI / Starlette.
Aplica la verificación Double Submit Cookie para todas las mutaciones de estado
(POST, PUT, PATCH, DELETE) que operan con cookies del navegador.
"""
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.csrf import verify_csrf_token

logger = logging.getLogger(__name__)

# Rutas exentas de validación CSRF (públicas, de autenticación inicial o de sondas)
CSRF_EXEMPT_PATHS = {
    "/auth/login",
    "/auth/mfa/challenge",
    "/auth/refresh",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/health",
    "/health/deep",
    "/whatsapp/webhook",
}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        method = request.method.upper()
        path = request.url.path

        # 1. Métodos seguros no requieren validación CSRF
        if method in ("GET", "HEAD", "OPTIONS", "TRACE"):
            return await call_next(request)

        # 2. Rutas exentas
        if path in CSRF_EXEMPT_PATHS or any(path.startswith(prefix) for prefix in ("/docs", "/redoc", "/openapi", "/whatsapp/webhook")):
            return await call_next(request)

        # 3. Comprobar si la petición proviene de un navegador con cookies de sesión
        has_session_cookie = "refresh_token" in request.cookies or "csrf_token" in request.cookies
        
        if has_session_cookie:
            header_token = request.headers.get("x-csrf-token")
            cookie_token = request.cookies.get("csrf_token")

            if not verify_csrf_token(header_token, cookie_token):
                logger.warning(
                    f"[CSRF VIOLATION] Petición mutante bloqueada: {method} {path}. "
                    f"Header presente: {bool(header_token)}, Cookie presente: {bool(cookie_token)}"
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Validación Anti-CSRF fallida: La cabecera X-CSRF-Token es requerida y debe coincidir con la cookie de sesión."
                    },
                )

        return await call_next(request)
