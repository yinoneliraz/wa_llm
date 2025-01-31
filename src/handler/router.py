from enum import Enum

from pydantic import BaseModel, TypeAdapter
from pydantic_ai import Agent
from sqlmodel import desc, select

from models import Message
from whatsapp import SendMessageRequest
from .base_handler import BaseHandler


class RouteEnum(str, Enum):
    hey = "HEY"
    summarize = "SUMMARIZE"
    ignore = "IGNORE"


class RouteModel(BaseModel):
    route: RouteEnum


class Router(BaseHandler):
    async def __call__(self, message: Message):
        route = await self._route(message.text)
        match route:
            case RouteEnum.hey:
                await self.send_message(message.chat_jid, "its the voice of my mother"),
            case RouteEnum.summarize:
                await self.summarize(message.chat_jid)
            case RouteEnum.ignore:
                pass

    async def _route(self, message: str) -> RouteEnum:
        agent = Agent(
            model="anthropic:claude-3-5-sonnet-latest",
            system_prompt="Extract a routing decision from the input.",
            result_type=RouteEnum,
        )

        result = await agent.run(message)
        return result.data

    async def summarize(self, chat_jid: str):
        stmt = (
            select(Message)
            .where(Message.chat_jid == chat_jid)
            .order_by(desc(Message.timestamp))
            .limit(5)
        )
        messages: list[Message] = self.session.exec(stmt).all()

        agent = Agent(
            model="anthropic:claude-3-5-sonnet-latest",
            system_prompt="Summarize the following messages in a few words.",
            result_type=str,
        )

        response = await agent.run(TypeAdapter(list[Message]).dump_json(messages).decode())
        await self.send_message(chat_jid, response.data)
