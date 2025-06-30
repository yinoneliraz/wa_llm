"""
Family Scheduler Module

Handles periodic tasks for family functionality:
- Send due reminders
- Process recurring reminders
- Generate daily summaries for child schedules
- Clean up old completed tasks

Usage:
- Run as a background task in your main application
- Or as a separate cron job using a script like app/family_scheduler.py
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List

from sqlmodel import select, and_, or_
from sqlmodel.ext.asyncio.session import AsyncSession

from models.family import Reminder, ChildScheduleEntry, GroceryItem
from whatsapp import WhatsAppClient, SendMessageRequest

logger = logging.getLogger(__name__)


class FamilyScheduler:
    """Scheduler for family-related periodic tasks"""
    
    def __init__(self, session: AsyncSession, whatsapp: WhatsAppClient):
        self.session = session
        self.whatsapp = whatsapp
    
    async def run_periodic_tasks(self):
        """Run all periodic tasks"""
        try:
            logger.info("Running family scheduler tasks")
            
            # Send due reminders
            await self._send_due_reminders()
            
            # Process recurring reminders
            await self._process_recurring_reminders()
            
            # Clean up old completed items (optional)
            # await self._cleanup_old_completed_items()
            
            logger.info("Family scheduler tasks completed")
            
        except Exception as e:
            logger.error(f"Error in family scheduler: {e}")
    
    async def _send_due_reminders(self):
        """Send reminders that are due"""
        now = datetime.now(timezone.utc)
        
        # Find due reminders that haven't been sent
        stmt = select(Reminder).where(
            and_(
                Reminder.due_time <= now,
                Reminder.sent == False,
                Reminder.completed == False
            )
        )
        
        result = await self.session.exec(stmt)
        due_reminders = result.all()
        
        for reminder in due_reminders:
            try:
                # Create a nice Hebrew reminder message
                user_phone = reminder.created_by.split('@')[0]  # Extract phone number
                message = f"🔔 **תזכורת עבור @{user_phone}:**\n{reminder.message}"
                
                await self.whatsapp.send_message(
                    SendMessageRequest(
                        phone=reminder.group_jid,
                        message=message
                    )
                )
                
                # Mark as sent
                reminder.sent = True
                self.session.add(reminder)
                
                logger.info(f"Sent reminder: {reminder.message} to {reminder.group_jid}")
                
            except Exception as e:
                logger.error(f"Failed to send reminder {reminder.id}: {e}")
        
        await self.session.commit()
    
    async def _process_recurring_reminders(self):
        """Create new instances of recurring reminders"""
        now = datetime.now(timezone.utc)
        
        # Find completed recurring reminders that need new instances
        stmt = select(Reminder).where(
            and_(
                Reminder.recurring_pattern.isnot(None),
                Reminder.completed == True,
                Reminder.due_time <= now
            )
        )
        
        result = await self.session.exec(stmt)
        recurring_reminders = result.all()
        
        for reminder in recurring_reminders:
            try:
                next_due_time = self._calculate_next_due_time(
                    reminder.due_time, 
                    reminder.recurring_pattern,
                    reminder.recurring_interval or 1
                )
                
                if next_due_time and next_due_time > now:
                    # Create new reminder instance
                    new_reminder = Reminder(
                        group_jid=reminder.group_jid,
                        created_by=reminder.created_by,
                        message=reminder.message,
                        due_time=next_due_time,
                        recurring_pattern=reminder.recurring_pattern,
                        recurring_interval=reminder.recurring_interval,
                        completed=False,
                        sent=False
                    )
                    
                    self.session.add(new_reminder)
                    logger.info(f"Created new recurring reminder: {reminder.message}")
                
            except Exception as e:
                logger.error(f"Failed to process recurring reminder {reminder.id}: {e}")
        
        await self.session.commit()
    
    def _calculate_next_due_time(
        self, 
        last_due_time: datetime, 
        pattern: str, 
        interval: int = 1
    ) -> datetime:
        """Calculate the next due time for a recurring reminder"""
        if pattern == "daily":
            return last_due_time + timedelta(days=interval)
        elif pattern == "weekly":
            return last_due_time + timedelta(weeks=interval)
        elif pattern == "monthly":
            # Approximate monthly (30 days)
            return last_due_time + timedelta(days=30 * interval)
        elif pattern == "yearly":
            return last_due_time + timedelta(days=365 * interval)
        else:
            logger.warning(f"Unknown recurring pattern: {pattern}")
            return None
    
    async def _cleanup_old_completed_items(self, days_old: int = 30):
        """Clean up old completed grocery items and reminders"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        # Clean up old completed grocery items
        stmt = select(GroceryItem).where(
            and_(
                GroceryItem.completed == True,
                GroceryItem.completed_at < cutoff_date
            )
        )
        result = await self.session.exec(stmt)
        old_items = result.all()
        
        for item in old_items:
            await self.session.delete(item)
        
        logger.info(f"Cleaned up {len(old_items)} old grocery items")
        
        # Clean up old completed non-recurring reminders
        stmt = select(Reminder).where(
            and_(
                Reminder.completed == True,
                Reminder.completed_at < cutoff_date,
                Reminder.recurring_pattern.is_(None)
            )
        )
        result = await self.session.exec(stmt)
        old_reminders = result.all()
        
        for reminder in old_reminders:
            await self.session.delete(reminder)
        
        logger.info(f"Cleaned up {len(old_reminders)} old reminders")
        
        await self.session.commit()
    
    async def generate_daily_child_summary(self, group_jid: str, child_name: str) -> str:
        """Generate a daily summary for a child's activities"""
        today = datetime.now(timezone.utc).date()
        start_of_day = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_of_day = start_of_day + timedelta(days=1)
        
        stmt = select(ChildScheduleEntry).where(
            and_(
                ChildScheduleEntry.group_jid == group_jid,
                ChildScheduleEntry.child_name.ilike(f"%{child_name}%"),
                ChildScheduleEntry.activity_time >= start_of_day,
                ChildScheduleEntry.activity_time < end_of_day
            )
        ).order_by(ChildScheduleEntry.activity_time)
        
        result = await self.session.exec(stmt)
        activities = result.all()
        
        if not activities:
            return f"לא נרשמו פעילויות עבור {child_name} היום."
        
        summary = f"📊 **סיכום יום של {child_name.title()}**\n\n"
        
        # Group by activity type
        activity_groups = {}
        for activity in activities:
            activity_type = activity.activity_type
            if activity_type not in activity_groups:
                activity_groups[activity_type] = []
            activity_groups[activity_type].append(activity)
        
        for activity_type, group_activities in activity_groups.items():
            summary += f"**{activity_type.title()}s:**\n"
            for activity in group_activities:
                time_str = activity.activity_time.strftime("%I:%M %p")
                duration_str = f" ({activity.duration_minutes}min)" if activity.duration_minutes else ""
                notes_str = f" - {activity.notes}" if activity.notes else ""
                summary += f"• {time_str}{duration_str}{notes_str}\n"
            summary += "\n"
        
        return summary.strip()


# Example script file for running as cron job:
"""
# app/family_scheduler.py

import asyncio
import logging

import logfire
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from config import Settings
from scheduler.family_scheduler import FamilyScheduler
from whatsapp import WhatsAppClient


async def main():
    settings = Settings()

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=settings.log_level,
    )
    logfire.configure()

    whatsapp = WhatsAppClient(
        settings.whatsapp_host,
        settings.whatsapp_basic_auth_user,
        settings.whatsapp_basic_auth_password,
    )

    engine = create_async_engine(settings.db_uri)
    async_session = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    async with async_session() as session:
        try:
            scheduler = FamilyScheduler(session, whatsapp)
            await scheduler.run_periodic_tasks()
            await session.commit()
        except Exception:
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())
"""