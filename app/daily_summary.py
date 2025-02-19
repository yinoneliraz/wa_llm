# TODO: This is a test entrypoint, remove it when we have a proper way to run the daily ingest
import asyncio
import logging

import logfire
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from config import Settings
from daily_summary_sync import daily_summary_sync
from whatsapp import WhatsAppClient


async def main():
    settings = Settings()

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=settings.log_level,
    )
    logfire.configure()

    whatsapp = WhatsAppClient(
        settings.whatsapp_host,
        settings.whatsapp_basic_auth_user,
        settings.whatsapp_basic_auth_password,
    )
    
    # Create engine with pooling configuration
    db_engine = create_async_engine(settings.db_uri)
    
    async with AsyncSession(db_engine) as session:
        try:
            await daily_summary_sync(session, whatsapp)
            await session.commit()
        except Exception:
            await session.rollback()
            raise

if __name__ == "__main__":
    asyncio.run(main())
