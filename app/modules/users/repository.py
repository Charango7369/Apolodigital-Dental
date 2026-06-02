# app/modules/users/repository.py
from sqlalchemy.ext.asyncio import AsyncSession  # 👈 Cambiado por la sesión asíncrona
from sqlalchemy.future import select             # 👈 Necesario para las consultas en SQLAlchemy 2.0
from app.modules.users.models import User


class UserRepository:
    def __init__(self, db: AsyncSession):        # 👈 Tipado correcto para consistencia
        self.db = db

    async def get_all(self, tenant_id: str):
        """Busca todos los usuarios pertenecientes a un Tenant de forma asíncrona."""
        # En entornos async se usa select() en lugar de db.query()
        result = await self.db.execute(
            select(User).where(User.tenant_id == tenant_id)
        )
        return result.scalars().all()

    async def create(self, user: User):
        """Persiste un nuevo usuario en la base de datos de forma asíncrona."""
        self.db.add(user)          # db.add sigue siendo síncrono en memoria
        await self.db.commit()     # 👈 El guardado físico en la base de datos REQUIERE await
        await self.db.refresh(user) # 👈 La recarga de datos (como el ID generado) REQUIERE await
        return user