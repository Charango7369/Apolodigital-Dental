from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute 

from app.core.config import settings
from app.core.logging import logger

from app.middlewares.logging_middleware import LoggingMiddleware
from app.middlewares.tenant_middleware import TenantMiddleware
from app.middlewares.error_middleware import ErrorHandlingMiddleware
from app.middlewares.csrf_middleware import CSRFMiddleware
from app.middlewares.security_headers_middleware import SecurityHeadersMiddleware

# --- Modelos globales ---
import app.models 

# Routers
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
from app.modules.tenants.staff_router import router as clinics_staff_router, tenants_staff_router
from app.modules.audit.router import router as audit_router
from app.modules.health.router import router as health_router
from app.modules.dashboard.router import router as dashboard_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Dental SaaS Backend")
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
# Middlewares (El orden importa: el último añadido es el primero en recibir la petición)
# =========================================================

app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(TenantMiddleware)
app.add_middleware(CSRFMiddleware)

# --- Configuración CORS segura (Outermost para responder preflights OPTIONS) ---
origins = [
    "http://localhost:5173",   # Vite
    "http://localhost:3000",   # Create React App
    "http://127.0.0.1:5173",   # Variante con 127.0.0.1
    "http://127.0.0.1:3000",   # Variante con 127.0.0.1
    "https://dental-frontend.edwinjrivero.workers.dev",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # Lista explícita de orígenes permitidos
    allow_credentials=True,       # Requerido para envío de Cookies HttpOnly
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# Routers
# =========================================================

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(tenants_router)
app.include_router(clinics_staff_router)
app.include_router(tenants_staff_router)
app.include_router(patients_router)
app.include_router(appointments_router)
app.include_router(inventory_router)
app.include_router(billing_router)
app.include_router(odontogram_router)
app.include_router(notifications_router)
app.include_router(reports_router)
app.include_router(files_router)
app.include_router(audit_router)
app.include_router(health_router)
app.include_router(dashboard_router)

# =========================================================
# Root Endpoint
# =========================================================

@app.get("/", tags=["General"])
async def root():
    return {
        "success": True,
        "message": "Dental SaaS API Running",
        "data": {
            "version": "1.0.0",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


def custom_generate_unique_id(route: APIRoute):
    return f"{route.tags[0]}-{route.name}"

app.router.generate_unique_id_function = custom_generate_unique_id
