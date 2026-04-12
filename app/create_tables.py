"""One-time script to create all database tables from SQLAlchemy models."""
import asyncio
from db.connection import _get_local_engine
from db.models import Base


async def create():
    engine = _get_local_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created.")


asyncio.run(create())
