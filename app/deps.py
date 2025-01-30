from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlmodel import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from config import Settings
from handler import MessageHandler


async def get_settings(request: Request) -> Settings:
    assert request.app.state.settings, "Settings not initialized"
    return request.app.state.settings


def get_db_session(request: Request) -> Session:
    assert request.app.state.db_engine, "Database engine not initialized"
    with Session(request.app.state.db_engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


async def get_db_async_session(request: Request) -> AsyncSession:
    assert request.app.state.db_engine, "Database engine not initialized"
    async with AsyncSession(request.app.state.db_engine) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_handler(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_db_async_session)],
) -> MessageHandler:
    return MessageHandler(settings, session)
