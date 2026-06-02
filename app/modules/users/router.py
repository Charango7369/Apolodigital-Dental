# app/modules/users/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import traceback  # 👈 Importamos la herramienta de rastreo

from app.db.session import get_db
from app.modules.users.schemas import UserCreate
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/")
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    try:  # 👈 Intentamos ejecutar el flujo normal
        repository = UserRepository(db)
        service = UserService(repository)
        return await service.create_user(payload, tenant_id=payload.tenant_id)
        
    except Exception as e:  # 👈 Si algo falla, lo atrapamos y lo exponemos
        print("\n❌ ====== ¡CAPTURA DE ERROR CRÍTICO EN POST /USERS/ ====== ❌")
        traceback.print_exc()  # Esto imprimirá el error real completo en tu consola de Railway
        print("❌ ======================================================= ❌\n")
        raise e  # Mantiene el error 500 para el cliente pero ya lo dejó grabado