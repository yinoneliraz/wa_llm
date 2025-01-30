from sqlalchemy.dialects.postgresql import insert
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


async def upsert(session: AsyncSession, entity: SQLModel):
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

    return await session.execute(stmt)
