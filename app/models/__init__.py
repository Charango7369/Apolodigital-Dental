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

# Importaciones directas (si alguna falla, nos enteraremos inmediatamente en los logs)
from app.modules.patients.models import Patient
from app.modules.appointments.models import Appointment


from app.modules.inventory.models import InventoryItem
from app.modules.billing.models import Invoice
from app.modules.odontogram.models import Odontogram  
from app.modules.notifications.models import Notification