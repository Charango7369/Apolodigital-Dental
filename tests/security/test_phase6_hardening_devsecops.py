# tests/security/test_phase6_hardening_devsecops.py
"""
Suite de Pruebas de Seguridad Ofensiva y Defensiva - FASE 6:
Hardening de Contenedores, Cabeceras HTTP Globales (OWASP) y DevSecOps.

Valida que el servidor web responda con todas las cabeceras de blindaje HTTP,
suprima fugas de huella digital y que los artefactos de infraestructura
(Dockerfile, .dockerignore) cumplan con los estándares de seguridad de contenedores.
"""
import os
import pytest
from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_security_headers_present_on_api_endpoints():
    """
    OWASP Secure Headers:
    Verifica que cada respuesta HTTP de la API REST incluya obligatoriamente
    todas las directivas de seguridad en profundidad.
    """
    response = client.get("/health")
    assert response.status_code == 200

    headers = response.headers

    # 1. Anti-MIME-Sniffing
    assert headers.get("X-Content-Type-Options") == "nosniff", "Falta X-Content-Type-Options: nosniff"

    # 2. Anti-Clickjacking
    assert headers.get("X-Frame-Options") == "DENY", "Falta X-Frame-Options: DENY"

    # 3. Protección XSS heredada
    assert "1; mode=block" in headers.get("X-XSS-Protection", ""), "Falta X-XSS-Protection"

    # 4. HSTS (HTTP Strict Transport Security)
    hsts = headers.get("Strict-Transport-Security", "")
    assert "max-age=63072000" in hsts, "HSTS debe configurarse por al menos 2 años (63072000s)"
    assert "includeSubDomains" in hsts, "HSTS debe proteger todos los subdominios"
    assert "preload" in hsts, "HSTS debe incluir flag preload para inclusión en listas de navegadores"

    # 5. Referrer Policy estricta
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin", "Falta Referrer-Policy estricta"

    # 6. Restricción de Hardware (Permissions-Policy)
    perm_policy = headers.get("Permissions-Policy", "")
    assert "geolocation=()" in perm_policy, "Debe deshabilitar geolocalización"
    assert "camera=()" in perm_policy, "Debe deshabilitar cámara"
    assert "microphone=()" in perm_policy, "Debe deshabilitar micrófono"

    # 7. Content-Security-Policy para API
    csp = headers.get("Content-Security-Policy", "")
    assert "default-src 'none'" in csp, "CSP de API debe ser Default Deny ('none')"
    assert "frame-ancestors 'none'" in csp, "CSP debe denegar embebido en iframes"

    # 8. Supresión de Huella Tecnológica (Fingerprinting Defense)
    assert headers.get("Server") == "ApoloDental-SecurityGateway", "Fuga de fingerprinting en Server"
    assert "X-Powered-By" not in headers, "Fuga de tecnología en X-Powered-By"


def test_security_headers_docs_endpoint_csp():
    """
    Verifica que la documentación OpenAPI / Swagger UI posea un CSP adaptado
    para cargar scripts seguros desde CDN manteniendo anti-framing estricto.
    """
    response = client.get("/docs")
    assert response.status_code == 200

    csp = response.headers.get("Content-Security-Policy", "")
    assert "https://cdn.jsdelivr.net" in csp, "Swagger UI requiere cdn.jsdelivr.net para renderizado"
    assert "frame-ancestors 'none'" in csp, "Docs deben prohibir clickjacking mediante frame-ancestors"


def test_dockerfile_security_specifications():
    """
    CIS Docker Benchmark & Principio de Menor Privilegio:
    Valida estáticamente que el Dockerfile implemente:
    1. Construcción multi-etapa (Multi-Stage Build).
    2. Ejecución bajo usuario no root.
    3. Sondeo de salud (HEALTHCHECK) nativo.
    4. Imagen base slim mínima.
    """
    dockerfile_path = "Dockerfile"
    assert os.path.exists(dockerfile_path), "El archivo Dockerfile no existe"

    with open(dockerfile_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Multi-Stage Build
    assert "AS builder" in content, "Dockerfile debe definir etapa builder"
    assert "AS runtime" in content, "Dockerfile debe definir etapa runtime"
    assert content.count("FROM ") >= 2, "Dockerfile debe contener al menos 2 etapas FROM"

    # 2. Usuario no privilegiado (Non-Root User)
    assert "USER 10001:10001" in content or "USER appuser" in content, (
        "VULNERABILIDAD CRÍTICA: El contenedor no debe ejecutarse como root"
    )
    assert "addgroup" in content and "adduser" in content, "Debe crear appuser/appgroup explícitamente"

    # 3. Sondeo de Salud nativo (HEALTHCHECK)
    assert "HEALTHCHECK" in content, "Dockerfile debe definir HEALTHCHECK para orquestadores"

    # 4. Imagen base segura
    assert "python:3.12-slim" in content, "Debe usar imagen minimalista python:3.12-slim"


def test_dockerignore_security_specifications():
    """
    Prevención de Fuga de Credenciales y Secretos en Capas Docker:
    Valida que .dockerignore excluya archivos sensibles, entornos virtuales y git.
    """
    dockerignore_path = ".dockerignore"
    assert os.path.exists(dockerignore_path), "El archivo .dockerignore no existe"

    with open(dockerignore_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert ".env" in content, ".dockerignore debe excluir archivos de entorno .env"
    assert ".git" in content, ".dockerignore debe excluir metadatos de Git"
    assert "venv" in content, ".dockerignore debe excluir entornos virtuales locales"
    assert "__pycache__" in content, ".dockerignore debe excluir bytecode y caché"
    assert "tests" in content, ".dockerignore no debe incluir pruebas unitarias en producción"
