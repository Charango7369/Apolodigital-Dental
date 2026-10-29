"""reconcile_clinic_tenants_and_blanca_lopez

Revision ID: f6b1a2c3d4e5
Revises: e5a91c2b3d4f
Create Date: 2026-10-28 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
import uuid
from datetime import datetime, timezone

# revision identifiers, used by Alembic.
revision: str = 'f6b1a2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'e5a91c2b3d4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PLATFORM_TENANT_ID = uuid.UUID("7ca2d9b7-8e46-4e63-942a-5a277826ce62")
DEMO_TENANT_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
BLANCA_TENANT_ID = uuid.UUID("b1a4c000-0000-4000-8000-000000000001")
BLANCA_USER_ID = uuid.UUID("b1a4c000-0000-4000-8000-000000000002")


def upgrade() -> None:
    conn = op.get_bind()
    now = datetime.now(timezone.utc)

    # 1. Bypass RLS en la conexión para la reconciliación administrativa
    try:
        conn.execute(text("SELECT set_config('app.bypass_rls', 'true', false)"))
    except Exception:
        pass

    print("\n[MIGRACION f6b1a2c3d4e5] Iniciando reconciliacion multi-tenant de usuarios...")

    # 2. Asegurar que existe el Tenant de la Plataforma
    conn.execute(text("""
        INSERT INTO tenants (id, name, is_active, created_at, updated_at)
        VALUES (:id, :name, true, :now, :now)
        ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, is_active = true;
    """), {
        "id": PLATFORM_TENANT_ID,
        "name": "ApoloDigital - Plataforma",
        "now": now,
    })

    # 3. Asegurar que existe el Tenant Demo / Clínica Principal
    conn.execute(text("""
        INSERT INTO tenants (id, name, is_active, created_at, updated_at)
        VALUES (:id, :name, true, :now, :now)
        ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, is_active = true;
    """), {
        "id": DEMO_TENANT_ID,
        "name": "Clínica Odontológica Principal",
        "now": now,
    })

    # 4. Aislar estrictamente a SUPER_ADMIN en el tenant de plataforma
    res_sa = conn.execute(text("SELECT id, email, tenant_id FROM users WHERE email = 'superadmin@apolodigital.lat'"))
    sa_user = res_sa.fetchone()
    if sa_user:
        print(f"  -> Asignando Superadmin a tenant de plataforma ({PLATFORM_TENANT_ID})...")
        conn.execute(text("""
            UPDATE users 
            SET tenant_id = :platform_tid,
                roles = '["SUPER_ADMIN"]',
                updated_at = :now
            WHERE email = 'superadmin@apolodigital.lat';
        """), {"platform_tid": PLATFORM_TENANT_ID, "now": now})

    # 5. Aislar estrictamente a admin@apolodigital.lat (Dr. Edwin Rivero) en la clínica demo
    res_ad = conn.execute(text("SELECT id, email, hashed_password FROM users WHERE email = 'admin@apolodigital.lat'"))
    ad_user = res_ad.fetchone()
    if ad_user:
        print(f"  -> Asignando Admin Demo a clínica principal ({DEMO_TENANT_ID})...")
        conn.execute(text("""
            UPDATE users 
            SET tenant_id = :demo_tid,
                updated_at = :now
            WHERE email = 'admin@apolodigital.lat';
        """), {"demo_tid": DEMO_TENANT_ID, "now": now})

    # 6. Reconciliar la clínica y el usuario de la Dra. Blanca López
    res_bt = conn.execute(text("SELECT id, name FROM tenants WHERE name ILIKE '%blanca%' OR id = :bid"), {"bid": BLANCA_TENANT_ID})
    blanca_tenant = res_bt.fetchone()
    if not blanca_tenant:
        print(f"  -> Creando clínica dedicada para Dra. Blanca López...")
        conn.execute(text("""
            INSERT INTO tenants (id, name, is_active, created_at, updated_at)
            VALUES (:id, :name, true, :now, :now)
            ON CONFLICT (id) DO NOTHING;
        """), {
            "id": BLANCA_TENANT_ID,
            "name": "Clínica Dental Dra. Blanca López",
            "now": now,
        })
        actual_blanca_tenant_id = BLANCA_TENANT_ID
    else:
        actual_blanca_tenant_id = blanca_tenant[0]
        print(f"  -> Clínica de Dra. Blanca López encontrada: {blanca_tenant[1]} ({actual_blanca_tenant_id})")

    # Buscar usuario blancalopez@gmail.com
    res_bu = conn.execute(text("SELECT id, email, tenant_id FROM users WHERE email ILIKE 'blancalopez%' OR full_name ILIKE '%blanca%lopez%'"))
    blanca_user = res_bu.fetchone()

    if blanca_user:
        print(f"  -> Actualizando Dra. Blanca López (ID {blanca_user[0]}) al tenant dedicado {actual_blanca_tenant_id}...")
        conn.execute(text("""
            UPDATE users 
            SET tenant_id = :tid,
                full_name = 'Dr. Blanca Lopez',
                roles = '["ADMIN", "DOCTOR"]',
                is_active = true,
                updated_at = :now
            WHERE id = :uid;
        """), {"tid": actual_blanca_tenant_id, "uid": blanca_user[0], "now": now})
    else:
        print(f"  -> Creando usuario Dra. Blanca López (blancalopez@gmail.com) como ADMIN en {actual_blanca_tenant_id}...")
        pwd_hash = ad_user[2] if ad_user and len(ad_user) > 2 else "$2b$12$AiC/sfmBlw04rUxQBLbB8.hSR9ilywRCDPuBxdoiDwlzCkwpshWF6"
        conn.execute(text("""
            INSERT INTO users (id, full_name, email, hashed_password, roles, is_active, tenant_id, created_at, updated_at)
            VALUES (:id, 'Dr. Blanca Lopez', 'blancalopez@gmail.com', :pwd, '["ADMIN", "DOCTOR"]', true, :tid, :now, :now)
            ON CONFLICT (email) DO UPDATE SET tenant_id = EXCLUDED.tenant_id, full_name = EXCLUDED.full_name, is_active = true;
        """), {
            "id": BLANCA_USER_ID,
            "pwd": pwd_hash,
            "tid": actual_blanca_tenant_id,
            "now": now,
        })

    # 7. Garantizar que en el tenant de Blanca López NO quede ningún usuario extraño
    conn.execute(text("""
        UPDATE users 
        SET tenant_id = :platform_tid 
        WHERE email = 'superadmin@apolodigital.lat' AND tenant_id = :blanca_tid;
    """), {"platform_tid": PLATFORM_TENANT_ID, "blanca_tid": actual_blanca_tenant_id})

    conn.execute(text("""
        UPDATE users 
        SET tenant_id = :demo_tid 
        WHERE email = 'admin@apolodigital.lat' AND tenant_id = :blanca_tid;
    """), {"demo_tid": DEMO_TENANT_ID, "blanca_tid": actual_blanca_tenant_id})

    print("[MIGRACION f6b1a2c3d4e5] Reconciliacion completada con exito.")


def downgrade() -> None:
    pass
