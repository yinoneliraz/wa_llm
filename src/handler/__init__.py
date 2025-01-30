from sqlalchemy.dialects.postgresql import insert
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from config import Settings
from handler.router import Router
from models import (
    WhatsAppWebhookPayload,
    BaseGroup,
    BaseSender,
    Message,
    Sender,
    Group,
)


class MessageHandler:
    def __init__(self, settings: Settings, session: AsyncSession):
        self.settings = settings
        self.session = session
        self.router = Router(session, settings.my_number)

    async def __call__(self, payload: WhatsAppWebhookPayload):
        message = await self.store_message(payload)

        # if I am in the message mention then:
        if message.text:
            if message.has_mentioned(self.settings.my_number):
                await self.router.handle(message)


    async def store_message(self, payload: WhatsAppWebhookPayload) -> Message:
        message = Message.from_webhook(payload)

        with self.session.begin_nested():
            # Ensure sender exists and is committed
            if (await self.session.get(Sender, message.sender_jid)) is None:
                sender = Sender(**BaseSender(
                    jid=message.sender_jid,  # Use normalized JID from message
                    push_name=payload.pushname,
                ).model_dump())
                await self.upsert(sender)
                await self.session.flush()  # Ensure sender is visible in this transaction

            if message.group_jid:
                if (await self.session.get(Group, message.group_jid)) is None:
                    # TODO: Retrieve group data if it's not exists

                    group = Group(**BaseGroup(group_jid=message.group_jid).model_dump())
                    await self.upsert(group)
                    await self.session.flush()  # Ensure group is visible in this transaction

            # Finally add the message
            self.session.add(message)
            await self.session.flush()  # Ensure everything is written

            # Don't call commit() inside a transaction!
            # Remove self.session.commit()

        return message

    async def upsert(self, entity: SQLModel):
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
        return await self.session.exec(stmt)
