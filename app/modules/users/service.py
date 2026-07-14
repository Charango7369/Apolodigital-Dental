# app/modules/users/service.py
from app.modules.users.repository import UserRepository
from app.modules.users.models import User
from app.core.security import hash_password


class UserService:
    """
    🚨 FIX: el modelo User no tiene un campo `role` (singular) — solo `roles`
    (lista JSON). El código anterior pasaba `role=data.role`, lo cual nunca
    funcionó porque ese atributo no existe en el modelo SQLAlchemy.
    Nota: el router de usuarios actual ya no usa esta clase (construye el
    User directamente para tener control total sobre la seguridad del
    tenant_id), pero la dejamos corregida por si se reutiliza en otro flujo.
    """
    def __init__(self, repository: UserRepository):
        self.repository = repository

    async def create_user(self, data, tenant_id):
        user = User(
            full_name=data.full_name,
            email=data.email,
            hashed_password=hash_password(data.password),
            roles=getattr(data, "roles", None) or ["RECEPTIONIST"],
            tenant_id=tenant_id,
        )
        return await self.repository.create(user)