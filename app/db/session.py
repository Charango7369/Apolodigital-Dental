from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings # Asumiendo que tienes un archivo de config

# 1. Crear el motor asíncrono
engine = create_async_engine(
    settings.DATABASE_URL, # Tu variable DB_URL de Railway
    echo=False,
    pool_pre_ping=True,
)

# 2. Crear la fábrica de sesiones
AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# 3. Definir la dependencia get_db
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()