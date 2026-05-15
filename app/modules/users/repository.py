from sqlalchemy.orm import Session
from app.modules.users.models import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, tenant_id):
        return self.db.query(User).filter(
            User.tenant_id == tenant_id
        ).all()

    def create(self, user: User):
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user