import asyncio
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from passlib.context import CryptContext

# Configuramos el mismo encriptador que usa FastAPI por defecto
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Tu cadena de conexión apuntando al puerto 5433
DATABASE_URL = "postgresql+asyncpg://postgres:ApoloDB2026@localhost:5432/apolo_db"

async def run_seed():
    print("Iniciando inyección de datos de prueba...")
    engine = create_async_engine(DATABASE_URL)
    
    # Generamos UUIDs maestros
    tenant_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    
    # Contraseña por defecto para pruebas
    plain_password = "password123"
    hashed_pwd = pwd_context.hash(plain_password)
    
    async with engine.begin() as conn:
        # 1. Crear la Clínica (Tenant)
        print("-> Creando Clínica (Tenant)...")
        await conn.execute(text("""
            INSERT INTO tenants (id, created_at, updated_at) 
            VALUES (:id, :now, :now)
        """), {"id": tenant_id, "now": datetime.utcnow()})
        
        # 2. Crear el Usuario Administrador / Doctor
        print(f"-> Creando Doctor Admin (Email: admin@apolodigital.lat | Pass: {plain_password})...")
        await conn.execute(text("""
            INSERT INTO users (id, full_name, email, hashed_password, roles, is_active, tenant_id, created_at, updated_at) 
            VALUES (:id, :name, :email, :pwd, :roles, true, :tenant_id, :now, :now)
        """), {
            "id": admin_id,
            "name": "Dr. Edwin Rivero",
            "email": "admin@apolodigital.lat",
            "pwd": hashed_pwd,
            "roles": '["ADMIN", "DOCTOR"]',
            "tenant_id": tenant_id,
            "now": datetime.utcnow()
        })
        
        # 3. Inyectar Pacientes Falsos
        print("-> Inyectando 3 pacientes de prueba...")
        pacientes = [
            {"id": uuid.uuid4(), "nombre": "Carlos Mamani", "telefono": "+59171234567"},
            {"id": uuid.uuid4(), "nombre": "Lucía Quispe", "telefono": "+59179876543"},
            {"id": uuid.uuid4(), "nombre": "Roberto Vargas", "telefono": "+59175554433"}
        ]
        
        for p in pacientes:
            # Asumiendo columnas estándar para la tabla patients. Ajusta si tienes first_name/last_name separados
            await conn.execute(text("""
                INSERT INTO patients (id, tenant_id, full_name, phone, created_at, updated_at) 
                VALUES (:id, :tenant_id, :name, :phone, :now, :now)
            """), {
                "id": p["id"],
                "tenant_id": tenant_id,
                "name": p["nombre"],
                "phone": p["telefono"],
                "now": datetime.utcnow()
            })
            
    await engine.dispose()
    print("¡Inyección completada con éxito! Ya puedes entrar al Swagger.")

if __name__ == "__main__":
    # Windows requiere esta política de bucle para asyncpg a veces
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(run_seed())