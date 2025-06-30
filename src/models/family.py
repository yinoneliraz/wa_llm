from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from uuid import uuid4

from sqlmodel import Field, Relationship, SQLModel, Column, DateTime, Index

if TYPE_CHECKING:
    from .group import Group
    from .sender import Sender


class GroceryList(SQLModel, table=True):
    """Represents a grocery shopping list for a family group"""
    id: str = Field(primary_key=True, default_factory=lambda: str(uuid4()))
    group_jid: str = Field(max_length=255, foreign_key="group.group_jid")
    name: str = Field(default="Shopping List", max_length=255)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    
    # Relationships
    items: List["GroceryItem"] = Relationship(back_populates="grocery_list")
    group: Optional["Group"] = Relationship()

    __table_args__ = (
        Index("idx_grocery_list_group", "group_jid"),
    )


class GroceryItem(SQLModel, table=True):
    """Individual items in a grocery list"""
    id: str = Field(primary_key=True, default_factory=lambda: str(uuid4()))
    list_id: str = Field(foreign_key="grocerylist.id")
    item_name: str = Field(max_length=255)
    quantity: Optional[str] = Field(default=None, max_length=50)
    added_by: str = Field(max_length=255, foreign_key="sender.jid")
    completed: bool = Field(default=False)
    completed_by: Optional[str] = Field(
        max_length=255, foreign_key="sender.jid", nullable=True
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    
    # Relationships
    grocery_list: Optional[GroceryList] = Relationship(back_populates="items")
    added_by_sender: Optional["Sender"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[GroceryItem.added_by]",
            "primaryjoin": "GroceryItem.added_by == Sender.jid",
        }
    )
    completed_by_sender: Optional["Sender"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[GroceryItem.completed_by]",
            "primaryjoin": "GroceryItem.completed_by == Sender.jid",
        }
    )

    __table_args__ = (
        Index("idx_grocery_item_list", "list_id"),
        Index("idx_grocery_item_completed", "completed"),
    )


class Reminder(SQLModel, table=True):
    """Reminders for family members"""
    id: str = Field(primary_key=True, default_factory=lambda: str(uuid4()))
    group_jid: str = Field(max_length=255, foreign_key="group.group_jid")
    created_by: str = Field(max_length=255, foreign_key="sender.jid")
    message: str = Field(max_length=1000)
    due_time: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    recurring_pattern: Optional[str] = Field(
        default=None, max_length=50
    )  # "daily", "weekly", "monthly", "yearly"
    recurring_interval: Optional[int] = Field(default=None)  # every N days/weeks/etc
    completed: bool = Field(default=False)
    sent: bool = Field(default=False)  # Track if reminder was sent
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    
    # Relationships
    group: Optional["Group"] = Relationship()
    creator: Optional["Sender"] = Relationship()

    __table_args__ = (
        Index("idx_reminder_group", "group_jid"),
        Index("idx_reminder_due_time", "due_time"),
        Index("idx_reminder_completed", "completed"),
        Index("idx_reminder_sent", "sent"),
    )


class ChildScheduleEntry(SQLModel, table=True):
    """Schedule entries for children (feeding, naps, etc.)"""
    id: str = Field(primary_key=True, default_factory=lambda: str(uuid4()))
    group_jid: str = Field(max_length=255, foreign_key="group.group_jid")
    child_name: str = Field(max_length=100)  # "toddler", "baby", or actual name
    activity_type: str = Field(max_length=50)  # "feeding", "nap", "diaper", "milestone"
    notes: Optional[str] = Field(default=None, max_length=500)
    recorded_by: str = Field(max_length=255, foreign_key="sender.jid")
    activity_time: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    duration_minutes: Optional[int] = Field(default=None)  # For naps, feeding duration
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    
    # Relationships
    group: Optional["Group"] = Relationship()
    recorder: Optional["Sender"] = Relationship()

    __table_args__ = (
        Index("idx_schedule_group", "group_jid"),
        Index("idx_schedule_child", "child_name"),
        Index("idx_schedule_activity", "activity_type"),
        Index("idx_schedule_time", "activity_time"),
    )