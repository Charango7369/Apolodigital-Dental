# app/modules/auth/router.py
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.core.config import settings
from app.core.rate_limiter import (
    get_client_ip, 
    rate_limiter_login, 
    rate_limiter_mfa, 
    rate_limit_storage
)
from app.core.security import (
    create_mfa_pending_token,
    decode_token,
    verify_password,
)
from app.core.totp import (
    generate_totp_secret, 
    generate_totp_uri, 
    verify_totp
)
from app.core.cache import token_cache
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import (
    GenericStatusResponse,
    LoginResponse,
    LogoutRequest,
    MFAChallengeRequest,
    MFADisableRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    RefreshTokenRequest,
    TokenRefreshResponse,
    UserResponse,
)
from app.modules.auth.service import AuthService
from app.modules.users.models import User as UserModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _build_user_response(user: UserModel) -> UserResponse:
    """Convierte el modelo de usuario SQLAlchemy en el schema Pydantic."""
    roles_raw = user.roles if isinstance(user.roles, list) else ["RECEPTIONIST"]
    roles_json = json.dumps(roles_raw)

    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        roles=roles_json,
        tenant_id=user.tenant_id,
    )


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(rate_limiter_login)])
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Inicio de sesión protegido con Rate Limiting distribuido (5 intentos / 15 min):
    - Si el usuario no tiene MFA: emite par Access Token (15 min) + Refresh Token (7 días RTR).
    - Si el usuario tiene MFA activado: emite token restringido con scope 'mfa_pending' (10 min).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Correo electrónico o contraseña incorrectos",
        headers={"WWW-Authenticate": "Bearer"},
    )

    clean_email = (form_data.username or "").strip().lower()
    client_ip = get_client_ip(request)

    # Rate limiting secundario por cuenta específica + IP para evitar ataques dirigidos de diccionario
    account_key = f"login_account:{clean_email}:{client_ip}"
    allowed, _, retry_after = await rate_limit_storage.is_allowed(
        account_key,
        max_requests=settings.RATE_LIMIT_LOGIN_MAX,
        window_seconds=settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS,
    )
    if not allowed:
        logger.warning(f"[RATE LIMIT] Bloqueo de cuenta/IP tras fallos repetidos: {account_key}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Demasiados intentos fallidos para esta cuenta. Bloqueada temporalmente por {retry_after} segundos.",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        # 🔍 1. Buscar al usuario
        query = select(UserModel).where(UserModel.email == clean_email)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        # 🛑 2. Validación en tiempo constante (mitigación de timing attack y enumeración)
        if not user or not user.is_active:
            verify_password(form_data.password, "$2b$12$e80yqZ65yCfqGZ2gTf5GVuF1aKsmZ2Oq7m9eO0u9R6hD4uB8rE.8G")
            raise credentials_exception

        # 🔑 3. Verificación criptográfica estricta de contraseña
        if not verify_password(form_data.password, user.hashed_password):
            logger.warning(f"Intento de autenticación fallido para: {clean_email}")
            raise credentials_exception

        user_agent = request.headers.get("user-agent")

        # 🔐 4. Evaluación de Autenticación Multifactor (MFA TOTP)
        if user.mfa_enabled:
            logger.info(f"Usuario {user.id} requiere desafío MFA para completar autenticación.")
            mfa_pending_token = create_mfa_pending_token(user_id=user.id, tenant_id=user.tenant_id)
            return LoginResponse(
                mfa_required=True,
                mfa_token=mfa_pending_token,
                message="Autenticación en dos pasos requerida. Ingrese su código TOTP de 6 dígitos.",
            )

        # 🎫 5. Credenciales válidas sin MFA: Generar Access Token (15m) + Refresh Token (RTR)
        access_token, refresh_token = await AuthService.create_user_session(
            db, user, client_ip=client_ip, user_agent=user_agent
        )
        user_response = _build_user_response(user)

        logger.info(f"Autenticación directa exitosa para usuario {user.id} en tenant {user.tenant_id}")

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=user_response,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado en /auth/login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor durante la autenticación.",
        )


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_access_token(
    payload: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Rotación Automática de Tokens de Refresco (RTR):
    - Intercambia un Refresh Token válido por un nuevo par de tokens.
    - Si se presenta un token ya consumido o revocado, activa la Detección Forense de Reuso
      e invalida inmediatamente toda la familia de sesiones activas.
    """
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    access_token, new_refresh_token, _ = await AuthService.rotate_refresh_token(
        db, payload.refresh_token, client_ip=client_ip, user_agent=user_agent
    )

    return TokenRefreshResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


@router.post("/logout", response_model=GenericStatusResponse)
async def logout(
    request: Request,
    payload: LogoutRequest = None,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Cierre de sesión seguro:
    - Revoca el Access Token actual en la caché distribuida por su identificador único JTI.
    - Si se provee un refresh_token, invalida la familia completa en base de datos.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token_str = auth_header[7:].strip()
        try:
            claims = decode_token(token_str)
            jti = claims.get("jti")
            if jti:
                await token_cache.revoke_token(jti, ttl_seconds=1800)
        except Exception:
            pass

    if payload and payload.refresh_token:
        await AuthService.revoke_session_by_token(db, payload.refresh_token)

    return GenericStatusResponse(
        success=True,
        message="Sesión cerrada y credenciales revocadas exitosamente.",
    )


# =========================================================
# ENDPOINTS DE AUTENTICACIÓN MULTIFACTOR (MFA TOTP)
# =========================================================

@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Paso 1 de activación MFA:
    Genera un secreto criptográfico Base32 y el URI estándar otpauth://
    El usuario debe escanear el QR o ingresar el secreto en su app autenticadora.
    MFA permanece inactivo hasta que se valide el primer código con /auth/mfa/verify.
    """
    secret = generate_totp_secret()
    
    # Almacenar secreto temporal en usuario (no activo hasta confirmar)
    current_user.mfa_secret = secret
    current_user.mfa_enabled = False
    await db.commit()

    otpauth_url = generate_totp_uri(
        secret=secret,
        account_name=current_user.email,
        issuer="Dental SaaS"
    )

    return MFASetupResponse(
        secret=secret,
        otpauth_url=otpauth_url,
    )


@router.post("/mfa/verify", response_model=GenericStatusResponse)
async def verify_mfa_setup(
    payload: MFAVerifyRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Paso 2 de activación MFA:
    Valida el código TOTP de 6 dígitos introducido por el usuario.
    Si coincide, activa permanentemente 'mfa_enabled = True'.
    """
    if not current_user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe iniciar la configuración con /auth/mfa/setup antes de verificar.",
        )

    is_valid = verify_totp(current_user.mfa_secret, payload.code)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código TOTP inválido o expirado. Verifique la sincronización de hora de su autenticador.",
        )

    current_user.mfa_enabled = True
    await db.commit()

    logger.info(f"MFA TOTP activado exitosamente para el usuario {current_user.id}")
    return GenericStatusResponse(
        success=True,
        message="Autenticación multifactor activada con éxito.",
    )


@router.post("/mfa/challenge", response_model=LoginResponse, dependencies=[Depends(rate_limiter_mfa)])
async def mfa_challenge(
    payload: MFAChallengeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Paso 2 de Login para cuentas con MFA:
    Recibe el token temporal 'mfa_token' (scope mfa_pending) y el código TOTP de 6 dígitos.
    Si el código es correcto, emite los tokens definitivos (Access + Refresh Token con RTR).
    """
    # 1. Validar mfa_token
    try:
        claims = decode_token(payload.mfa_token)
        if claims.get("scope") != "mfa_pending" or claims.get("type") != "mfa_challenge":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de desafío MFA inválido.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = UUID(claims["sub"])
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de desafío MFA inválido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Consultar usuario
    query = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not user.is_active or not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El usuario no tiene una configuración MFA activa o está inactivo.",
        )

    # 3. Validar código TOTP en tiempo constante
    if not verify_totp(user.mfa_secret, payload.code):
        logger.warning(f"[MFA] Código TOTP fallido para usuario {user.id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código de autenticación TOTP incorrecto o expirado.",
        )

    # 4. Éxito: Crear sesión y rotación
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    access_token, refresh_token = await AuthService.create_user_session(
        db, user, client_ip=client_ip, user_agent=user_agent
    )
    user_response = _build_user_response(user)

    logger.info(f"Desafío MFA superado con éxito por usuario {user.id}")

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=user_response,
    )


@router.post("/mfa/disable", response_model=GenericStatusResponse)
async def disable_mfa(
    payload: MFADisableRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Desactivación de MFA:
    Requiere obligatoriamente la contraseña actual del usuario y el código TOTP vigente.
    """
    if not current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La autenticación multifactor no está activa en esta cuenta.",
        )

    # 1. Validar contraseña
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contraseña incorrecta.",
        )

    # 2. Validar código TOTP
    if not verify_totp(current_user.mfa_secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código TOTP incorrecto.",
        )

    # 3. Desactivar
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    await db.commit()

    logger.info(f"MFA desactivado para usuario {current_user.id}")
    return GenericStatusResponse(
        success=True,
        message="Autenticación multifactor desactivada exitosamente.",
    )
