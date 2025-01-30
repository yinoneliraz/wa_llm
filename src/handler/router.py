from enum import Enum

from pydantic import BaseModel, TypeAdapter
from pydantic_ai import Agent
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import desc, select

from models import Message, Sender
from whatsapp_gw import MessageRequest, send_whatsapp_message


class RouteEnum(str, Enum):
    hey = "HEY"
    summarize = "SUMMARIZE"
    ignore = "IGNORE"


class RouteModel(BaseModel):
    route: RouteEnum


class Router:
    def __init__(self, session: AsyncSession, my_number: str):
        self.session = session
        self.my_number = my_number

    async def handle(self, message: Message):
        route = await self.route(message.text)
        match route:
            case RouteEnum.hey:
                await self.send_message(
                    MessageRequest(
                        phone=message.chat_jid, message="its the voice of my mother"
                    ),
                )
            case RouteEnum.summarize:
                await self.summarize(message.chat_jid)
            case RouteEnum.ignore:
                pass

    async def route(self, message: str) -> RouteEnum:
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
        await self.send_message(MessageRequest(phone=chat_jid, message=response.data))

    async def send_message(self, message: MessageRequest):
        resp = await send_whatsapp_message(message)
        with self.session.begin_nested():
            new_message = Message(
                message_id=resp.results.message_id,
                text=message.message,
                sender_jid=self.my_number,
                chat_jid=message.phone,
            )

            # Ensure sender exists (should be our bot's sender record)
            if (await self.session.get(Sender, self.my_number)) is None:
                sender = Sender(
                    jid=self.my_number,
                    push_name="Bot",  # Or whatever name you want to give your bot
                )
                await self.upsert(sender)
                await self.session.flush()

            await self.upsert(new_message)
            await self.session.flush()
