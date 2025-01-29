from typing import TYPE_CHECKING, Annotated, List, Optional

from pydantic import BeforeValidator
from sqlmodel import Field, Relationship, SQLModel

from src.jid import normalize_jid

if TYPE_CHECKING:
    from .group import Group
    from .message import Message


class Sender(SQLModel, table=True):
    jid: Annotated[str, BeforeValidator(normalize_jid)] = Field(
        primary_key=True, max_length=255
    )
    push_name: Optional[str] = Field(default=None, max_length=255)

    messages: List["Message"] = Relationship(back_populates="sender")
    groups_owned: List["Group"] = Relationship(back_populates="owner")
