from typing import Annotated

from fastapi import Depends, FastAPI
from sqlmodel import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from config import Settings
from handler import MessageHandler


def get_settings(app: FastAPI = Depends()) -> Settings:
    if app.state.settings is None:
        raise RuntimeError(
            "Settings not initialized. Please wait for application startup to complete."
        )
    return app.state.settings


def get_db_session(app: FastAPI = Depends()):
    with Session(app.state.db_engine) as session:
        yield session
        session.commit()


async def get_db_async_session(app: FastAPI = Depends()):
    async with AsyncSession(app.state.db_engine) as session:
        yield session
        await session.commit()


async def get_handler(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_db_session)],
):
    return MessageHandler(settings, session)
