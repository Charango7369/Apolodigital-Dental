# app/db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings
from app.core.tenant_context import (
    apply_db_tenant_context,
    reset_db_tenant_context,
)

# 1. Crear el motor asíncrono
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600
)

# 2. Crear la fábrica de sesiones
AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# 3. Definir la dependencia get_db con inyección de contexto RLS
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            # Sincroniza variables de sesión PostgreSQL para Row-Level Security
            await apply_db_tenant_context(session)
            yield session
        finally:
            await reset_db_tenant_context(session)
            await session.close()
