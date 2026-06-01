from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import logger

from app.middlewares.logging_middleware import LoggingMiddleware
from app.middlewares.tenant_middleware import TenantMiddleware
from app.middlewares.error_middleware import ErrorHandlingMiddleware

from app.db.base import Base
from app.db.session import engine

# --- Modelos globales ---
import app.models 

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

    # Crear tablas async
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
# Routers
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
# Health Check
# =========================================================


@app.get(
    "/health",
    tags=["Health"],
)
async def health_check():
    return {
        "success": True,
        "message": "API running correctly",
        "data": {
            "project": settings.PROJECT_NAME,
            "environment": settings.ENVIRONMENT,
            "status": "healthy",
        },
    }


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