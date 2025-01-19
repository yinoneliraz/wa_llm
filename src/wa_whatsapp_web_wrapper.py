import os
from typing import Dict, Any
import requests
from pydantic import BaseModel

class WhatsAppMessage(BaseModel):
    phone: str
    message: str

host = os.getenv("WHATSAPP_HOST")

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
