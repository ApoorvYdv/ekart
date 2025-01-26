from typing import Any, Callable

import boto3
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base

from .config.database_config import DatabaseConfig


def get_aws_client_provider() -> Callable[..., Any]:
    return boto3.client


db_cfg = DatabaseConfig()


class AsyncDatabaseSession:

    engine = create_async_engine(
        DatabaseConfig().build_db_url(async_driver=True),
    )
    SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def __call__(self):
        return self.engine


get_async_engine = AsyncDatabaseSession()
