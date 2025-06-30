#!/usr/bin/env python3
"""
Family Scheduler Runner

Run this script to process due reminders and send them.
This should be run periodically (every minute) via cron or as a background task.

Usage: python app/family_scheduler.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to Python path
current_dir = Path(__file__).parent.parent
src_dir = current_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import logfire
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from config import Settings
from scheduler.family_scheduler import FamilyScheduler
from whatsapp import WhatsAppClient


async def main():
    """Main scheduler function"""
    settings = Settings()

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=settings.log_level,
    )
    
    # Configure logfire if available
    try:
        logfire.configure()
        logfire.instrument_httpx(capture_all=True)
        logfire.instrument_system_metrics()
    except Exception:
        pass  # Logfire optional

    # Initialize WhatsApp client
    whatsapp = WhatsAppClient(
        settings.whatsapp_host,
        settings.whatsapp_basic_auth_user,
        settings.whatsapp_basic_auth_password,
    )

    # Create database engine
    engine = create_async_engine(settings.db_uri)
    async_session = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    # Run scheduler tasks
    async with async_session() as session:
        try:
            logging.info("Starting family scheduler tasks")
            scheduler = FamilyScheduler(session, whatsapp)
            await scheduler.run_periodic_tasks()
            await session.commit()
            logging.info("Family scheduler tasks completed successfully")
        except Exception as e:
            logging.error(f"Family scheduler failed: {e}")
            await session.rollback()
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
        print("✅ Family scheduler completed successfully")
    except Exception as e:
        print(f"❌ Family scheduler failed: {e}")
        sys.exit(1)