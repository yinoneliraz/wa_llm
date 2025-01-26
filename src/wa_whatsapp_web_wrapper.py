import base64
import requests
from typing import Dict, Any
from pydantic import BaseModel
from config import Settings



class WhatsAppMessage(BaseModel):
    phone: str
    message: str

class WhatsAppDevice(BaseModel):
    name: str
    #  Will end with @s.whatsapp.net
    device: str

class WhatsAppDevicesResponse(BaseModel):
    code: str
    message: str
    results: list[WhatsAppDevice]
 
settings = Settings()
host = settings.WHATSAPP_HOST

def return_whatsapp_basic_auth() -> Dict[str, str]:
    if not settings.WHATSAPP_BASIC_AUTH_USER or settings.WHATSAPP_BASIC_AUTH_PASSWORD:
        return {}
    
    credentials = f"{settings.WHATSAPP_BASIC_AUTH_USER}:{settings.WHATSAPP_BASIC_AUTH_PASSWORD}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    print(f"Basic {encoded_credentials}")
    return {"Authorization": f"Basic {encoded_credentials}"}

def send_whatsapp_message(message: WhatsAppMessage) -> Dict[str, Any]:
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

    try:
        response = requests.post(
            f"{host}/send/message",
            headers=headers,
            json=message.model_dump(),
            timeout=10  # 10 seconds timeout
        )
        response.raise_for_status()
        return response.json()
                
    except requests.RequestException as e:
        print(f"Error sending WhatsApp message: {str(e)}")
        raise

def get_whatsapp_devices() -> WhatsAppDevicesResponse:
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
    try:
        response = requests.get(
            f"{host}/app/devices",
            headers=headers,
            timeout=10  # 10 seconds timeout
        )
        response.raise_for_status()
        return WhatsAppDevicesResponse.model_validate(response.json())
                
    except requests.RequestException as e:
        print(f"Error getting WhatsApp devices: {str(e)}")
        raise