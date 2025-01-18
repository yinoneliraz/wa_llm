from db import store_message
from message_router import route_message
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class MessageContent(BaseModel):
    id: str
    text: str

class WebhookMessage(BaseModel):
    from_: str = Field(..., alias="from", description="The sender's ID including group context if applicable")
    message: Optional[MessageContent] = Field(None, description="The message content if present")
    pushname: str = Field(..., description="The sender's display name")
    forwarded: Optional[bool] = Field(None, description="Whether the message was forwarded")
    timestamp: str = Field(..., description="Message timestamp in ISO format")

def webhook_logic(payload: dict[str, Any]) -> int:

    message = WebhookMessage.model_validate(payload)

    # TODO: add parsing of the message with pydantic latter..
    message_id = store_message(message.model_dump(by_alias=True))
    print(f"message_id is {message_id}, payload is {payload}")


    # TODO: Parse first..
    # route_message(payload)

    return message_id