from sqlalchemy.orm import Session
from app.modules.tenants.models import Tenant
from app.modules.users.models import User
from app.core.security import hash_password


def seed_initial_data(db: Session):
    tenant = Tenant(name="Demo Tenant", slug="demo")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    admin = User(
        full_name="Super Admin",
        email="admin@demo.com",
        hashed_password=hash_password("Admin123*"),
        role="SUPERADMIN",
        tenant_id=tenant.id,
    )

    db.add(admin)
    db.commit()