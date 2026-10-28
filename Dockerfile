# ==============================================================================
# Multi-Stage Dockerfile de Alta Seguridad para Entornos Cloud (Railway / Kubernetes)
# Cumple con CIS Docker Benchmark, OWASP Container Security y Principio de Menor Privilegio
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Builder (Compilación y Empaquetado de Dependencias)
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Instalar herramientas de compilación requeridas exclusivamente durante el build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar manifiesto de dependencias e instalar en prefijo aislado /install
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# ------------------------------------------------------------------------------
# Stage 2: Runtime (Entorno Mínimo de Ejecución sin Herramientas de Compilación)
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Variables de entorno para hardening de ejecución Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PORT=8080

# Instalar exclusivamente bibliotecas compartidas de runtime indispensables
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Creación de usuario y grupo de sistema sin privilegios (UID/GID 10001:10001)
RUN addgroup --system --gid 10001 appgroup && \
    adduser --system --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin appuser

# Copiar paquetes instalados desde el builder
COPY --from=builder /install /usr/local

# Crear directorio de trabajo y transferir propiedad al usuario no privilegiado
WORKDIR /app
COPY --chown=appuser:appgroup . /app

# Transición irrevocable a usuario no root (Cero Privilegios)
USER 10001:10001

# Sondeo de salud nativo (Healthcheck) sin dependencias externas (curl/wget)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request, os; urllib.request.urlopen('http://localhost:' + str(os.environ.get('PORT', 8080)) + '/health', timeout=3)" || exit 1

EXPOSE 8080

# Inicio seguro: Migración automática de esquema y arranque de servidor ASGI Uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
