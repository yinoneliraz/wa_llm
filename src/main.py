from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from config import get_settings
from db import init_db, get_messages_from_db
from webhook_logic import webhook_logic
from contextlib import asynccontextmanager

# Load settings
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown
    pass

# Initialize FastAPI app
app = FastAPI(title="Webhook API", lifespan=lifespan)

# Pydantic models for request/response validation
class WebhookResponse(BaseModel):
    status: str
    message: str
    id: int

class ErrorResponse(BaseModel):
    error: str
    message: Optional[str] = None
    details: Optional[str] = None

@app.get("/")
async def hello_world() -> str:
    return "Hello, World!"

@app.post("/webhook", response_model=WebhookResponse)
async def webhook(payload: Dict[str, Any]) -> WebhookResponse:
    try:
        if not payload:
            raise HTTPException(
                status_code=400, 
                detail="No payload received"
            )

        message_id = webhook_logic(payload)
        
        return WebhookResponse(
            status="success",
            message="Webhook received and stored and handled",
            id=message_id
        )
    
    except ValueError as validation_error:
        raise HTTPException(
            status_code=400,
            detail=str(validation_error)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process webhook: {str(e)}"
        )

@app.get("/messages")
async def get_messages() -> list:
    try:
        messages = get_messages_from_db()
        return messages
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve messages: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    
    print(f"Running on {settings.HOST}:{settings.PORT}")
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )