# app/core/cache.py
"""
Módulo de Caché y Revocación Distribuida de Sesiones.
Provee soporte para:
1. Redis (si `REDIS_URL` está configurado en las variables de entorno).
2. Fallback asíncrono en memoria con limpieza automática por TTL (Time-To-Live)
   y concurrencia segura para despliegues sin clúster Redis.
"""
import asyncio
import logging
import time
from typing import Dict, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)


class InMemoryCache:
    """Almacén en memoria con expiración por TTL y sincronización asíncrona."""
    def __init__(self):
        self._store: Dict[str, Tuple[str, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[str]:
        async with self._lock:
            if key not in self._store:
                return None
            val, expire_at = self._store[key]
            if time.time() > expire_at:
                del self._store[key]
                return None
            return val

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        async with self._lock:
            expire_at = time.time() + max(1, ttl_seconds)
            self._store[key] = (value, expire_at)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def clear_expired(self) -> None:
        async with self._lock:
            now = time.time()
            expired_keys = [k for k, (_, exp) in self._store.items() if now > exp]
            for k in expired_keys:
                del self._store[k]


class CacheManager:
    def __init__(self):
        self._in_memory = InMemoryCache()
        self._redis_client = None
        self._use_redis = False

        if settings.REDIS_URL:
            try:
                import redis.asyncio as aioredis
                self._redis_client = aioredis.from_url(
                    settings.REDIS_URL, 
                    decode_responses=True,
                    socket_timeout=2.0
                )
                self._use_redis = True
                logger.info("Conectado a Redis para revocación de tokens y rate limiting.")
            except ImportError:
                logger.warning("Librería 'redis' no instalada. Usando fallback en memoria para caché/revocación.")
            except Exception as e:
                logger.warning(f"No se pudo conectar a Redis ({e}). Usando fallback en memoria.")

    async def get(self, key: str) -> Optional[str]:
        if self._use_redis and self._redis_client:
            try:
                return await self._redis_client.get(key)
            except Exception as e:
                logger.error(f"Error al leer de Redis ({e}). Consultando fallback local.")
        return await self._in_memory.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        if self._use_redis and self._redis_client:
            try:
                await self._redis_client.set(key, value, ex=max(1, ttl_seconds))
                return
            except Exception as e:
                logger.error(f"Error al escribir en Redis ({e}). Guardando en fallback local.")
        await self._in_memory.set(key, value, ttl_seconds)

    async def delete(self, key: str) -> None:
        if self._use_redis and self._redis_client:
            try:
                await self._redis_client.delete(key)
            except Exception as e:
                logger.error(f"Error al borrar de Redis ({e}).")
        await self._in_memory.delete(key)

    # Métodos especializados para JWT JTI y Familias de Tokens
    async def revoke_token(self, jti: str, ttl_seconds: int = 1800) -> None:
        """Registra un identificador único de JWT (jti) en la lista negra de revocación."""
        key = f"revoked_token:{jti}"
        await self.set(key, "1", ttl_seconds)

    async def is_token_revoked(self, jti: str) -> bool:
        """Verifica si el JTI del token se encuentra en la lista de revocación."""
        if not jti:
            return False
        key = f"revoked_token:{jti}"
        return (await self.get(key)) is not None

    async def revoke_family(self, family_id: str, ttl_seconds: int = 604800) -> None:
        """Registra una familia de refresh tokens como completamente revocada por reuso."""
        key = f"revoked_family:{family_id}"
        await self.set(key, "compromised", ttl_seconds)

    async def is_family_revoked(self, family_id: str) -> bool:
        if not family_id:
            return False
        key = f"revoked_family:{family_id}"
        return (await self.get(key)) is not None


# Instancia singleton de caché
token_cache = CacheManager()
