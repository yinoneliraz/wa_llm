import os
import json
from claude_wrapper import prompt
from webhook_logic_pydantic import WebhookMessage
from wa_whatsapp_web_wrapper import send_whatsapp_message, WhatsAppMessage
from db import get_n_latest_messages_from_channel
def route_message(message: WebhookMessage) -> None:

    # if I am in the message mention then:
    if check_if_i_am_mentioned(message.message.text):
        if "hey" in message.message.text:
            # send message to whatsapp..
            reply = f"its the voice of my mother"
            send_whatsapp_message(WhatsAppMessage(phone=message.from_, message=reply))
    # if the message includes "hey @username" I reply "its the voice of my mother"
    # if the message includes "someone is looking for you on the phone" If its not I don't aggrees "

        if "summarize" in message.message.text:
            messages = get_n_latest_messages_from_channel(message.from_, 5)
            messages_str = json.dumps(messages)
            response = prompt(messages_str, "Please summarize the following messages in a few words")
            send_whatsapp_message(WhatsAppMessage(phone=message.from_, message=response))


def check_if_i_am_mentioned(message: str) -> bool:
    MY_NUMBER = os.getenv("MY_NUMBER")
    return f"@{MY_NUMBER}" in message