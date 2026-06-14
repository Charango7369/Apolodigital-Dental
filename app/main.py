from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute # <-- Añadido para la Opción B

from app.core.config import settings
from app.core.logging import logger

from app.middlewares.logging_middleware import LoggingMiddleware
from app.middlewares.tenant_middleware import TenantMiddleware
from app.middlewares.error_middleware import ErrorHandlingMiddleware

# --- Modelos globales (necesario para que Alembic los detecte si se importa este archivo) ---
import app.models 

# Imports limpios y sin duplicados
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.patients.router import router as patients_router
from app.modules.appointments.router import router as appointments_router
from app.modules.inventory.router import router as inventory_router
from app.modules.billing.router import router as billing_router
from app.modules.odontogram.router import router as odontogram_router
from app.modules.notifications.router import router as notifications_router
from app.modules.reports.router import router as reports_router
from app.modules.files.router import router as files_router
from app.modules.tenants.router import router as tenants_router
from app.modules.health.router import router as health_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup / Shutdown Events
    """
    logger.info("🚀 Starting Dental SaaS Backend")
    # Base.metadata.create_all ha sido eliminado. 
    # La responsabilidad del DDL ahora es 100% de Alembic.
    yield
    logger.info("🛑 Shutting down Dental SaaS Backend")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# =========================================================
# Middlewares
# =========================================================

app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(TenantMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# Routers (Inclusiones únicas)
# =========================================================

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(tenants_router)
app.include_router(patients_router)
app.include_router(appointments_router)
app.include_router(inventory_router)
app.include_router(billing_router)
app.include_router(odontogram_router)
app.include_router(notifications_router)
app.include_router(reports_router)
app.include_router(files_router)
app.include_router(health_router)

# =========================================================
# Root Endpoint
# =========================================================

@app.get(
    "/",
    tags=["Root"],
)
async def root():
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Dental SaaS API Running",
            "data": {
                "docs": "/docs",
                "redoc": "/redoc",
                "version": "1.0.0",
            },
        },
    )

# =========================================================
# Global Exception Handlers
# =========================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal Server Error",
            "data": None,
        },
    )

# =========================================================
# OpenAPI Operation ID Simplification (Opción B)
# =========================================================
# Esto evita colisiones iterando sobre todas las rutas cargadas
# y asignando el nombre de la función en Python como ID único.
for route in app.routes:
    if isinstance(route, APIRoute):
        route.operation_id = route.name