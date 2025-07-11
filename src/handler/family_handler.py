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
from models.family import GroceryList, GroceryItem, ChildScheduleEntry
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


class ScheduleCommand(BaseModel):
    """Parsed child schedule command structure"""
    action: str = Field(description="add, show, or log")
    child_name: str = Field(description="name of child: baby, toddler, or actual name")
    activity_type: str = Field(description="feeding, nap, diaper, milestone, etc.")
    notes: Optional[str] = Field(description="additional notes")
    time: Optional[str] = Field(description="time of activity")
    duration: Optional[int] = Field(description="duration in minutes for naps/feeding")


class FamilyHandler(BaseHandler):
    """Handler for family-specific commands: groceries, child schedules"""

    async def __call__(self, message: Message):
        """Main entry point for family command processing"""
        if not message.text or not message.group:
            return

        # Check if this is a family command
        if await self._is_family_command(message.text):
            try:
                if await self._is_grocery_command(message.text):
                    await self._handle_grocery(message)
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
            "baby", "toddler", "feeding", "nap", "diaper", "milestone",
            "family", "help family",
            # Hebrew keywords
            "קניות", "רשימה", "רשימת קניות", "קנה", "קניתי", "לקחתי", "חנות", "סופר",
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

**לוח זמנים ילדים:**
• "התינוק אכל ב2 אחה״צ"
• "הפעוט התחיל לישון"
• "תראה לוח זמנים של התינוק"
• "התינוק עשה את הצעדים הראשונים!" (אבני דרך)

פשוט דבר בטבעיות - אני אבין! 😊
        """
        await self.send_message(message.chat_jid, help_text, message.message_id)

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