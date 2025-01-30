from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from sqlmodel import SQLModel, create_engine

import models  # noqa
from config import Settings
from deps import get_handler
from handler import MessageHandler

settings = Settings()  # pyright: ignore [reportCallIssue]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global settings
    app.state.settings = settings

    engine = create_engine(settings.db_uri, pool_size=10, max_overflow=20)
    SQLModel.metadata.create_all(engine)
    app.state.db_engine = engine

    try:
        yield
    finally:
        app.state.db_pool.closeall()


# Initialize FastAPI app
app = FastAPI(title="Webhook API", lifespan=lifespan)


@app.post("/webhook")
async def webhook(
    payload: models.WhatsAppWebhookPayload,
    handler: Annotated[MessageHandler, Depends(get_handler)],
) -> str:
    if payload.message and payload.from_:
        await handler(payload)

    return "ok"


if __name__ == "__main__":
    import uvicorn

    print(f"Running on {settings.host}:{settings.port}")

    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
