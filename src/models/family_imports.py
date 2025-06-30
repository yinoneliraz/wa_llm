# Family Models Import Extension
# Add these imports to src/models/__init__.py to include family models

from .family import GroceryList, GroceryItem, Reminder, ChildScheduleEntry

# Add to the __all__ list in src/models/__init__.py:
FAMILY_MODELS = [
    "GroceryList",
    "GroceryItem", 
    "Reminder",
    "ChildScheduleEntry",
]

# Complete updated __all__ for src/models/__init__.py:
"""
__all__ = [
    "Group",
    "BaseGroup",
    "Message",
    "BaseMessage",
    "Sender",
    "BaseSender",
    "WhatsAppWebhookPayload",
    "upsert",
    "bulk_upsert",
    "KBTopic",
    "KBTopicCreate",
    # Family models
    "GroceryList",
    "GroceryItem",
    "Reminder", 
    "ChildScheduleEntry",
]
"""