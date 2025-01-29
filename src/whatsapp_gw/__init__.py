import base64
from typing import Dict, Generic, TypeVar

import httpx
from pydantic import BaseModel

from src.config import Settings


class MessageRequest(BaseModel):
    phone: str
    message: str


class MessageResponsePayload(BaseModel):
    message_id: str
    status: str


class DeviceResponsePayload(BaseModel):
    name: str
    #  Will end with @s.whatsapp.net
    device: str


T = TypeVar("T")


class WhatsappResponse(BaseModel, Generic[T]):
    code: str
    message: str
    results: T


settings = Settings()  # todo, fix this - shouldnt be global


def return_whatsapp_basic_auth() -> Dict[str, str]:
    if not (settings.whatsapp_basic_auth_user or settings.whatsapp_basic_auth_password):
        return {}

    credentials = (
        f"{settings.whatsapp_basic_auth_user}:{settings.whatsapp_basic_auth_password}"
    )
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {encoded_credentials}"}


async def send_whatsapp_message(
    message: MessageRequest,
) -> WhatsappResponse[MessageResponsePayload]:
    """
    Send a WhatsApp message using the API.

    Args:
        message: WhatsAppMessage object containing phone and message
        base_url: Base URL of the WhatsApp API service

    Returns:
        Dict containing the API response

    Raises:
        requests.RequestException: If the request fails
    """
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }
    headers.update(return_whatsapp_basic_auth())

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.whatsapp_host}/send/message",
            headers=headers,
            json=message.model_dump(),
            timeout=10,  # 10 seconds timeout
        )
        response.raise_for_status()
        return WhatsappResponse[MessageResponsePayload].model_validate_json(
            response.content
        )


async def get_whatsapp_devices() -> WhatsappResponse:
    """
    Get information about connected WhatsApp devices/sessions.

    Returns:
        WhatsAppDevicesResponse containing the device information

    Raises:
        requests.RequestException: If the request fails
        ValidationError: If the response doesn't match the expected schema
    """
    headers = {
        "Accept": "application/json, text/plain, */*",
    }
    headers.update(return_whatsapp_basic_auth())
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.whatsapp_host}/app/devices",
            headers=headers,
            timeout=10,  # 10 seconds timeout
        )
        response.raise_for_status()
        return WhatsappResponse[list[DeviceResponsePayload]].model_validate_json(
            response.content
        )
