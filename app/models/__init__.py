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

# Importar el resto de modelos (ajusta los nombres de clase si son diferentes)
try:
    from app.modules.patients.models import Patient
except ImportError:
    pass

try:
    from app.modules.appointments.models import Appointment
except ImportError:
    pass

try:
    from app.modules.inventory.models import InventoryItem
except ImportError:
    pass

try:
    from app.modules.billing.models import Invoice
except ImportError:
    pass

try:
    from app.modules.odontogram.models import OdontogramEntry
except ImportError:
    pass

try:
    from app.modules.notifications.models import Notification
except ImportError:
    pass