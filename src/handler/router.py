from enum import Enum

from pydantic import BaseModel, TypeAdapter
from pydantic_ai import Agent
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import desc, select

from .upsert import upsert
from models import Message, Sender, BaseMessage, BaseSender
from models.jid import normalize_jid
from whatsapp import WhatsAppClient, SendMessageRequest


class RouteEnum(str, Enum):
    hey = "HEY"
    summarize = "SUMMARIZE"
    ignore = "IGNORE"


class RouteModel(BaseModel):
    route: RouteEnum


class Router:
    def __init__(self, session: AsyncSession, whatsapp: WhatsAppClient):
        self.session = session
        self.whatsapp = whatsapp

    async def __call__(self, message: Message):
        route = await self._route(message.text)
        match route:
            case RouteEnum.hey:
                await self.send_message(
                    SendMessageRequest(
                        phone=message.chat_jid, message="its the voice of my mother"
                    ),
                )
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

        response = await agent.run(TypeAdapter(list[Message]).dump_json(messages))
        await self.send_message(
            SendMessageRequest(phone=chat_jid, message=response.data)
        )

    async def send_message(self, message: SendMessageRequest):
        resp = await self.whatsapp.send_message(message)
        async with self.session.begin_nested():
            my_number = await self.whatsapp.get_my_jid()
            new_message = BaseMessage(
                message_id=resp.results.message_id,
                text=message.message,
                sender_jid=my_number,
                chat_jid=message.phone,
            )

            # Ensure sender exists (should be our bot's sender record)
            if (await self.session.get(Sender, normalize_jid(my_number))) is None:
                sender = BaseSender(
                    jid=my_number,
                )
                await upsert(self.session, Sender(**sender.model_dump()))
                await self.session.flush()

            await upsert(self.session, Message(**new_message.model_dump()))
            await self.session.flush()
