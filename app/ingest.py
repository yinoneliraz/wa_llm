# TODO: This is a test entrypoint, remove it when we have a proper way to run the daily ingest
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from config import Settings
from daily_ingest.daily_ingest import topicsLoader
from voyageai.client_async import AsyncClient

if __name__ == "__main__":
    settings = Settings()

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=settings.log_level,
    )

    # Create engine with pooling configuration
    engine = create_async_engine(settings.db_uri)
    db_session = AsyncSession(engine)

    embedding_client = AsyncClient(api_key=settings.voyage_api_key, max_retries=5)
    topics_loader = topicsLoader()

    async def main():
        await topics_loader.load_topics_for_all_groups(db_session, embedding_client)

    asyncio.run(main())
