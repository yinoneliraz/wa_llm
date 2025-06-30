import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult
from sqlmodel import select, desc, and_, or_
from tenacity import (
    retry,
    wait_random_exponential,
    stop_after_attempt,
    before_sleep_log,
)

from models import Message
from models.family import GroceryList, GroceryItem, Reminder, ChildScheduleEntry
from whatsapp.jid import parse_jid
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class GroceryCommand(BaseModel):
    """Parsed grocery command structure"""
    action: str = Field(description="add, remove, complete, show, or clear")
    items: List[str] = Field(description="list of grocery items")
    quantities: List[str] = Field(description="quantities for each item, if specified")


class ReminderCommand(BaseModel):
    """Parsed reminder command structure"""
    action: str = Field(description="add, show, complete, or delete")
    message: str = Field(description="reminder message or description")
    due_time: Optional[str] = Field(description="when the reminder is due")
    recurring: Optional[str] = Field(description="recurring pattern: daily, weekly, monthly")


class ScheduleCommand(BaseModel):
    """Parsed child schedule command structure"""
    action: str = Field(description="add, show, or log")
    child_name: str = Field(description="name of child: baby, toddler, or actual name")
    activity_type: str = Field(description="feeding, nap, diaper, milestone, etc.")
    notes: Optional[str] = Field(description="additional notes")
    time: Optional[str] = Field(description="time of activity")
    duration: Optional[int] = Field(description="duration in minutes for naps/feeding")


class FamilyHandler(BaseHandler):
    """Handler for family-specific commands: groceries, reminders, child schedules"""

    async def __call__(self, message: Message):
        """Main entry point for family command processing"""
        if not message.text or not message.group:
            return

        # Check if this is a family command
        if await self._is_family_command(message.text):
            try:
                if await self._is_grocery_command(message.text):
                    await self._handle_grocery(message)
                elif await self._is_reminder_command(message.text):
                    await self._handle_reminder(message)
                elif await self._is_schedule_command(message.text):
                    await self._handle_schedule(message)
                else:
                    await self._handle_family_help(message)
            except Exception as e:
                logger.error(f"Error handling family command: {e}")
                await self.send_message(
                    message.chat_jid,
                    "סליחה, הייתה לי בעיה לעבד את הפקודה המשפחתית הזאת. אנא נסה שוב.",
                    message.message_id,
                )

    async def _is_family_command(self, text: str) -> bool:
        """Check if message contains family-related keywords in Hebrew or English"""
        family_keywords = [
            # English keywords
            "grocery", "groceries", "shopping", "list", "buy", "store",
            "remind", "reminder", "remember", "schedule", "due",
            "baby", "toddler", "feeding", "nap", "diaper", "milestone",
            "family", "help family",
            # Hebrew keywords
            "קניות", "רשימה", "רשימת קניות", "קנה", "קניתי", "לקחתי", "חנות", "סופר",
            "תזכורת", "תזכיר", "זכור", "לוח זמנים", "מועד",
            "תינוק", "פעוט", "האכלה", "שינה", "חיתול", "אבן דרך",
            "משפחה", "עזרה משפחתית", "בוט משפחה"
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in family_keywords)

    async def _is_grocery_command(self, text: str) -> bool:
        """Check if message is grocery-related in Hebrew or English"""
        grocery_keywords = [
            # English
            "grocery", "groceries", "shopping", "list", "buy", "store", "got ", "picked up",
            # Hebrew
            "קניות", "רשימה", "רשימת קניות", "קנה", "קניתי", "לקחתי", "חנות", "סופר", 
            "תוסיף", "הוסף", "צריך", "קנייה"
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in grocery_keywords)

    async def _is_reminder_command(self, text: str) -> bool:
        """Check if message is reminder-related in Hebrew or English"""
        reminder_keywords = [
            # English
            "remind", "reminder", "remember", "schedule", "due", "appointment",
            # Hebrew
            "תזכורת", "תזכיר", "זכור", "לוח זמנים", "מועד", "פגישה", "זמן"
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in reminder_keywords)

    async def _is_schedule_command(self, text: str) -> bool:
        """Check if message is child schedule-related in Hebrew or English"""
        schedule_keywords = [
            # English
            "baby", "toddler", "feeding", "nap", "diaper", "milestone", "schedule",
            # Hebrew
            "תינוק", "פעוט", "האכלה", "שינה", "חיתול", "אבן דרך", "לוח זמנים",
            "אכל", "ישן", "התחיל", "סיים"
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in schedule_keywords)

    @retry(
        wait=wait_random_exponential(min=1, max=30),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.DEBUG),
        reraise=True,
    )
    async def _parse_grocery_command(self, text: str) -> AgentRunResult[GroceryCommand]:
        """Parse natural language grocery commands in Hebrew or English"""
        agent = Agent(
            model="anthropic:claude-4-sonnet-20250514",
            system_prompt="""Parse grocery/shopping commands into structured format. Support both Hebrew and English input.
            
            Actions:
            - add: adding items to the grocery list (הוספה לרשימה)
            - complete/got: marking items as completed/purchased (סימון כרכישה)
            - show: showing the current list (הצגת רשימה)
            - clear: clearing completed items (מחיקת פריטים שנרכשו)
            - remove: removing items from list (הסרת פריטים)
            
            Hebrew Examples:
            "תוסיף חלב ולחם לרשימת קניות" -> action: add, items: ["חלב", "לחם"]
            "קניתי את החלב" -> action: complete, items: ["חלב"]
            "תראה רשימת קניות" -> action: show, items: []
            "צריך 2 בקבוקי חלב ו3 תפוחים" -> action: add, items: ["חלב", "תפוחים"], quantities: ["2 בקבוקים", "3"]
            "לקחתי את הלחם" -> action: complete, items: ["לחם"]
            
            English Examples:
            "add milk and bread to grocery list" -> action: add, items: ["milk", "bread"]
            "got the milk" -> action: complete, items: ["milk"]
            "show grocery list" -> action: show, items: []
            "need 2 bottles of milk and 3 apples" -> action: add, items: ["milk", "apples"], quantities: ["2 bottles", "3"]
            """,
            output_type=GroceryCommand,
        )
        return await agent.run(text)

    @retry(
        wait=wait_random_exponential(min=1, max=30),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.DEBUG),
        reraise=True,
    )
    async def _parse_reminder_command(self, text: str) -> AgentRunResult[ReminderCommand]:
        """Parse natural language reminder commands in Hebrew or English"""
        agent = Agent(
            model="anthropic:claude-4-sonnet-20250514",
            system_prompt="""Parse reminder commands into structured format. Support both Hebrew and English input.
            
            Actions:
            - add: creating a new reminder (יצירת תזכורת)
            - show: showing current reminders (הצגת תזכורות)
            - complete: marking reminder as done (סימון כהושלם)
            - delete: removing a reminder (מחיקת תזכורת)
            
            Parse relative times in Hebrew and English:
            Hebrew: "בעוד 30 דקות", "מחר ב3 אחה"צ", "השבוע הבא", "כל יום", "יומי"
            English: "in 30 minutes", "tomorrow at 3pm", "next week", "daily", "every day"
            
            Hebrew Examples:
            "תזכיר לי להתקשר לרופא מחר ב3 אחה"צ" -> action: add, message: "התקשר לרופא", due_time: "מחר 3 אחה"צ"
            "תזכיר לי לקחת ויטמינים כל יום" -> action: add, message: "קחת ויטמינים", recurring: "יומי"
            "תראה את התזכורות שלי" -> action: show
            
            English Examples:
            "remind me to call doctor at 3pm tomorrow" -> action: add, message: "call doctor", due_time: "tomorrow 3pm"
            "remind me to take vitamins daily" -> action: add, message: "take vitamins", recurring: "daily"
            "show my reminders" -> action: show
            """,
            output_type=ReminderCommand,
        )
        return await agent.run(text)

    @retry(
        wait=wait_random_exponential(min=1, max=30),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.DEBUG),
        reraise=True,
    )
    async def _parse_schedule_command(self, text: str) -> AgentRunResult[ScheduleCommand]:
        """Parse natural language child schedule commands in Hebrew or English"""
        agent = Agent(
            model="anthropic:claude-4-sonnet-20250514",
            system_prompt="""Parse child schedule commands into structured format. Support both Hebrew and English input.
            
            Actions:
            - add/log: logging an activity (רישום פעילות)
            - show: showing recent activities (הצגת פעילויות)
            
            Child names in Hebrew: תינוק, פעוט, בן/בת, or actual names
            Child names in English: baby, toddler, or actual names
            
            Activity types in Hebrew: האכלה, שינה, חיתול, אבן דרך, משחק, אמבטיה
            Activity types in English: feeding, nap, diaper, milestone, play, bath
            
            Hebrew Examples:
            "התינוק אכל ב2 אחה"צ" -> action: log, child_name: "תינוק", activity_type: "האכלה", time: "2 אחה"צ"
            "הפעוט התחיל לישון" -> action: log, child_name: "פעוט", activity_type: "שינה"
            "תראה את הלוח זמנים של התינוק" -> action: show, child_name: "תינוק"
            "התינוק עשה את הצעדים הראשונים!" -> action: log, child_name: "תינוק", activity_type: "אבן דרך", notes: "צעדים ראשונים"
            
            English Examples:
            "baby fed at 2pm" -> action: log, child_name: "baby", activity_type: "feeding", time: "2pm"
            "toddler nap started" -> action: log, child_name: "toddler", activity_type: "nap"
            "show baby's schedule" -> action: show, child_name: "baby"
            "baby had first steps!" -> action: log, child_name: "baby", activity_type: "milestone", notes: "first steps"
            """,
            output_type=ScheduleCommand,
        )
        return await agent.run(text)

    async def _handle_grocery(self, message: Message):
        """Handle grocery list commands"""
        try:
            parsed = await self._parse_grocery_command(message.text)
            command = parsed.data

            if command.action == "add":
                await self._add_grocery_items(message, command.items, command.quantities)
            elif command.action in ["complete", "got"]:
                await self._complete_grocery_items(message, command.items)
            elif command.action == "show":
                await self._show_grocery_list(message)
            elif command.action == "clear":
                await self._clear_completed_items(message)
            elif command.action == "remove":
                await self._remove_grocery_items(message, command.items)

        except Exception as e:
            logger.error(f"Error handling grocery command: {e}")
            await self.send_message(
                message.chat_jid,
                "לא הצלחתי להבין את הפקודה הזאת. נסה 'תוסיף חלב לרשימה' או 'קניתי לחם'",
                message.message_id,
            )

    async def _handle_reminder(self, message: Message):
        """Handle reminder commands"""
        try:
            parsed = await self._parse_reminder_command(message.text)
            command = parsed.data

            if command.action == "add":
                await self._add_reminder(message, command)
            elif command.action == "show":
                await self._show_reminders(message)
            elif command.action == "complete":
                await self._complete_reminder(message, command.message)
            elif command.action == "delete":
                await self._delete_reminder(message, command.message)

        except Exception as e:
            logger.error(f"Error handling reminder command: {e}")
            await self.send_message(
                message.chat_jid,
                "לא הצלחתי להבין את התזכורת הזאת. נסה 'תזכיר לי להתקשר לרופא מחר ב3 אחה\"צ'",
                message.message_id,
            )

    async def _handle_schedule(self, message: Message):
        """Handle child schedule commands"""
        try:
            parsed = await self._parse_schedule_command(message.text)
            command = parsed.data

            if command.action in ["add", "log"]:
                await self._log_schedule_entry(message, command)
            elif command.action == "show":
                await self._show_schedule(message, command.child_name)

        except Exception as e:
            logger.error(f"Error handling schedule command: {e}")
            await self.send_message(
                message.chat_jid,
                "לא הצלחתי להבין את הרישום הזה. נסה 'התינוק אכל ב2 אחה\"צ' או 'תראה לוח זמנים של הפעוט'",
                message.message_id,
            )

    # Grocery List Methods
    async def _get_or_create_grocery_list(self, group_jid: str) -> GroceryList:
        """Get or create the main grocery list for a group"""
        stmt = select(GroceryList).where(GroceryList.group_jid == group_jid)
        result = await self.session.exec(stmt)
        grocery_list = result.first()

        if not grocery_list:
            grocery_list = GroceryList(group_jid=group_jid)
            self.session.add(grocery_list)
            await self.session.flush()

        return grocery_list

    async def _add_grocery_items(self, message: Message, items: List[str], quantities: List[str]):
        """Add items to grocery list"""
        grocery_list = await self._get_or_create_grocery_list(message.group_jid)
        
        added_items = []
        for i, item in enumerate(items):
            quantity = quantities[i] if i < len(quantities) else None
            
            # Check if item already exists
            stmt = select(GroceryItem).where(
                and_(
                    GroceryItem.list_id == grocery_list.id,
                    GroceryItem.item_name.ilike(f"%{item}%"),
                    GroceryItem.completed == False
                )
            )
            result = await self.session.exec(stmt)
            existing_item = result.first()

            if existing_item:
                continue  # Skip if already exists

            new_item = GroceryItem(
                list_id=grocery_list.id,
                item_name=item,
                quantity=quantity,
                added_by=message.sender_jid,
            )
            self.session.add(new_item)
            added_items.append(f"{quantity + ' ' if quantity else ''}{item}")

        await self.session.commit()

        if added_items:
            response = f"✅ נוסף לרשימת הקניות:\n" + "\n".join(f"• {item}" for item in added_items)
        else:
            response = "הפריטים האלה כבר ברשימה!"

        await self.send_message(message.chat_jid, response, message.message_id)

    async def _complete_grocery_items(self, message: Message, items: List[str]):
        """Mark grocery items as completed"""
        completed_items = []
        
        for item in items:
            stmt = select(GroceryItem).join(GroceryList).where(
                and_(
                    GroceryList.group_jid == message.group_jid,
                    GroceryItem.item_name.ilike(f"%{item}%"),
                    GroceryItem.completed == False
                )
            )
            result = await self.session.exec(stmt)
            grocery_item = result.first()

            if grocery_item:
                grocery_item.completed = True
                grocery_item.completed_by = message.sender_jid
                grocery_item.completed_at = datetime.now(timezone.utc)
                completed_items.append(grocery_item.item_name)

        await self.session.commit()

        if completed_items:
            response = f"✅ סומן כנרכש:\n" + "\n".join(f"• {item}" for item in completed_items)
        else:
            response = "לא מצאתי את הפריטים האלה ברשימת הקניות."

        await self.send_message(message.chat_jid, response, message.message_id)

    async def _show_grocery_list(self, message: Message):
        """Show current grocery list"""
        stmt = (
            select(GroceryItem)
            .join(GroceryList)
            .where(
                and_(
                    GroceryList.group_jid == message.group_jid,
                    GroceryItem.completed == False
                )
            )
            .order_by(GroceryItem.created_at)
        )
        result = await self.session.exec(stmt)
        items = result.all()

        if not items:
            response = "🛒 רשימת הקניות שלכם ריקה!"
        else:
            response = "🛒 **רשימת קניות:**\n"
            for item in items:
                quantity_str = f"{item.quantity} " if item.quantity else ""
                response += f"• {quantity_str}{item.item_name}\n"

        await self.send_message(message.chat_jid, response, message.message_id)

    # Helper Methods
    async def _handle_family_help(self, message: Message):
        """Show family bot help in Hebrew"""
        help_text = """
👨‍👩‍👧‍👦 **עזרה בוט משפחתי**

**רשימות קניות:**
• "תוסיף חלב ולחם לרשימה"
• "קניתי את החלב" או "לקחתי לחם"
• "תראה רשימת קניות"

**תזכורות:**
• "תזכיר לי להתקשר לרופא מחר ב3 אחה״צ"
• "תזכיר לי לקחת ויטמינים כל יום"
• "תראה את התזכורות שלי"

**לוח זמנים ילדים:**
• "התינוק אכל ב2 אחה״צ"
• "הפעוט התחיל לישון"
• "תראה לוח זמנים של התינוק"
• "התינוק עשה את הצעדים הראשונים!" (אבני דרך)

פשוט דבר בטבעיות - אני אבין! 😊
        """
        await self.send_message(message.chat_jid, help_text, message.message_id)

    # Placeholder methods for reminder and schedule functionality
    async def _add_reminder(self, message: Message, command: ReminderCommand):
        # TODO: Implement reminder creation with time parsing
        await self.send_message(
            message.chat_jid,
            "פונקציונליות תזכורות בקרוב! 🔔",
            message.message_id,
        )

    async def _show_reminders(self, message: Message):
        # TODO: Implement reminder display
        await self.send_message(
            message.chat_jid,
            "הצגת תזכורות בקרוב! 📅",
            message.message_id,
        )

    async def _complete_reminder(self, message: Message, reminder_text: str):
        # TODO: Implement reminder completion
        pass

    async def _delete_reminder(self, message: Message, reminder_text: str):
        # TODO: Implement reminder deletion
        pass

    async def _log_schedule_entry(self, message: Message, command: ScheduleCommand):
        # TODO: Implement schedule logging
        await self.send_message(
            message.chat_jid,
            "רישום לוח זמנים בקרוב! 👶",
            message.message_id,
        )

    async def _show_schedule(self, message: Message, child_name: str):
        # TODO: Implement schedule display
        await self.send_message(
            message.chat_jid,
            f"לוח זמנים עבור {child_name} בקרוב! 📊",
            message.message_id,
        )