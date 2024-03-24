from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool

from mountaineer.database.config import DatabaseConfig, PoolType
from mountaineer.dependencies import CoreDependencies
from mountaineer.logging import LOGGER

# We share the connection pool across the entire process
GLOBAL_ENGINE: dict[str, AsyncEngine] = {}


def engine_from_config(config: DatabaseConfig, force_new: bool = False):
    global GLOBAL_ENGINE

    if not config.SQLALCHEMY_DATABASE_URI:
        raise RuntimeError(f"No SQLALCHEMY_DATABASE_URI set: {config}")

    if force_new or str(config.SQLALCHEMY_DATABASE_URI) not in GLOBAL_ENGINE:
        GLOBAL_ENGINE[str(config.SQLALCHEMY_DATABASE_URI)] = create_async_engine(
            str(config.SQLALCHEMY_DATABASE_URI),
            poolclass=(
                NullPool
                if config.DATABASE_POOL_TYPE == PoolType.NULL
                else AsyncAdaptedQueuePool
            ),
        )

    return GLOBAL_ENGINE[str(config.SQLALCHEMY_DATABASE_URI)]


async def get_db(
    config: DatabaseConfig = Depends(
        CoreDependencies.get_config_with_type(DatabaseConfig)
    ),
):
    return engine_from_config(config)


async def get_db_session(
    engine: AsyncEngine = Depends(get_db),
):
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        try:
            yield session
        except Exception as e:
            # SQLAlchemy provides rollback support automatically with the async session manager
            LOGGER.exception(
                f"Error in user code, rolling back uncommitted db changes: {e}"
            )
            raise


async def unregister_global_engine():
    global GLOBAL_ENGINE
    if GLOBAL_ENGINE is not None:
        for engine in GLOBAL_ENGINE.values():
            await engine.dispose()
        GLOBAL_ENGINE = {}
