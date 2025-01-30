import json

from anthropic import AsyncAnthropic
from sqlmodel import Session, desc, select

from config import Settings
from models import Message
from whatsapp_gw import MessageRequest, send_whatsapp_message


class MessageHandler:
    def __init__(self, settings: Settings, session: Session):
        self.settings = settings
        self.session = session
        self.cli = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def __call__(self, message: Message):
        self.session.add(message)

        # if I am in the message mention then:
        if message.text:
            if self.mentioned_me(message):
                if "hey" in message.text:
                    await self.send_message(
                        MessageRequest(
                            phone=message.chat_jid, message="its the voice of my mother"
                        ),
                    )
                if "summarize" in message.text:
                    await self.summarize(message.chat_jid)

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
        response = await self.cli.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            system=system,
            messages=[{"role": "user", "content": message}],
        )

        assert response.content[0].type == "text"
        return response.content[0].text
