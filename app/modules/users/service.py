from app.modules.users.repository import UserRepository
from app.modules.users.models import User
from app.core.security import hash_password


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def create_user(self, data, tenant_id):
        user = User(
            full_name=data.full_name,
            email=data.email,
            hashed_password=hash_password(data.password),
            role=data.role,
            tenant_id=tenant_id,
        )

        return self.repository.create(user)