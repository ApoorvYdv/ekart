from contextlib import asynccontextmanager

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from .utils.common.logger import logger


@asynccontextmanager
async def session_context(engine: AsyncEngine, client_name: str = None):
    session = AsyncSession(engine)
    schema_translate_map = {
        None: client_name,
    }
    await session.connection(
        execution_options={
            "schema_translate_map": schema_translate_map,
        }
    )
    try:
        yield session
    except Exception as ex:
        await session.rollback()
        if isinstance(ex, HTTPException):
            raise
        logger.error(f"An error occured during a transaction: {ex}")

    finally:
        await session.close()
