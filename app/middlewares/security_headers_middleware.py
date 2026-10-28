# app/middlewares/security_headers_middleware.py
"""
Middleware de Cabeceras de Seguridad HTTP Globales (OWASP Secure Headers).
Aplica defensas en profundidad contra Clickjacking, MIME-Sniffing, XSS,
fugas de referer y abuso de APIs de hardware del navegador,
además de suprimir cabeceras de fingerprinting de servidores y frameworks.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Rutas que requieren CSP permisivo para renderizado interactivo de Swagger UI / ReDoc
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")

# CSP Estricto para endpoints de API REST (Default Deny)
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none';"

# CSP Especializado para la interfaz gráfica de Swagger / ReDoc
DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "connect-src 'self'; "
    "frame-ancestors 'none';"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        path = request.url.path

        # 1. Anti-MIME-Sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 2. Anti-Clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # 3. Protección XSS heredada para navegadores clásicos
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # 4. HSTS (HTTP Strict Transport Security): 2 años (63072000s) con subdominios y precarga
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"

        # 5. Política de Referrer estricta
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 6. Restricción de permisos y APIs del navegador (Permissions-Policy)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), camera=(), microphone=(), payment=(), usb=(), "
            "accelerometer=(), gyroscope=(), magnetometer=()"
        )

        # 7. Content-Security-Policy contextual
        if path.startswith(DOCS_PATHS):
            response.headers["Content-Security-Policy"] = DOCS_CSP
        else:
            response.headers["Content-Security-Policy"] = API_CSP

        # 8. Prevención de huella tecnológica (Fingerprinting Defense)
        # Oculta o neutraliza cabeceras que delaten software y versiones
        response.headers["Server"] = "ApoloDental-SecurityGateway"
        if "X-Powered-By" in response.headers:
            del response.headers["X-Powered-By"]

        return response
