import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from warnings import warn

# Add src to Python path
current_dir = Path(__file__).parent.parent
src_dir = current_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
import logging
import logfire

from api import status, webhook
import models  # noqa
from config import Settings
from whatsapp import WhatsAppClient
from whatsapp.init_groups import gather_groups
from voyageai.client_async import AsyncClient
from scheduler.family_scheduler import FamilyScheduler

settings = Settings()  # pyright: ignore [reportCallIssue]


async def run_family_scheduler_periodically(async_session, whatsapp):
    """Background task to run family scheduler every minute"""
    logger = logging.getLogger(__name__)
    logger.info("Starting family scheduler background task")
    
    while True:
        try:
            # Wait 60 seconds before each run
            await asyncio.sleep(60)
            
            # Run scheduler in a new session
            async with async_session() as session:
                try:
                    scheduler = FamilyScheduler(session, whatsapp)
                    await scheduler.run_periodic_tasks()
                    await session.commit()
                except Exception as e:
                    logger.error(f"Family scheduler task failed: {e}")
                    await session.rollback()
                    
        except asyncio.CancelledError:
            logger.info("Family scheduler background task cancelled")
            break
        except Exception as e:
            logger.error(f"Unexpected error in family scheduler: {e}")
            # Continue running even if there's an error
            await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global settings
    # Create and configure logger
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=settings.log_level,
    )

    app.state.settings = settings

    app.state.whatsapp = WhatsAppClient(
        settings.whatsapp_host,
        settings.whatsapp_basic_auth_user,
        settings.whatsapp_basic_auth_password,
    )

    if settings.db_uri.startswith("postgresql://"):
        warn("use 'postgresql+asyncpg://' instead of 'postgresql://' in db_uri")
    engine = create_async_engine(
        settings.db_uri,
        pool_size=20,
        max_overflow=40,
        pool_timeout=30,
        pool_pre_ping=True,
        pool_recycle=600,
        future=True,
    )
    logfire.instrument_sqlalchemy(engine)
    async_session = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    asyncio.create_task(gather_groups(engine, app.state.whatsapp))
    
    # Start family scheduler background task
    scheduler_task = asyncio.create_task(
        run_family_scheduler_periodically(async_session, app.state.whatsapp)
    )

    app.state.db_engine = engine
    app.state.async_session = async_session
    app.state.embedding_client = AsyncClient(
        api_key=settings.voyage_api_key, max_retries=settings.voyage_max_retries
    )
    app.state.scheduler_task = scheduler_task
    
    try:
        yield
    finally:
        # Cancel scheduler task
        if scheduler_task and not scheduler_task.done():
            scheduler_task.cancel()
            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass
        await engine.dispose()


# Initialize FastAPI app
app = FastAPI(title="Webhook API", lifespan=lifespan)

logfire.configure()
logfire.instrument_pydantic_ai()
logfire.instrument_fastapi(app)
logfire.instrument_httpx(capture_all=True)
logfire.instrument_system_metrics()


app.include_router(webhook.router)
app.include_router(status.router)

if __name__ == "__main__":
    import uvicorn

    print(f"Running on {settings.host}:{settings.port}")

    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
