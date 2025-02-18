import logging
from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, TypeAdapter
from pydantic_ai import Agent
from sqlmodel import desc, select

from models import Message
from .base_handler import BaseHandler

# Creating an object
logger = logging.getLogger(__name__)


class RouteEnum(str, Enum):
    summarize = "SUMMARIZE"
    ask_question = "ASK_QUESTION"
    other = "OTHER"


class RouteModel(BaseModel):
    route: RouteEnum


class Router(BaseHandler):
    async def __call__(self, message: Message):
        route = await self._route(message.text)
        match route:
            case RouteEnum.summarize:
                await self.summarize(message.chat_jid)
            case RouteEnum.other:
                logging.warning(
                    f"OTHER route was chosen Lets see why: {message.text}, {message.chat_jid}"
                )

    async def _route(self, message: str) -> RouteEnum:
        agent = Agent(
            model="anthropic:claude-3-5-haiku-latest",
            system_prompt="Extract a routing decision from the input.",
            result_type=RouteEnum,
        )

        result = await agent.run(message)
        return result.data

    async def summarize(self, chat_jid: str):
        time_24_hours_ago = datetime.utcnow() - timedelta(hours=24)
        stmt = (
            select(Message)
            .where(Message.chat_jid == chat_jid)
            .where(Message.timestamp >= time_24_hours_ago)
            .order_by(desc(Message.timestamp))
        )
        res = await self.session.exec(stmt)
        messages: list[Message] = res.all()

        agent = Agent(
            model="anthropic:claude-3-5-sonnet-latest",
            system_prompt="Summarize the following messages in a few words.",
            result_type=str,
        )

        # TODO: format messages in a way that is easy for the LLM to read
        response = await agent.run(
            TypeAdapter(list[Message]).dump_json(messages).decode()
        )
        await self.send_message(chat_jid, response.data)
