import json
from claude_wrapper import prompt
from webhook_logic_pydantic import WebhookMessage
from wa_whatsapp_web_wrapper import send_whatsapp_message, WhatsAppMessage
from db import get_n_latest_messages_from_channel
from config import Settings

settings = Settings()

def route_message(message: WebhookMessage) -> None:
    phone = extract_number_from_webhook_message(message)
    group_name = extract_group_name(message)

    phone_or_group = group_name if group_name != "" else phone
    # if I am in the message mention then:
    if check_if_i_am_mentioned(message.message.text):
        if "hey" in message.message.text:
            # send message to whatsapp..
            reply = f"its the voice of my mother"
            send_whatsapp_message(WhatsAppMessage(phone=phone_or_group, message=reply))
    # if the message includes "hey @username" I reply "its the voice of my mother"
    # if the message includes "someone is looking for you on the phone" If its not I don't aggrees "

        if "summarize" in message.message.text:
            messages = get_n_latest_messages_from_channel(phone, group_name, 5)
            messages_str = json.dumps(messages)
            response = prompt(messages_str, "Please summarize the following messages in a few words")
            send_whatsapp_message(WhatsAppMessage(phone=phone_or_group, message=response))


def check_if_i_am_mentioned(message: str) -> bool:

    # TODO: migrate from using my number from from env variable to /devices endpoint.
    # at least validate that the message is from a device that is connected to my number
    MY_NUMBER = settings.MY_NUMBER
    
    return f"@{MY_NUMBER}" in message

def extract_number_from_webhook_message(message: WebhookMessage) -> str:
    # POSTFIX = "@s.whatsapp.net"
    number_candidate = message.from_.split("@")[0]
    number = number_candidate.split(":")[0]
    return number
    # return f"{number}{POSTFIX}"

def extract_group_name(message: WebhookMessage) -> str:
    GROUP_POSTFIX = "@g.us"

    if not " in " in message.from_:
        return ""
    group_candidate = message.from_.split(" in ")[1]
    if GROUP_POSTFIX in group_candidate:
        return group_candidate.split(GROUP_POSTFIX)[0]
    return ""
