# app/middlewares/tenant_middleware.py
"""
Middleware de Contexto Multi-Tenant y Enrutamiento de Políticas RLS.
Extrae la identidad del tenant del token JWT autenticado (o habilita bypass
para endpoints públicos autorizados como autenticación y healthcheck),
inyectando el contexto en variables de hilo/corutina (ContextVar) y en request.state.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from jose import jwt, JWTError

from app.core.security import SECRET_KEY, ALGORITHM
from app.core.tenant_context import (
    set_current_tenant_context,
    set_bypass_rls,
    clear_tenant_context
)

# Endpoints que requieren bypass explícito de RLS para resolución previa de identidad
PUBLIC_BYPASS_PREFIXES = (
    "/auth/login",
    "/auth/refresh",
    "/auth/mfa/challenge",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json"
)


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        clear_tenant_context()
        path = request.url.path

        # 1. Bypass automático para endpoints públicos y de autenticación
        if any(path.startswith(prefix) for prefix in PUBLIC_BYPASS_PREFIXES):
            set_bypass_rls(True)
            request.state.bypass_rls = True
            try:
                response = await call_next(request)
                return response
            finally:
                clear_tenant_context()

        # 2. Extracción segura del tenant desde el token JWT autenticado
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header.split(" ", 1)[1].strip()
            try:
                # Decodificación criptográfica rápida (la validación completa de expiración y JTI
                # se ejecuta en la dependencia get_current_user)
                payload = jwt.decode(
                    raw_token, 
                    SECRET_KEY, 
                    algorithms=[ALGORITHM],
                    options={"verify_aud": False}
                )
                
                tenant_id = payload.get("tenant_id")
                roles = payload.get("roles", [])

                if "SUPER_ADMIN" in roles:
                    set_bypass_rls(True)
                    request.state.bypass_rls = True
                elif tenant_id:
                    set_current_tenant_context(tenant_id)
                    request.state.tenant_id = tenant_id

            except JWTError:
                # Si el token es inválido, no se inyecta contexto (Default Deny)
                pass

        try:
            response = await call_next(request)
            return response
        finally:
            clear_tenant_context()
