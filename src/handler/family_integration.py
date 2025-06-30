"""
Family Bot Integration Module

This module provides the integration point for family functionality.
It can be easily imported and removed without affecting existing code.

To integrate:
1. Import this module in src/handler/__init__.py
2. Add family_handler to MessageHandler
3. Call it in the message processing pipeline

To remove:
1. Remove the import and calls
2. The existing bot functionality remains unchanged
"""

import logging
from sqlmodel.ext.asyncio.session import AsyncSession
from voyageai.client_async import AsyncClient

from models import Message
from whatsapp import WhatsAppClient
from .family_handler import FamilyHandler

logger = logging.getLogger(__name__)


class FamilyIntegration:
    """Integration class for family functionality"""
    
    def __init__(
        self,
        session: AsyncSession,
        whatsapp: WhatsAppClient,
        embedding_client: AsyncClient,
    ):
        self.family_handler = FamilyHandler(session, whatsapp, embedding_client)
    
    async def should_handle_family_command(self, message: Message) -> bool:
        """
        Check if this message should be handled by family bot
        
        Conditions:
        1. Message has text
        2. Message is from a group
        3. Group has family_group=True (you'll need to set this manually)
        4. Message contains family-related keywords
        """
        if not message or not message.text or not message.group:
            return False
            
        # For now, check if group is managed (you can add family_group check later)
        # When you add the family_group column, replace this with:
        # return message.group.family_group
        
        # Temporary: Check if message contains family keywords
        family_keywords = [
            # English keywords
            "grocery", "groceries", "shopping", "list", "buy", "store",
            "remind", "reminder", "remember", 
            "baby", "toddler", "feeding", "nap", "diaper", "schedule",
            # Hebrew keywords
            "קניות", "רשימה", "רשימת קניות", "תזכורת", "תזכיר",
            "תינוק", "פעוט", "האכלה", "שינה", "חיתול", "לוח זמנים"
        ]
        
        text_lower = message.text.lower()
        return any(keyword in text_lower for keyword in family_keywords)
    
    async def handle_family_message(self, message: Message):
        """Handle a family-related message"""
        try:
            await self.family_handler(message)
        except Exception as e:
            logger.error(f"Error in family handler: {e}")


# Example integration code for MessageHandler:
"""
# In src/handler/__init__.py, add to MessageHandler.__init__:

from .family_integration import FamilyIntegration

class MessageHandler(BaseHandler):
    def __init__(self, session, whatsapp, embedding_client):
        # ... existing code ...
        self.family_integration = FamilyIntegration(session, whatsapp, embedding_client)
        
    async def __call__(self, payload):
        # ... existing code ...
        
        # Add this after storing the message:
        if message and message.text:
            # Check if this is a family command
            if await self.family_integration.should_handle_family_command(message):
                await self.family_integration.handle_family_message(message)
                return  # Handle family command and return
            
            # Continue with existing logic...
            if message.has_mentioned(await self.whatsapp.get_my_jid()):
                await self.router(message)
"""