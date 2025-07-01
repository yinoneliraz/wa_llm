import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
import pytz

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

# User timezone (Jerusalem, Israel)
USER_TIMEZONE = pytz.timezone('Asia/Jerusalem')


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

    def _get_user_now(self) -> datetime:
        """Get current time in user's timezone (Jerusalem)"""
        utc_now = datetime.now(timezone.utc)
        user_now = utc_now.astimezone(USER_TIMEZONE)
        logger.info(f"User current time (Jerusalem): {user_now.strftime('%d/%m/%Y %H:%M:%S %Z')}")
        return user_now

    def _to_utc(self, user_time: datetime) -> datetime:
        """Convert user timezone datetime to UTC for database storage"""
        if user_time.tzinfo is None:
            # Assume it's in user timezone if no timezone info
            user_time = USER_TIMEZONE.localize(user_time)
        return user_time.astimezone(timezone.utc)

    def _to_user_timezone(self, utc_time: datetime) -> datetime:
        """Convert UTC datetime to user timezone for display"""
        if utc_time.tzinfo is None:
            utc_time = timezone.utc.localize(utc_time)
        return utc_time.astimezone(USER_TIMEZONE)

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
            "grocery", "groceries", "shopping", "list", "buy", "store", "got ", "picked up", "remove",
            # Hebrew
            "קניות", "רשימה", "רשימת קניות", "קנה", "קניתי", "לקחתי", "חנות", "סופר", 
            "תוסיף", "הוסף", "צריך", "קנייה", "רכשתי", "הבאתי",
            # Hebrew removal words
            "תוריד", "תסיר", "תמחק", "תוציא", "הוצא", "הסר", "הורד"
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in grocery_keywords)

    async def _is_reminder_command(self, text: str) -> bool:
        """Check if message is reminder-related in Hebrew or English"""
        reminder_keywords = [
            # English
            "remind", "reminder", "remember", "schedule", "due", "appointment", "show",
            # Hebrew - creating reminders
            "תזכורת", "תזכיר", "זכור", "לוח זמנים", "מועד", "פגישה", "זמן",
            # Hebrew - showing/viewing reminders
            "תראה", "הצג", "הראה", "הצגת", "רשימת תזכורות", "התזכורות שלי",
            # Hebrew - managing reminders  
            "סיימתי", "עשיתי", "השלמתי", "מחק תזכורת", "תמחק", "הסר תזכורת",
            "תנקה תזכורות", "נקה תזכורות", "מחק תזכורות"
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
            - complete: marking items as completed/purchased (סימון כרכישה)
            - remove: explicitly removing items from list (הסרת פריטים)
            - show: showing the current list (הצגת רשימה)
            - clear: clearing completed items (מחיקת פריטים שנרכשו)
            
            Hebrew Examples for COMPLETE action (marking as purchased):
            "קניתי את החלב" -> action: complete, items: ["חלב"]
            "קניתי לחם" -> action: complete, items: ["לחם"]
            "לקחתי את התפוחים" -> action: complete, items: ["תפוחים"]
            "רכשתי חלב ולחם" -> action: complete, items: ["חלב", "לחם"]
            "הבאתי את החלב" -> action: complete, items: ["חלב"]
            
            Hebrew Examples for REMOVE action (removing from list):
            "תוריד את הלחם מרשימת הקניות" -> action: remove, items: ["לחם"]
            "תסיר את החלב מהרשימה" -> action: remove, items: ["חלב"]
            "תמחק את התפוחים" -> action: remove, items: ["תפוחים"]
            "תוציא את הלחם מהרשימה" -> action: remove, items: ["לחם"]
            
            Hebrew Examples for ADD action:
            "תוסיף חלב ולחם לרשימה" -> action: add, items: ["חלב", "לחם"]
            "צריך 2 בקבוקי חלב ו3 תפוחים" -> action: add, items: ["חלב", "תפוחים"], quantities: ["2 בקבוקים", "3"]
            
            Hebrew Examples for SHOW action:
            "תראה רשימת קניות" -> action: show, items: []
            "מה ברשימה" -> action: show, items: []
            
            English Examples:
            "got the milk" -> action: complete, items: ["milk"]
            "bought bread" -> action: complete, items: ["bread"]
            "remove milk from list" -> action: remove, items: ["milk"]
            "add milk and bread to grocery list" -> action: add, items: ["milk", "bread"]
            "show grocery list" -> action: show, items: []
            
            IMPORTANT: 
            - "קניתי" = complete (purchased)
            - "לקחתי" = complete (took/got)
            - "רכשתי" = complete (acquired)
            - "תוריד/תסיר/תמחק/תוציא" = remove (explicit removal)
            - Extract the actual item names without "את ה" prefixes
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
            - clear: clearing completed reminders (ניקוי תזכורות מושלמות)
            
            Parse relative times in Hebrew and English:
            Hebrew: "בעוד 30 דקות", "בעוד שתי דקות", "מחר ב3 אחה״צ", "השבוע הבא", "כל יום", "יומי"
            English: "in 30 minutes", "in two minutes", "tomorrow at 3pm", "next week", "daily", "every day"
            
            Hebrew Examples for ADD:
            "תזכיר לי להתקשר לרופא ב5 אחה״צ" -> action: add, message: "התקשר לרופא", due_time: "ב5 אחה״צ"
            "תזכיר לי לקחת ויטמינים כל יום" -> action: add, message: "קחת ויטמינים", recurring: "יומי"
            "תזכיר לי לקנות חלב בעוד שתי דקות" -> action: add, message: "קנות חלב", due_time: "בעוד שתי דקות"
            "תזכיר לי לקרוא לאמא מחר בבוקר" -> action: add, message: "קרוא לאמא", due_time: "מחר בבוקר"
            
            Hebrew Examples for SHOW:
            "תראה את התזכורות שלי" -> action: show
            "מה התזכורות שלי" -> action: show
            "הצג תזכורות" -> action: show
            
            Hebrew Examples for COMPLETE:
            "סיימתי להתקשר לרופא" -> action: complete, message: "התקשר לרופא"
            "עשיתי קניות" -> action: complete, message: "קניות"
            "השלמתי לקחת ויטמינים" -> action: complete, message: "לקחת ויטמינים"
            
            Hebrew Examples for DELETE:
            "מחק תזכורת להתקשר לרופא" -> action: delete, message: "התקשר לרופא"
            "תמחק את התזכורת לקניות" -> action: delete, message: "קניות"
            "הסר תזכורת לויטמינים" -> action: delete, message: "ויטמינים"
            
            Hebrew Examples for CLEAR:
            "תנקה תזכורות שהושלמו" -> action: clear
            "מחק תזכורות מושלמות" -> action: clear
            "נקה תזכורות ישנות" -> action: clear
            
            English Examples:
            "remind me to call doctor at 5pm" -> action: add, message: "call doctor", due_time: "5pm"
            "remind me to take vitamins daily" -> action: add, message: "take vitamins", recurring: "daily"
            "show my reminders" -> action: show
            "completed calling doctor" -> action: complete, message: "calling doctor"
            "delete reminder about groceries" -> action: delete, message: "groceries"
            "clear completed reminders" -> action: clear
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
            logger.info(f"Processing grocery command: '{message.text}'")
            parsed = await self._parse_grocery_command(message.text)
            command = parsed.data
            
            logger.info(f"Parsed command - Action: {command.action}, Items: {command.items}, Quantities: {command.quantities}")

            if command.action == "add":
                await self._add_grocery_items(message, command.items, command.quantities)
            elif command.action in ["complete", "got"]:
                await self._complete_grocery_items(message, command.items)
            elif command.action == "remove":
                await self._remove_grocery_items(message, command.items)
            elif command.action == "show":
                await self._show_grocery_list(message)
            elif command.action == "clear":
                await self._clear_completed_items(message)

        except Exception as e:
            logger.error(f"Error handling grocery command: {e}")
            await self.send_message(
                message.chat_jid,
                "לא הצלחתי להבין את הפקודה הזאת. נסה:\n• 'תוסיף חלב לרשימה' - להוספה\n• 'קניתי לחם' - לסימון כרכישה\n• 'תוריד את החלב מרשימת הקניות' - להסרה\n• 'תראה רשימת קניות' - להצגה",
                message.message_id,
            )

    async def _handle_reminder(self, message: Message):
        """Handle reminder commands"""
        try:
            logger.info(f"Processing reminder command: '{message.text}'")
            parsed = await self._parse_reminder_command(message.text)
            command = parsed.data
            
            logger.info(f"Parsed reminder command - Action: {command.action}, Message: {command.message}, Due time: {command.due_time}, Recurring: {command.recurring}")

            if command.action == "add":
                await self._add_reminder(message, command)
            elif command.action == "show":
                await self._show_reminders(message)
            elif command.action == "complete":
                await self._complete_reminder(message, command.message)
            elif command.action == "delete":
                await self._delete_reminder(message, command.message)
            elif command.action == "clear":
                await self._clear_completed_reminders(message)

        except Exception as e:
            logger.error(f"Error handling reminder command: {e}")
            await self.send_message(
                message.chat_jid,
                "לא הצלחתי להבין את פקודת התזכורת. נסה:\n• 'תזכיר לי לעשות משהו ב5 אחה״צ' - ליצירה\n• 'תראה את התזכורות שלי' - להצגה\n• 'סיימתי [משימה]' - לסימון כהושלם\n• 'מחק תזכורת [משימה]' - למחיקה",
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
            
            # Clean the item name
            clean_item = item.strip()
            for prefix in ["את ה", "את", "ה"]:
                if clean_item.startswith(prefix):
                    clean_item = clean_item[len(prefix):].strip()
            
            logger.info(f"Adding item: '{item}' -> cleaned: '{clean_item}' with quantity: {quantity}")
            
            # Check if item already exists
            stmt = select(GroceryItem).where(
                and_(
                    GroceryItem.list_id == grocery_list.id,
                    or_(
                        GroceryItem.item_name.ilike(f"%{clean_item}%"),
                        GroceryItem.item_name == clean_item,
                        GroceryItem.item_name == item
                    ),
                    GroceryItem.completed == False
                )
            )
            result = await self.session.exec(stmt)
            existing_item = result.first()

            if existing_item:
                logger.info(f"Item '{clean_item}' already exists in list")
                continue  # Skip if already exists

            # Use the cleaned item name for storage
            final_item_name = clean_item if clean_item else item
            new_item = GroceryItem(
                list_id=grocery_list.id,
                item_name=final_item_name,
                quantity=quantity,
                added_by=message.sender_jid,
            )
            self.session.add(new_item)
            added_items.append(f"{quantity + ' ' if quantity else ''}{final_item_name}")
            logger.info(f"Added new item: {final_item_name}")

        await self.session.commit()

        if added_items:
            response = f"✅ נוסף לרשימת הקניות:\n" + "\n".join(f"• {item}" for item in added_items)
        else:
            response = "הפריטים האלה כבר ברשימה!"

        await self.send_message(message.chat_jid, response, message.message_id)

    async def _remove_grocery_items(self, message: Message, items: List[str]):
        """Remove items from grocery list (not mark as completed, but delete entirely)"""
        removed_items = []
        
        for item in items:
            # Clean the item name - remove common Hebrew prefixes
            clean_item = item.strip()
            for prefix in ["את ה", "את", "ה"]:
                if clean_item.startswith(prefix):
                    clean_item = clean_item[len(prefix):].strip()
            
            logger.info(f"Looking for item to remove: '{item}' -> cleaned: '{clean_item}'")
            
            # Try multiple matching strategies
            stmt = select(GroceryItem).join(GroceryList).where(
                and_(
                    GroceryList.group_jid == message.group_jid,
                    GroceryItem.completed == False,  # Only remove non-completed items
                    or_(
                        GroceryItem.item_name.ilike(f"%{clean_item}%"),
                        GroceryItem.item_name.ilike(f"%{item}%"),
                        GroceryItem.item_name == clean_item,
                        GroceryItem.item_name == item
                    )
                )
            ).limit(1)  # Only get the first match
            
            result = await self.session.exec(stmt)
            grocery_item = result.first()

            if grocery_item:
                logger.info(f"Found item to remove: {grocery_item.item_name}")
                removed_items.append(grocery_item.item_name)
                await self.session.delete(grocery_item)
            else:
                logger.warning(f"Could not find item '{item}' (cleaned: '{clean_item}') to remove")

        await self.session.commit()

        if removed_items:
            response = f"🗑️ הוסר מהרשימה:\n" + "\n".join(f"• {item}" for item in removed_items)
        else:
            response = "לא מצאתי את הפריטים האלה ברשימת הקניות."

        await self.send_message(message.chat_jid, response, message.message_id)

    async def _clear_completed_items(self, message: Message):
        """Clear all completed items from the grocery list"""
        stmt = select(GroceryItem).join(GroceryList).where(
            and_(
                GroceryList.group_jid == message.group_jid,
                GroceryItem.completed == True
            )
        )
        result = await self.session.exec(stmt)
        completed_items = result.all()

        if completed_items:
            for item in completed_items:
                await self.session.delete(item)
            
            await self.session.commit()
            response = f"🧹 נוקו {len(completed_items)} פריטים שנרכשו מהרשימה"
        else:
            response = "אין פריטים שנרכשו לניקוי"

        await self.send_message(message.chat_jid, response, message.message_id)

    async def _complete_grocery_items(self, message: Message, items: List[str]):
        """Mark grocery items as completed"""
        completed_items = []
        
        for item in items:
            # Clean the item name - remove common Hebrew prefixes
            clean_item = item.strip()
            for prefix in ["את ה", "את", "ה"]:
                if clean_item.startswith(prefix):
                    clean_item = clean_item[len(prefix):].strip()
            
            logger.info(f"Looking for item to complete: '{item}' -> cleaned: '{clean_item}'")
            
            # Try multiple matching strategies
            stmt = select(GroceryItem).join(GroceryList).where(
                and_(
                    GroceryList.group_jid == message.group_jid,
                    GroceryItem.completed == False,
                    or_(
                        GroceryItem.item_name.ilike(f"%{clean_item}%"),
                        GroceryItem.item_name.ilike(f"%{item}%"),
                        GroceryItem.item_name == clean_item,
                        GroceryItem.item_name == item
                    )
                )
            ).limit(1)  # Only get the first match
            
            result = await self.session.exec(stmt)
            grocery_item = result.first()

            if grocery_item:
                logger.info(f"Found item to complete: {grocery_item.item_name}")
                grocery_item.completed = True
                grocery_item.completed_by = message.sender_jid
                # Store completion time in UTC but it represents user's action time
                grocery_item.completed_at = self._to_utc(self._get_user_now())
                completed_items.append(grocery_item.item_name)
            else:
                logger.warning(f"Could not find item '{item}' (cleaned: '{clean_item}') to complete")

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
• "תוסיף חלב ולחם לרשימה" - הוספת פריטים
• "קניתי את החלב" או "לקחתי לחם" - סימון כרכישה
• "תוריד את החלב מרשימת הקניות" - הסרת פריטים
• "תראה רשימת קניות" - הצגת הרשימה
• "תנקה פריטים שנרכשו" - ניקוי פריטים מושלמים

**תזכורות:**
• "תזכיר לי להתקשר לרופא ב5 אחה״צ" - יצירת תזכורת
• "תזכיר לי לקנות חלב בעוד שתי דקות" - תזכורת מיידית
• "תזכיר לי לקחת ויטמינים כל יום" - תזכורת חוזרת
• "תראה את התזכורות שלי" - הצגת תזכורות
• "סיימתי להתקשר לרופא" - סימון כהושלם
• "מחק תזכורת לקניות" - מחיקת תזכורת
• "תנקה תזכורות שהושלמו" - ניקוי תזכורות ישנות

**לוח זמנים ילדים:**
• "התינוק אכל ב2 אחה״צ"
• "הפעוט התחיל לישון"
• "תראה לוח זמנים של התינוק"
• "התינוק עשה את הצעדים הראשונים!" (אבני דרך)

**זמנים נתמכים בתזכורות:**
• "ב5 אחה״צ", "מחר ב9 בבוקר"
• "בעוד שתי דקות", "בעוד שעה"
• "בערב", "בלילה", "מחרתיים"

פשוט דבר בטבעיות - אני אבין! 😊
        """
        await self.send_message(message.chat_jid, help_text, message.message_id)

    # Reminder functionality - now implemented with timezone support!
    async def _add_reminder(self, message: Message, command: ReminderCommand):
        """Create a new reminder with time parsing and timezone support"""
        try:
            # Parse the due time (returns UTC for database storage)
            due_time_utc = await self._parse_hebrew_time(command.due_time, command.recurring)
            
            if not due_time_utc:
                await self.send_message(
                    message.chat_jid,
                    "לא הצלחתי להבין את הזמן. נסה: 'ב5 אחה״צ', 'מחר ב9 בבוקר', או 'בעוד שתיים דקות'",
                    message.message_id,
                )
                return
            
            # Create reminder (stored in UTC)
            reminder = Reminder(
                group_jid=message.group_jid,
                created_by=message.sender_jid,
                message=command.message,
                due_time=due_time_utc,
                recurring_pattern=command.recurring,
                recurring_interval=1 if command.recurring else None,
            )
            
            self.session.add(reminder)
            await self.session.commit()
            
            # Convert to user timezone for display
            due_time_user = self._to_user_timezone(due_time_utc)
            time_str = due_time_user.strftime("%d/%m/%Y %H:%M")
            recurring_str = f" (חוזר {command.recurring})" if command.recurring else ""
            
            # Calculate time until reminder for user feedback
            now_user = self._get_user_now()
            time_diff = due_time_user - now_user
            if time_diff.total_seconds() < 3600:  # Less than 1 hour
                until_str = f" - בעוד {int(time_diff.total_seconds() / 60)} דקות"
            elif time_diff.total_seconds() < 86400:  # Less than 1 day
                until_str = f" - בעוד {int(time_diff.total_seconds() / 3600)} שעות"
            else:
                until_str = f" - בעוד {time_diff.days} ימים"
            
            response = f"✅ תזכורת נוצרה:\n📝 {command.message}\n⏰ {time_str}{until_str}{recurring_str}"
            await self.send_message(message.chat_jid, response, message.message_id)
            
        except Exception as e:
            logger.error(f"Error creating reminder: {e}")
            await self.send_message(
                message.chat_jid,
                "הייתה בעיה ביצירת התזכורת. אנא נסה שוב.",
                message.message_id,
            )

    async def _show_reminders(self, message: Message):
        """Show current active reminders with improved formatting and timezone support"""
        # Use user's current time for calculations
        now_user = self._get_user_now()
        now_utc = self._to_utc(now_user)
        
        # Get active (upcoming) reminders
        stmt_active = select(Reminder).where(
            and_(
                Reminder.group_jid == message.group_jid,
                Reminder.completed == False,
                Reminder.due_time > now_utc  # Compare with UTC in database
            )
        ).order_by(Reminder.due_time)
        
        # Get overdue reminders
        stmt_overdue = select(Reminder).where(
            and_(
                Reminder.group_jid == message.group_jid,
                Reminder.completed == False,
                Reminder.due_time <= now_utc,  # Compare with UTC in database
                Reminder.sent == False  # Not sent yet
            )
        ).order_by(Reminder.due_time)
        
        result_active = await self.session.exec(stmt_active)
        result_overdue = await self.session.exec(stmt_overdue)
        
        active_reminders = result_active.all()
        overdue_reminders = result_overdue.all()
        
        if not active_reminders and not overdue_reminders:
            response = "📅 אין תזכורות פעילות"
        else:
            response = "📅 **התזכורות שלך:**\n\n"
            
            # Show overdue reminders first
            if overdue_reminders:
                response += "🔴 **תזכורות שפג תוקפן:**\n"
                for i, reminder in enumerate(overdue_reminders, 1):
                    # Convert UTC from database to user timezone for display
                    due_time_user = self._to_user_timezone(reminder.due_time)
                    time_str = due_time_user.strftime("%d/%m %H:%M")
                    
                    time_diff = now_user - due_time_user
                    if time_diff.total_seconds() < 3600:  # Less than 1 hour
                        overdue_str = f"לפני {int(time_diff.total_seconds() / 60)} דקות"
                    elif time_diff.total_seconds() < 86400:  # Less than 1 day
                        overdue_str = f"לפני {int(time_diff.total_seconds() / 3600)} שעות"
                    else:
                        overdue_str = f"לפני {time_diff.days} ימים"
                    
                    recurring_str = f" (חוזר {reminder.recurring_pattern})" if reminder.recurring_pattern else ""
                    response += f"{i}. {reminder.message}\n   ⏰ {time_str} ({overdue_str}){recurring_str}\n\n"
            
            # Show upcoming reminders
            if active_reminders:
                response += "🟢 **תזכורות עתידיות:**\n"
                for i, reminder in enumerate(active_reminders, 1):
                    # Convert UTC from database to user timezone for display
                    due_time_user = self._to_user_timezone(reminder.due_time)
                    time_str = due_time_user.strftime("%d/%m %H:%M")
                    
                    # Calculate time until reminder
                    time_diff = due_time_user - now_user
                    if time_diff.total_seconds() < 3600:  # Less than 1 hour
                        until_str = f"בעוד {int(time_diff.total_seconds() / 60)} דקות"
                    elif time_diff.total_seconds() < 86400:  # Less than 1 day
                        until_str = f"בעוד {int(time_diff.total_seconds() / 3600)} שעות"
                    else:
                        until_str = f"בעוד {time_diff.days} ימים"
                    
                    recurring_str = f" (חוזר {reminder.recurring_pattern})" if reminder.recurring_pattern else ""
                    response += f"{i}. {reminder.message}\n   ⏰ {time_str} ({until_str}){recurring_str}\n\n"
            
            # Add management instructions
            response += "💡 **ניהול תזכורות:**\n"
            response += "• 'סיימתי [תיאור התזכורת]' - לסימון כהושלם\n"
            response += "• 'מחק תזכורת [תיאור]' - למחיקת תזכורת\n"
            response += "• 'תנקה תזכורות שהושלמו' - לניקוי כל התזכורות שהושלמו"
        
        await self.send_message(message.chat_jid, response, message.message_id)

    async def _clear_completed_reminders(self, message: Message):
        """Clear all completed reminders"""
        stmt = select(Reminder).where(
            and_(
                Reminder.group_jid == message.group_jid,
                Reminder.completed == True
            )
        )
        result = await self.session.exec(stmt)
        completed_reminders = result.all()

        if completed_reminders:
            for reminder in completed_reminders:
                await self.session.delete(reminder)
            
            await self.session.commit()
            response = f"🧹 נוקו {len(completed_reminders)} תזכורות שהושלמו"
        else:
            response = "אין תזכורות מושלמות לניקוי"

        await self.send_message(message.chat_jid, response, message.message_id)

    async def _complete_reminder(self, message: Message, reminder_text: str):
        """Mark a reminder as completed"""
        stmt = select(Reminder).where(
            and_(
                Reminder.group_jid == message.group_jid,
                Reminder.completed == False,
                Reminder.message.ilike(f"%{reminder_text}%")
            )
        ).limit(1)
        
        result = await self.session.exec(stmt)
        reminder = result.first()
        
        if reminder:
            reminder.completed = True
            # Store completion time in UTC but show user time in response
            reminder.completed_at = self._to_utc(self._get_user_now())
            await self.session.commit()
            
            response = f"✅ התזכורת הושלמה: {reminder.message}"
        else:
            response = "לא מצאתי תזכורת כזאת"
        
        await self.send_message(message.chat_jid, response, message.message_id)

    async def _delete_reminder(self, message: Message, reminder_text: str):
        """Delete a reminder"""
        stmt = select(Reminder).where(
            and_(
                Reminder.group_jid == message.group_jid,
                Reminder.completed == False,
                Reminder.message.ilike(f"%{reminder_text}%")
            )
        ).limit(1)
        
        result = await self.session.exec(stmt)
        reminder = result.first()
        
        if reminder:
            await self.session.delete(reminder)
            await self.session.commit()
            
            response = f"🗑️ התזכורת נמחקה: {reminder.message}"
        else:
            response = "לא מצאתי תזכורת כזאת למחיקה"
        
        await self.send_message(message.chat_jid, response, message.message_id)

    async def _parse_hebrew_time(self, time_str: str, recurring: str = None) -> datetime:
        """Parse Hebrew time expressions into datetime objects using user's timezone"""
        if not time_str:
            return None
        
        # Use user's current time instead of UTC
        now = self._get_user_now()
        text = time_str.lower().strip()
        
        logger.info(f"Parsing Hebrew time: '{time_str}' -> '{text}' (User time: {now.strftime('%H:%M %Z')})")
        
        # Handle relative times - these should return immediately
        if "בעוד" in text:
            logger.info(f"Processing relative time: {text}")
            # "בעוד שעה", "בעוד 30 דקות", "בעוד יומיים"
            if "דקות" in text or "דקה" in text:
                minutes = self._extract_number(text)
                logger.info(f"Extracted minutes: {minutes}")
                result_time = now + timedelta(minutes=minutes or 30)
                logger.info(f"Relative time result (user timezone): {result_time.strftime('%d/%m/%Y %H:%M:%S %Z')}")
                # Convert to UTC for database storage
                return self._to_utc(result_time)
            elif "שעות" in text or "שעה" in text:
                hours = self._extract_number(text)
                logger.info(f"Extracted hours: {hours}")
                # Handle fractional hours (like חצי שעה = 0.5 hours = 30 minutes)
                if hours and hours < 1:
                    # Convert fractional hours to minutes
                    result_time = now + timedelta(minutes=hours * 60)
                else:
                    result_time = now + timedelta(hours=hours or 1)
                logger.info(f"Relative time result (user timezone): {result_time.strftime('%d/%m/%Y %H:%M:%S %Z')}")
                return self._to_utc(result_time)
            elif "ימים" in text or "יום" in text:
                days = self._extract_number(text)
                logger.info(f"Extracted days: {days}")
                result_time = now + timedelta(days=days or 1)
                logger.info(f"Relative time result (user timezone): {result_time.strftime('%d/%m/%Y %H:%M:%S %Z')}")
                return self._to_utc(result_time)
            else:
                # General "בעוד" without specific unit - default to 1 hour
                logger.info("General 'בעוד' - defaulting to 1 hour")
                result_time = now + timedelta(hours=1)
                return self._to_utc(result_time)
        
        # Handle specific times (only if not relative)
        target_time = now
        
        # Handle day references
        if "מחר" in text:
            target_time = now + timedelta(days=1)
        elif "מחרתיים" in text:
            target_time = now + timedelta(days=2)
        elif "השבוע הבא" in text:
            target_time = now + timedelta(days=7)
        
        # Extract hour from Hebrew time
        hour = None
        minute = 0
        
        # Look for patterns like "ב5 אחה״צ", "ב9 בבוקר", "ב15:30"
        if "אחה״צ" in text or "אחהצ" in text:
            # Afternoon - add 12 to hour if needed
            hour = self._extract_number(text)
            if hour and hour < 12:
                hour += 12
        elif "בבוקר" in text:
            # Morning
            hour = self._extract_number(text)
        elif "בערב" in text:
            # Evening - assume PM
            hour = self._extract_number(text)
            if hour and hour < 12:
                hour += 12
        elif "בלילה" in text:
            # Night
            hour = self._extract_number(text)
            if hour and hour < 6:  # 0-5 AM is night, 6-11 is morning
                target_time = target_time + timedelta(days=1)
        else:
            # Try to extract just the hour
            hour = self._extract_number(text)
        
        # Look for minute specification (like 15:30)
        if ":" in text:
            time_parts = text.split(":")
            if len(time_parts) >= 2:
                try:
                    hour = int(time_parts[0][-2:])  # Last 2 digits before :
                    minute = int(time_parts[1][:2])  # First 2 digits after :
                except ValueError:
                    pass
        
        # Set the time
        if hour is not None:
            try:
                target_time = target_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # If the time is in the past today, move to tomorrow
                if target_time <= now and "מחר" not in text:
                    target_time = target_time + timedelta(days=1)
                
                logger.info(f"Parsed time (user timezone): {target_time.strftime('%d/%m/%Y %H:%M:%S %Z')}")
                # Convert to UTC for database storage
                return self._to_utc(target_time)
            except ValueError as e:
                logger.error(f"Invalid time values: hour={hour}, minute={minute}, error={e}")
        
        # Default fallback - 1 hour from now
        logger.warning(f"Could not parse time '{time_str}', using 1 hour from now")
        result_time = now + timedelta(hours=1)
        return self._to_utc(result_time)

    def _extract_number(self, text: str) -> float:
        """Extract number from Hebrew text"""
        import re
        
        # Hebrew number words (including feminine forms)
        hebrew_numbers = {
            # Masculine forms
            "אחד": 1, "שניים": 2, "שלושה": 3, "ארבעה": 4, "חמישה": 5,
            "שישה": 6, "שבעה": 7, "שמונה": 8, "תשעה": 9, "עשרה": 10,
            # Feminine forms (used with feminine nouns like דקות, שעות)
            "אחת": 1, "שתי": 2, "שתיים": 2, "שלוש": 3, "ארבע": 4, "חמש": 5,
            "שש": 6, "שבע": 7, "שמונה": 8, "תשע": 9, "עשר": 10,
            # Combined numbers
            "אחד עשר": 11, "שתים עשרה": 12, "שלוש עשרה": 13,
            "ארבע עשרה": 14, "חמש עשרה": 15, "שש עשרה": 16,
            "שבע עשרה": 17, "שמונה עשרה": 18, "תשע עשרה": 19,
            "עשרים": 20, "שלושים": 30, "ארבעים": 40, "חמישים": 50,
            # Fractions
            "חצי": 0.5, "רבע": 0.25, "שלושת רבעי": 0.75
        }
        
        logger.info(f"Extracting number from: '{text}'")
        
        # Try Hebrew number words first (longer phrases first)
        sorted_hebrew = sorted(hebrew_numbers.items(), key=lambda x: len(x[0]), reverse=True)
        for hebrew_num, value in sorted_hebrew:
            if hebrew_num in text:
                logger.info(f"Found Hebrew number: '{hebrew_num}' = {value}")
                return value
        
        # Try to extract digits
        numbers = re.findall(r'\d+', text)
        if numbers:
            number = int(numbers[0])
            logger.info(f"Found digit: {number}")
            return number
        
        logger.warning(f"No number found in: '{text}'")
        return None

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