from db import store_message
from message_router import route_message
from typing import Any
from webhook_logic_pydantic import WebhookMessage

def webhook_logic(payload: dict[str, Any]) -> int:

    message = WebhookMessage.model_validate(payload)

    message_id = store_message(message.model_dump(by_alias=True))
    print(f"message_id is {message_id}, payload is {payload}")

    # Only route if there's a message content
    if message.message:
        route_message(message)

    return message_id