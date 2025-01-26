# !/bin/python3
# isort: skip_file
from logging import getLogger
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.sql import text
from .config.database_config import DatabaseConfig
from .migrations.utils import get_schemas
# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


config.set_main_option("sqlalchemy.url", DatabaseConfig().build_url_as_string())
schemas = get_schemas()
schemas.append("config")
# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

from .core.models.config.config import Base as ConfigBase
from .core.models.police.police import Base as PoliceBase
from .core.models import Base

# target_metadata = [ConfigBase.metadata, PoliceBase.metadata]
target_metadata = Base.metadata
logger = getLogger("alembic")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        target_metadata=target_metadata,
        transaction_per_migration=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
    with connectable.connect() as connection:
        for schema in schemas:
            logger.info(f"Working for schema {schemas}")
            logger.info(f"Working for schema {schema}")
            
            try:
                connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
                # set search path on the connection, which ensures that
                # PostgreSQL will emit all CREATE / ALTER / DROP statements
                # in terms of this schema by default
                connection.execute(text('set search_path to "%s"' % schema))
                # in SQLAlchemy v2+ the search path change needs to be committed
                connection.commit()

                # make use of non-supported SQLAlchemy attribute to ensure
                # the dialect reflects tables in terms of the current tenant name
                connection.dialect.default_schema_name = schema

                context.configure(
                    connection=connection,
                    target_metadata=target_metadata,
                    transaction_per_migration=True,
                    version_table_schema=schema,
                    include_object=include_object,
                    include_schemas=True,
                )

                with context.begin_transaction():
                    context.run_migrations()
            finally:
                logger.info("Trying to close database connection... ")
                connection.close()
                logger.info(
                    "Connection Status post closing connection: " "closed"
                    if connection.closed
                    else "open"
                )

def include_object(object, name, type_, reflected, compare_to):
    # Only include tables in the 'msw' schema
    if(type_ == 'table' and object.schema in schemas): 
        return True
        
    if(type_ == 'column' and object.table.schema in schemas): 
        return True

    return False

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
