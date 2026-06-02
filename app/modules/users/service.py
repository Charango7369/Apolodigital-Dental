# app/modules/users/service.py
from app.modules.users.repository import UserRepository
from app.modules.users.models import User
from app.core.security import hash_password


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    async def create_user(self, data, tenant_id):  # 👈 Añadimos 'async'
        user = User(
            full_name=data.full_name,
            email=data.email,
            hashed_password=hash_password(data.password),
            role=data.role,
            tenant_id=tenant_id,
        )

        # 👈 Añadimos 'await' porque el repositorio ahora operará con AsyncSession
        return await self.repository.create(user)