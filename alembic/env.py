import sys
import os
from dotenv import load_dotenv
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# 1. Añadir la carpeta raíz del proyecto al sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# 2. Cargar variables de entorno
load_dotenv()

# 3. Importar Base y modelos
from app.db.base import Base
import app.models  # asegúrate de que app/models/__init__.py importe todos tus modelos

# Configuración de Alembic
config = context.config

# 4. Obtener la URL de la base de datos desde el entorno
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise ValueError("CRÍTICO: La variable DATABASE_URL no está definida en tu .env")

# FIX: Alembic usa motor síncrono, así que quitamos '+asyncpg' si existe
sync_database_url = database_url.replace("+asyncpg", "")
config.set_main_option("sqlalchemy.url", sync_database_url)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata de los modelos
from app.db.base import Base

target_metadata = Base.metadata

def run_migrations_offline():
    """Ejecuta migraciones en modo offline."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Ejecuta migraciones en modo online."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
