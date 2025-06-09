# This handler is used to handle whatsapp group link spam

import logging
from .base_handler import BaseHandler
from pydantic_ai import Agent
from pydantic import BaseModel
from sqlmodel import Field
from models import Message
from whatsapp.jid import parse_jid

# Creating an object
logger = logging.getLogger(__name__)


class WhatsappGroupLinkSpamHandler(BaseHandler):
        
    async def __call__(self, message: Message):
        pass
 
