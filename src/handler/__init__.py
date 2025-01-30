import json

from anthropic import AsyncAnthropic
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, desc, select, SQLModel

from config import Settings
from models import (
    WhatsAppWebhookPayload,
    BaseGroup,
    BaseMessage,
    BaseSender,
    Message,
    Sender,
    Group,
)
from whatsapp_gw import MessageRequest, send_whatsapp_message


class MessageHandler:
    def __init__(self, settings: Settings, session: Session):
        self.settings = settings
        self.session = session
        self.cli = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def __call__(self, payload: WhatsAppWebhookPayload):
        message = await self.store_message(payload)

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

    def mentioned_me(self, message: BaseMessage) -> bool:
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

    async def store_message(self, payload: WhatsAppWebhookPayload) -> Message:
        message = Message.from_webhook(payload)

        with self.session.begin_nested():
            # Ensure sender exists and is committed
            if self.session.get(Sender, message.sender_jid) is None:
                sender = Sender(**BaseSender(
                    jid=message.sender_jid,  # Use normalized JID from message
                    push_name=payload.pushname,
                ).model_dump())
                self.upsert(sender)
                self.session.flush()  # Ensure sender is visible in this transaction

            if message.group_jid:
                if self.session.get(Group, message.group_jid) is None:
                    # TODO: Retrieve group if it's not exists

                    group = Group(**Group(group_jid=message.group_jid).model_dump())
                    self.upsert(group)
                    self.session.flush()  # Ensure group is visible in this transaction

            # Finally add the message
            self.session.add(message)
            self.session.flush()  # Ensure everything is written

            # Don't call commit() inside a transaction!
            # Remove self.session.commit()

        return message

    async def send_message(self, message: MessageRequest):
        resp = await send_whatsapp_message(message)
        with self.session.begin_nested():
            new_message = Message(
                message_id=resp.results.message_id,
                text=message.message,
                sender_jid=self.settings.my_number,
                chat_jid=message.phone,
            )

            # Ensure sender exists (should be our bot's sender record)
            if self.session.get(Sender, self.settings.my_number) is None:
                sender = Sender(
                    jid=self.settings.my_number,
                    push_name="Bot",  # Or whatever name you want to give your bot
                )
                self.upsert(sender)
                self.session.flush()

            self.upsert(new_message)
            self.session.flush()

    def upsert(self, entity: SQLModel):
        # Split fields into primary keys and values
        pkeys, vals = {}, {}
        for f in entity.__table__.columns:
            (pkeys if f.primary_key else vals)[f.name] = getattr(entity, f.name)

        # Create insert statement
        stmt = insert(entity.__class__).values(**{**pkeys, **vals})

        # Create on_conflict_do_update statement
        stmt = stmt.on_conflict_do_update(
            index_elements=list(pkeys.keys()),  # Convert keys to list
            set_={
                k: stmt.excluded[k]  # Use excluded to reference values from INSERT
                for k in vals.keys()  # Only update non-primary key columns
            },
        )

        # Execute the statement (don't use session.add with insert statement)
        return self.session.execute(stmt)
