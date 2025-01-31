from typing import TYPE_CHECKING, List, Optional

from pydantic import field_validator
from sqlmodel import Field, Relationship, SQLModel

from .jid import normalize_jid

if TYPE_CHECKING:
    from .message import Message
    from .sender import Sender


class BaseGroup(SQLModel):
    group_jid: str = Field(primary_key=True, max_length=255)
    group_name: Optional[str] = Field(default=None, max_length=255)
    group_topic: Optional[str] = Field(default=None)
    owner_jid: Optional[str] = Field(
        max_length=255, foreign_key="sender.jid", nullable=True
    )
    managed: bool = Field(default=False)

    @field_validator("group_jid", "owner_jid", mode="before")
    @classmethod
    def normalize(cls, value: Optional[str]) -> str:
        return normalize_jid(value) if value else None


class Group(BaseGroup, table=True):
    owner: Optional["Sender"] = Relationship(back_populates="groups_owned")
    messages: List["Message"] = Relationship(back_populates="group")


Group.model_rebuild()
