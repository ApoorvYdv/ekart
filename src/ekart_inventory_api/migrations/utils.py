from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from .config.database_config import DatabaseConfig

engine = create_engine(
    DatabaseConfig().build_db_url(async_driver=False),
)


def get_schemas():
    session = Session(engine)
    result = session.execute(text("SELECT name from config.agencies;"))
    schemas = [row[0] for row in result]
    session.close()

    return schemas
