# app/core/rate_limiter.py
"""
Rate Limiter de Ventana Deslizante (Sliding Window Rate Limiter).
Mitigación distribuida contra ataques de fuerza bruta, credential stuffing
y denegación de servicio a nivel de endpoints críticos de autenticación.
"""
import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Callable, Optional

from fastapi import HTTPException, Request, status
from app.core.config import settings

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """
    Controlador de tasa por ventana de tiempo deslizante en memoria con fallback.
    Almacena marcas de tiempo de solicitudes para garantizar precisión matemática.
    """
    def __init__(self):
        # Mapea clave -> deque de timestamps (float)
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def is_allowed(
        self, key: str, max_requests: int, window_seconds: int
    ) -> tuple[bool, int, int]:
        """
        Calcula si la solicitud es permitida.
        Retorna: (is_allowed, remaining_requests, retry_after_seconds)
        """
        now = time.time()
        window_start = now - window_seconds

        async with self._lock:
            queue = self._requests[key]

            # 1. Purgar solicitudes fuera de la ventana actual
            while queue and queue[0] < window_start:
                queue.popleft()

            # 2. Comprobar si se alcanzó el límite
            if len(queue) >= max_requests:
                earliest = queue[0]
                retry_after = max(1, int(earliest + window_seconds - now))
                return False, 0, retry_after

            # 3. Registrar la solicitud actual
            queue.append(now)
            remaining = max(0, max_requests - len(queue))
            return True, remaining, 0

    async def reset(self, key: Optional[str] = None) -> None:
        """Reinicia el contador para una clave específica o limpia toda la estructura (para tests)."""
        async with self._lock:
            if key:
                self._requests.pop(key, None)
            else:
                self._requests.clear()


# Instancia singleton para rate limiting en memoria
rate_limit_storage = SlidingWindowRateLimiter()


def get_client_ip(request: Request) -> str:
    """
    Extrae la dirección IP real del cliente respetando headers de proxy inverso
    (Cloudflare 'cf-connecting-ip', 'x-forwarded-for' o socket directo).
    """
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()

    x_forwarded = request.headers.get("x-forwarded-for")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown-client"


class RateLimitCheck:
    """
    Dependencia reutilizable para inyectar límites de tasa en rutas FastAPI.
    """
    def __init__(
        self, 
        max_requests: int, 
        window_seconds: int, 
        key_prefix: str = "rate_limit"
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix

    async def __call__(self, request: Request) -> None:
        ip = get_client_ip(request)
        path = request.url.path
        key = f"{self.key_prefix}:{path}:{ip}"

        allowed, remaining, retry_after = await rate_limit_storage.is_allowed(
            key, self.max_requests, self.window_seconds
        )

        if not allowed:
            logger.warning(f"[RATE LIMIT] Límite excedido para IP {ip} en {path}. Reintento en {retry_after}s.")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Demasiados intentos. Por motivos de seguridad, espere {retry_after} segundos antes de reintentar.",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )


# Fábricas de dependencias preconfiguradas
rate_limiter_login = RateLimitCheck(
    max_requests=settings.RATE_LIMIT_LOGIN_MAX,
    window_seconds=settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS,
    key_prefix="login"
)

rate_limiter_mfa = RateLimitCheck(
    max_requests=settings.RATE_LIMIT_LOGIN_MAX,
    window_seconds=settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS,
    key_prefix="mfa"
)

rate_limiter_reset = RateLimitCheck(
    max_requests=settings.RATE_LIMIT_RESET_MAX,
    window_seconds=settings.RATE_LIMIT_RESET_WINDOW_SECONDS,
    key_prefix="reset_password"
)
