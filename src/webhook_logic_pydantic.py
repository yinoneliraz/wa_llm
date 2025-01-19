from pydantic import BaseModel, Field
from typing import Optional

class MessageContent(BaseModel):
    id: str
    text: str

class WebhookMessage(BaseModel):
    from_: str = Field(..., alias="from", description="The sender's ID including group context if applicable")
    message: Optional[MessageContent] = Field(None, description="The message content if present")
    pushname: str = Field(..., description="The sender's display name")
    forwarded: Optional[bool] = Field(None, description="Whether the message was forwarded")
    timestamp: str = Field(..., description="Message timestamp in ISO format")
