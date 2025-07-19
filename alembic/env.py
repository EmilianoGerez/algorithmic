"""Alembic environment configuration module."""

import os
import sys
from logging.config import fileConfig

from alembic import context

from dotenv import load_dotenv

from sqlalchemy import engine_from_config, pool

# Cargar variables desde .env
load_dotenv()

# Agregar el path del proyecto para importar modelos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# TODO: Add database models when database integration is implemented
# from src.db import models
# from src.db.base import Base

# For now, use None as target_metadata since no models are defined yet
target_metadata = None

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
# target_metadata = Base.metadata  # Will be enabled when models are added


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
    config_section = config.get_section(config.config_ini_section)
    if config_section is None:
        raise ValueError("No configuration section found")

    connectable = engine_from_config(
        config_section,
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
