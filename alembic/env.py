from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys
from dotenv import load_dotenv

# Cargar variables desde .env
load_dotenv()

# Agregar el path del proyecto para importar modelos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar metadatos
from src.db.base import Base
from src.db import models

# Configuración de Alembic
config = context.config

# Inyectar la URL manualmente desde variable de entorno
db_url = os.getenv("DATABASE_URL")
if db_url is None:
    raise ValueError("DATABASE_URL is not set in environment variables.")
config.set_main_option("sqlalchemy.url", db_url)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadatos de los modelos para autogenerar migraciones
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Modo offline (sin conexión real a la DB)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Modo online (con engine conectado)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# Selección de modo (offline/online)
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
