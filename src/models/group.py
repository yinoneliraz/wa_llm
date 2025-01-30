from typing import TYPE_CHECKING, Annotated, List, Optional

from pydantic import BeforeValidator
from sqlmodel import Field, Relationship, SQLModel

from .jid import normalize_jid

if TYPE_CHECKING:
    from .message import Message
    from .sender import Sender


class Group(SQLModel, table=True):
    group_jid: Annotated[str, BeforeValidator(normalize_jid)] = Field(
        primary_key=True, max_length=255
    )
    group_name: Optional[str] = Field(default=None, max_length=255)
    group_topic: Optional[str] = Field(default=None, max_length=255)
    owner_jid: Annotated[str, BeforeValidator(normalize_jid)] = Field(
        max_length=255, foreign_key="sender.jid"
    )
    managed: bool = Field(default=False)

    owner: Optional["Sender"] = Relationship(back_populates="groups_owned")
    messages: List["Message"] = Relationship(back_populates="group")
