# app/core/tenant_context.py
"""
Módulo de Gestión de Contexto Multi-Tenant y Seguridad a Nivel de Fila (PostgreSQL RLS).
Administra variables de contexto (ContextVar) aisladas por petición/corutina
y sincroniza el contexto de sesión de base de datos (SET LOCAL / set_config)
con las políticas de Row-Level Security en PostgreSQL.
"""
from contextvars import ContextVar
from typing import Optional, Union
from uuid import UUID
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ContextVars locales a la tarea/corutina asíncrona actual
_current_tenant_id_ctx: ContextVar[Optional[UUID]] = ContextVar("current_tenant_id_ctx", default=None)
_bypass_rls_ctx: ContextVar[bool] = ContextVar("bypass_rls_ctx", default=False)


def set_current_tenant_context(tenant_id: Optional[Union[UUID, str]]) -> None:
    """Establece el tenant_id en el contexto asíncrono actual."""
    if tenant_id is None:
        _current_tenant_id_ctx.set(None)
    elif isinstance(tenant_id, UUID):
        _current_tenant_id_ctx.set(tenant_id)
    else:
        try:
            _current_tenant_id_ctx.set(UUID(str(tenant_id)))
        except (ValueError, TypeError) as e:
            logger.error(f"[RLS] tenant_id inválido suministrado al contexto: {tenant_id}")
            _current_tenant_id_ctx.set(None)


def get_current_tenant_context() -> Optional[UUID]:
    """Obtiene el tenant_id del contexto asíncrono actual."""
    return _current_tenant_id_ctx.get()


def set_bypass_rls(bypass: bool = True) -> None:
    """Establece la bandera de evasión autorizada de RLS (SuperAdmin / Tareas del Sistema)."""
    _bypass_rls_ctx.set(bool(bypass))


def is_bypass_rls() -> bool:
    """Indica si el contexto actual tiene autorización de evasión de RLS."""
    return _bypass_rls_ctx.get()


def clear_tenant_context() -> None:
    """Limpia los ContextVars al finalizar el ciclo de vida de la petición."""
    _current_tenant_id_ctx.set(None)
    _bypass_rls_ctx.set(False)


async def apply_db_tenant_context(
    session: AsyncSession,
    tenant_id: Optional[Union[UUID, str]] = None,
    bypass: Optional[bool] = None
) -> None:
    """
    Sincroniza la conexión de base de datos con las variables de sesión de PostgreSQL:
    1. Si la conexión proviene de un superusuario ('postgres'), cambia al rol no privilegiado 'dental_app'
       para que PostgreSQL aplique obligatoriamente las políticas de RLS.
    2. Configura 'app.current_tenant_id' y 'app.bypass_rls' vía set_config (ámbito de sesión,
       preservado a través de transacciones y sentencias commit).
    3. Si no se especifica tenant ni bypass, adopta postura Default Deny (Fail-Closed).
    """
    # Si el dialecto no es PostgreSQL (ej. SQLite en tests aislados), omitir RLS nativo
    try:
        bind = session.bind
        if bind and bind.dialect.name != "postgresql":
            return
    except Exception:
        pass

    effective_bypass = bypass if bypass is not None else is_bypass_rls()
    effective_tenant = tenant_id if tenant_id is not None else get_current_tenant_context()

    try:
        # En entornos cloud (Railway/Docker) donde DATABASE_URL conecta como 'postgres' (superuser),
        # PostgreSQL omite RLS a menos que se use un rol no privilegiado (NOSUPERUSER NOBYPASSRLS).
        await session.execute(text("SET ROLE dental_app"))
    except Exception:
        # Si el rol 'dental_app' aún no existe (pre-migración) o el usuario ya es no-superuser, ignorar.
        pass

    try:
        if effective_bypass:
            await session.execute(text("SELECT set_config('app.bypass_rls', 'true', false)"))
            await session.execute(text("SELECT set_config('app.current_tenant_id', '', false)"))
        elif effective_tenant:
            await session.execute(text("SELECT set_config('app.bypass_rls', '', false)"))
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(effective_tenant)}
            )
        else:
            # Postura Fail-Closed por defecto: cadenas vacías fuerzan NULL en NULLIF(...::uuid)
            await session.execute(text("SELECT set_config('app.bypass_rls', '', false)"))
            await session.execute(text("SELECT set_config('app.current_tenant_id', '', false)"))
    except Exception as e:
        logger.debug(f"[RLS] Error aplicando set_config en sesión: {e}")


async def reset_db_tenant_context(session: AsyncSession) -> None:
    """
    Restaura el estado original de la conexión al devolverse al pool de SQLAlchemy.
    Previene contaminación cruzada de parámetros entre peticiones recicladas.
    """
    try:
        bind = session.bind
        if bind and bind.dialect.name != "postgresql":
            return
    except Exception:
        pass

    try:
        await session.execute(text("SELECT set_config('app.current_tenant_id', '', false)"))
        await session.execute(text("SELECT set_config('app.bypass_rls', '', false)"))
        await session.execute(text("RESET ROLE"))
    except Exception as e:
        logger.debug(f"[RLS] Error menor restableciendo contexto de BD: {e}")


class TenantDBScope:
    """
    Context manager asíncrono para scripts, tareas en segundo plano o tests
    que requieran ejecutar operaciones en el contexto de un tenant específico o en modo bypass.
    
    Ejemplo:
        async with TenantDBScope(session, tenant_id=clinic_id):
            patients = await session.execute(select(Patient))
    """
    def __init__(
        self,
        session: AsyncSession,
        tenant_id: Optional[Union[UUID, str]] = None,
        bypass: bool = False
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.bypass = bypass

    async def __aenter__(self):
        set_current_tenant_context(self.tenant_id)
        set_bypass_rls(self.bypass)
        await apply_db_tenant_context(self.session, self.tenant_id, self.bypass)
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await reset_db_tenant_context(self.session)
        clear_tenant_context()
