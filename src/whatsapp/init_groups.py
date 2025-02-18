from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from models import Group, BaseGroup, Sender, BaseSender, upsert
from .client import WhatsAppClient


async def gather_groups(db_engine: AsyncEngine, client: WhatsAppClient):
    groups = await client.get_user_groups()

    async with AsyncSession(db_engine) as session:
        try:
            for g in groups.results.data:
                if (await session.get(Sender, g.OwnerJID)) is None and g.OwnerJID:
                    owner = Sender(
                        **BaseSender(
                            jid=g.OwnerJID,
                        ).model_dump()
                    )
                    await upsert(session, owner)

                og = await session.get(Group, g.JID)

                group = Group(
                    **BaseGroup(
                        group_jid=g.group_jid,
                        group_name=g.Name,
                        group_topic=g.Topic,
                        owner_jid=g.OwnerJID,
                        managed=og.managed if og else False,
                        community_keys=og.community_keys if og else None,
                    ).model_dump()
                )
                await upsert(session, group)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
