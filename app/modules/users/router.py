# app/modules/users/router.py
from fastapi import APIRouter, Depends, HTTPException, status

#from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import traceback  # 👈 Importamos la herramienta de rastreo

from app.db.session import get_db
from app.modules.users.schemas import UserCreate
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService
# 🚨 Importamos el guardián que acabamos de crear
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User as UserModel
from app.modules.users.schemas import UserResponse # Tu esquema de respuesta de usuario


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
    

# 🔐 ESTE ENDPOINT ACTIVARÁ EL CANDADO EN SWAGGER
@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: UserModel = Depends(get_current_user)):
    """
    Devuelve el perfil del usuario autenticado basado en el Token JWT.
    """
    return current_user