from sqlmodel.ext.asyncio.session import AsyncSession

from handler.router import Router
from models import (
    WhatsAppWebhookPayload,
    BaseGroup,
    BaseSender,
    Message,
    Sender,
    Group,
)
from whatsapp import WhatsAppClient
from .upsert import upsert


class MessageHandler:
    def __init__(self, session: AsyncSession, whatsapp: WhatsAppClient):
        self.session = session
        self.whatsapp = whatsapp
        self.router = Router(session, whatsapp)

    async def __call__(self, payload: WhatsAppWebhookPayload):
        message = await self.store_message(payload)

        # if I am in the message mention then:
        if message.text:
            if message.has_mentioned(await self.whatsapp.get_my_jid()):
                if message.group and not message.group.managed:
                    return
                await self.router(message)

    async def store_message(self, payload: WhatsAppWebhookPayload) -> Message:
        message = Message.from_webhook(payload)

        async with self.session.begin_nested():
            # Ensure sender exists and is committed
            if (await self.session.get(Sender, message.sender_jid)) is None:
                sender = Sender(
                    **BaseSender(
                        jid=message.sender_jid,  # Use normalized JID from message
                        push_name=payload.pushname,
                    ).model_dump()
                )
                await upsert(self.session, sender)
                await (
                    self.session.flush()
                )  # Ensure sender is visible in this transaction

            if message.group_jid:
                if (await self.session.get(Group, message.group_jid)) is None:
                    group = Group(**BaseGroup(group_jid=message.group_jid).model_dump())
                    await upsert(self.session, group)
                    await self.session.flush()

            # Finally add the message
            self.session.add(message)
            await self.session.flush()

        await self.session.refresh(message)
        return message
