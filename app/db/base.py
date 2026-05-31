from sqlalchemy.orm import DeclarativeBase

# =============================================================================
# IMPORTACIÓN DE MODELOS
# =============================================================================
# Es CRUCIAL importar todos los modelos que tengan relaciones (Foreign Keys)
# antes de que se ejecute Base.metadata.create_all(). De lo contrario, 
# SQLAlchemy no conocerá la tabla de destino (ej. 'tenants') y fallará.
# =============================================================================

try:
    # Importamos Tenant primero porque User depende de él
    from app.modules.tenants.models import Tenant
except ImportError:
    Tenant = None  # Permitir inicio si el archivo aún no existe

try:
    from app.modules.users.models import User
except ImportError:
    User = None

try:
    from app.modules.patients.models import Patient
except ImportError:
    Patient = None

try:
    from app.modules.appointments.models import Appointment
except ImportError:
    Appointment = None

try:
    from app.modules.inventory.models import InventoryItem
except ImportError:
    InventoryItem = None

try:
    from app.modules.billing.models import Invoice
except ImportError:
    Invoice = None

try:
    from app.modules.odontogram.models import OdontogramEntry
except ImportError:
    OdontogramEntry = None

try:
    from app.modules.notifications.models import Notification
except ImportError:
    Notification = None

# Puedes agregar más imports aquí a medida que crees los archivos models.py


class Base(DeclarativeBase):
    """
    Clase base declarativa para todos los modelos de SQLAlchemy.
    Los modelos deben heredar de esta clase para ser registrados en el metadata.
    """
    pass