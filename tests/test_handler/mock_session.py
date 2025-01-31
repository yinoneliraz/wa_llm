from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


class NestedTransaction:
    def __init__(self, session):
        self.session = session
        self._storage_snapshot = None

    async def __aenter__(self):
        self._storage_snapshot = self.session._storage.copy()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Restore the storage state on exception
            self.session._storage = self._storage_snapshot

class AsyncSessionMock(MagicMock):  # Changed to MagicMock as base
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._storage = {}  # In-memory storage for entities

        # Explicitly set async methods
        self.get = AsyncMock(side_effect=self._get)
        self.add = AsyncMock(side_effect=self._add)
        self.flush = AsyncMock(side_effect=self._flush)
        self.execute = AsyncMock(side_effect=self._execute)

    async def _get(self, model_class, key):
        """Simulates get operation by checking in-memory storage"""
        model_key = (model_class.__name__, key)
        return self._storage.get(model_key)

    async def _add(self, instance):
        """Simulates adding an entity to the session"""
        if not isinstance(instance, SQLModel):
            raise TypeError("Instance must be a SQLModel")

        # Store using class name and primary key as composite key
        for field in instance.__table__.primary_key:
            key = getattr(instance, field.name)
            model_key = (instance.__class__.__name__, key)
            self._storage[model_key] = instance

    async def _flush(self):
        """Simulates flushing the session"""
        pass

    async def _execute(self, statement):
        """Simulates executing a statement"""
        # For upsert operations, we'll simulate the behavior
        if hasattr(statement, 'is_insert') and statement.is_insert:
            # Extract values from the statement
            values = statement._values
            # In a real implementation, you might want to handle the on_conflict_do_update logic
            return MagicMock()
        return MagicMock()

    def begin_nested(self):  # Regular method, not async
        """Returns a context manager for a nested transaction"""
        return NestedTransaction(self)

@pytest.fixture
def mock_session():  # Changed to sync fixture
    """Fixture that provides a mock AsyncSession"""
    session = AsyncSessionMock(spec=AsyncSession)
    return session