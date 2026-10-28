# app/models/__init__.py
"""
Este archivo importa todos los modelos para asegurar que SQLAlchemy
los registre en Base.metadata antes de crear las tablas.
El orden es importante: primero las tablas padre (tenants), luego las hijas.
"""

# Importar primero Tenant (no depende de nadie)
from app.modules.tenants.models import Tenant

# Importar User (depende de Tenant por el TenantMixin)
from app.modules.users.models import User

# FASE 2: Modelo de persistencia y rotación de tokens
from app.modules.auth.models import RefreshToken

# FASE 4: Modelo de bitácora de auditoría médica inmutable
from app.modules.audit.models import MedicalAuditLog

# Importaciones directas
from app.modules.patients.models import Patient
from app.modules.appointments.models import Appointment
from app.modules.inventory.models import InventoryItem
from app.modules.odontogram.models import Odontogram  
from app.modules.notifications.models import Notification
from app.modules.billing.models import AccountReceivable, Payment
