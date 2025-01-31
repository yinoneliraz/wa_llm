# import asyncio
# from typing import AsyncGenerator

# import pytest
# import pytest_asyncio
# from httpx import AsyncClient
# from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
# from sqlmodel import SQLModel

# from app.main import app
# from config import Settings
# from models import Group, Message, Sender


# @pytest.fixture(scope="session")
# def event_loop():
#     """Create an instance of the default event loop for each test case."""
#     loop = asyncio.get_event_loop_policy().new_event_loop()
#     yield loop
#     loop.close()


# @pytest_asyncio.fixture(scope="session")
# async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
#     """Create a test database engine."""
#     engine = create_async_engine(
#         "postgresql+asyncpg://user:password@localhost:5432/test_db",
#         echo=False,
#         future=True,
#     )

#     async with engine.begin() as conn:
#         await conn.run_sync(SQLModel.metadata.drop_all)
#         await conn.run_sync(SQLModel.metadata.create_all)

#     yield engine

#     async with engine.begin() as conn:
#         await conn.run_sync(SQLModel.metadata.drop_all)

#     await engine.dispose()


# @pytest_asyncio.fixture
# async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
#     """Get a test database session."""
#     async with AsyncSession(db_engine) as session:
#         yield session
#         await session.rollback()


# @pytest_asyncio.fixture
# async def client() -> AsyncGenerator[AsyncClient, None]:
#     """Get a test client for making HTTP requests."""
#     async with AsyncClient(app=app, base_url="http://test") as client:
#         yield client


# @pytest.fixture
# def settings() -> Settings:
#     """Get test settings."""
#     return Settings(
#         db_uri="postgresql+asyncpg://user:password@localhost:5432/test_db",
#         my_number="1234567890",
#         whatsapp_host="http://localhost:3000",
#         anthropic_api_key="test_key",
#     ) 