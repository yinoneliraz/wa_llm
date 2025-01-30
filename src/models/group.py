from typing import TYPE_CHECKING, Annotated, List, Optional

from pydantic import BeforeValidator
from sqlmodel import Field, Relationship, SQLModel

from .jid import normalize_jid

if TYPE_CHECKING:
    from .message import Message
    from .sender import Sender


class BaseGroup(SQLModel):
    group_jid: Annotated[str, BeforeValidator(normalize_jid)] = Field(
        primary_key=True, max_length=255
    )
    group_name: Optional[str] = Field(default=None, max_length=255)
    group_topic: Optional[str] = Field(default=None)
    owner_jid: Annotated[Optional[str], BeforeValidator(normalize_jid)] = Field(
        max_length=255, foreign_key="sender.jid", nullable=True
    )
    managed: bool = Field(default=False)


class Group(BaseGroup, table=True):
    owner: Optional["Sender"] = Relationship(back_populates="groups_owned")
    messages: List["Message"] = Relationship(back_populates="group")


Group.model_rebuild()
