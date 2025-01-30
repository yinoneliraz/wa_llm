import json

from sqlmodel import Session, desc, select
from pydantic import BaseModel

from pydantic_ai import Agent
from config import Settings
from models import Message
from whatsapp_gw import MessageRequest, send_whatsapp_message

from enum import Enum

class RouteEnum(str, Enum):
    hey = 'HEY'
    summarize = 'SUMMARIZE'
    ignore = 'IGNORE'

class RouteModel(BaseModel):
    route: RouteEnum


class MessageHandler:
    def __init__(self, settings: Settings, session: Session):
        self.settings = settings
        self.session = session

    async def __call__(self, message: Message):
        self.session.add(message)

        # if I am in the message mention then:
        if message.text:
            if self.mentioned_me(message):
                
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

    def mentioned_me(self, message: Message) -> bool:
        # TODO: migrate from using my number from from env variable to /devices endpoint.
        # at least validate that the message is from a device that is connected to my number
        assert message.text
        return f"@{self.settings.my_number}" in message.text

    async def summarize(self, chat_jid: str):
        stmt = (
            select(Message)
            .where(Message.chat_jid == chat_jid)
            .order_by(desc(Message.timestamp))
            .limit(5)
        )
        messages = self.session.exec(stmt).all()
        messages_str = json.dumps(messages)
        response = await self.prompt(
            messages_str, "Please summarize the following messages in a few words"
        )
        await self.send_message(MessageRequest(phone=chat_jid, message=response))

    async def send_message(self, message: MessageRequest):
        resp = await send_whatsapp_message(message)
        self.session.add(
            Message(
                message_id=resp.results.message_id,
                text=message.message,
                sender_jid=self.settings.my_number,
                chat_jid=message.phone,
            )
        )



    async def prompt(
        self, message: str, system: str = "You are a helpful assistant"
    ) -> str:
        
        agent = Agent(
            model='anthropic:claude-3-5-sonnet-latest',
            system_prompt=system,
        )

        result = await agent.run(message)  
        return result.data


    async def route(self, message: str) -> RouteEnum:
        agent = Agent(
            model='anthropic:claude-3-5-sonnet-latest',
            system_prompt='Extract a routing decision from the input.',
            result_type=RouteEnum,
        )

        result = await agent.run(message)  
        return result.data