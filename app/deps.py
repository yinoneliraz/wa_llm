from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings
from handler import MessageHandler
from whatsapp import WhatsAppClient


async def get_settings(request: Request) -> Settings:
    assert request.app.state.settings, "Settings not initialized"
    return request.app.state.settings


async def get_db_async_session(request: Request) -> AsyncSession:
    assert request.app.state.db_engine, "Database engine not initialized"
    async with AsyncSession(request.app.state.db_engine) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_whatsapp(request: Request) -> WhatsAppClient:
    assert request.app.state.whatsapp, "WhatsApp client not initialized"
    return request.app.state.whatsapp


async def get_handler(
    session: Annotated[AsyncSession, Depends(get_db_async_session)],
    whatsapp: Annotated[WhatsAppClient, Depends(get_whatsapp)],
) -> MessageHandler:
    return MessageHandler(session, whatsapp)
