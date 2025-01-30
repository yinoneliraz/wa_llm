from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import AsyncEngine

from handler.upsert import upsert
from models import Group, BaseGroup, Sender, BaseSender
from .client import WhatsAppClient


async def gather_groups(db_engine: AsyncEngine, client: WhatsAppClient):
    groups = await client.get_user_groups()

    async with AsyncSession(db_engine) as session:
        try:
            for g in groups.results.data:
                if (await session.get(Sender, g.OwnerJID)) is None:
                    owner = Sender(
                        **BaseSender(
                            jid=g.OwnerJID,
                        ).model_dump()
                    )
                    await upsert(session, owner)

                group = Group(
                    **BaseGroup(
                        group_jid=g.JID,
                        group_name=g.Name,
                        group_topic=g.Topic,
                        owner_jid=g.OwnerJID,
                    ).model_dump()
                )
                await upsert(session, group)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
