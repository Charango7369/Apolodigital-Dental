# tests/security/test_phase7_infrastructure_headers.py
"""
Test Suite: FASE 7 - Infraestructura, Cabeceras de Seguridad y Configuración Cloud
(Cloudflare Workers/Pages y Railway Backend)
Valida:
1. Políticas CORS restrictivas con soporte seguro de credenciales (sin comodines '*').
2. Cabeceras OWASP en el backend (HSTS con preload, Anti-Clickjacking, Anti-Sniffing, CSP, Permissions-Policy).
3. Aislamiento CSP diferenciado entre endpoints de API (default-src 'none') y Swagger Docs.
4. Sincronización de configuración perimetral de Cloudflare (_headers y wrangler.jsonc).
5. Configuración de runtime y resiliencia de infraestructura.
"""
import json
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

FRONTEND_ROOT = Path("D:/Dental-Frontend")


@pytest.mark.asyncio
async def test_cors_allows_authorized_origins_with_credentials():
    """Valida que los orígenes autorizados reciban cabeceras CORS explícitas con soporte de credenciales."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://api.dental.internal") as client:
        # Petición preflight OPTIONS desde origen autorizado
        response = await client.options(
            "/auth/login",
            headers={
                "Origin": "https://dental-frontend.edwinjrivero.workers.dev",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "https://dental-frontend.edwinjrivero.workers.dev"
        assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_cors_rejects_unauthorized_origins():
    """Valida que un origen no autorizado NO reciba cabeceras de autorización CORS."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://api.dental.internal") as client:
        response = await client.options(
            "/auth/login",
            headers={
                "Origin": "https://malicious-attacker-website.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        # El middleware CORS de FastAPI omite la cabecera allow-origin para orígenes no permitidos
        assert response.headers.get("access-control-allow-origin") != "https://malicious-attacker-website.com"
        assert response.headers.get("access-control-allow-origin") != "*"


@pytest.mark.asyncio
async def test_backend_security_headers_on_api_endpoints():
    """Verifica la presencia obligatoria de todas las cabeceras de hardening en los endpoints de API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://api.dental.internal") as client:
        response = await client.get("/health/")
        assert response.status_code == 200

        headers = response.headers

        # 1. HSTS estricto
        hsts = headers.get("strict-transport-security", "")
        assert "max-age=63072000" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" in hsts

        # 2. Anti-Clickjacking y MIME-Sniffing
        assert headers.get("x-frame-options") == "DENY"
        assert headers.get("x-content-type-options") == "nosniff"

        # 3. Referrer y Permissions Policy
        assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert "geolocation=()" in headers.get("permissions-policy", "")
        assert "camera=()" in headers.get("permissions-policy", "")

        # 4. CSP Default Deny para endpoints de API
        assert headers.get("content-security-policy") == "default-src 'none'; frame-ancestors 'none'; base-uri 'none';"


@pytest.mark.asyncio
async def test_docs_endpoint_has_specialized_csp():
    """Verifica que el endpoint /docs tenga una política CSP adaptada a los activos de Swagger UI."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://api.dental.internal") as client:
        response = await client.get("/docs")
        assert response.status_code == 200

        csp = response.headers.get("content-security-policy", "")
        assert "cdn.jsdelivr.net" in csp
        assert "frame-ancestors 'none'" in csp


def test_cloudflare_headers_file_contains_mandatory_security_rules():
    """Valida que los archivos _headers de Cloudflare Pages/Workers contengan las reglas perimetrales."""
    for rel_path in ["public/_headers", "dist/_headers"]:
        headers_file = FRONTEND_ROOT / rel_path
        if not headers_file.exists():
            continue

        content = headers_file.read_text(encoding="utf-8")

        assert "X-Frame-Options: DENY" in content
        assert "X-Content-Type-Options: nosniff" in content
        assert "Strict-Transport-Security: max-age=63072000; includeSubDomains; preload" in content
        assert "Content-Security-Policy:" in content
        assert "connect-src 'self' https://web-production-aab12.up.railway.app" in content
        assert "Permissions-Policy:" in content


def test_wrangler_spa_configuration():
    """Valida que wrangler.jsonc configure correctamente el enrutamiento para Single-Page Applications."""
    wrangler_file = FRONTEND_ROOT / "wrangler.jsonc"
    assert wrangler_file.exists(), "wrangler.jsonc no existe en el frontend"

    content = wrangler_file.read_text(encoding="utf-8")
    data = json.loads(content)

    assert data.get("name") == "dental-frontend"
    assets = data.get("assets", {})
    assert assets.get("directory") == "./dist"
    assert assets.get("not_found_handling") == "single-page-application"
