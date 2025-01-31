from datetime import datetime, timezone

import pytest
from sqlmodel import select

from models import Message, Sender, Group
from models.webhook import WhatsAppWebhookPayload
from ..mock_session import mock_session # noqa


@pytest.mark.asyncio
async def test_message_creation(mock_session):
    # Create test data
    sender = Sender(jid="1234567890@s.whatsapp.net", push_name="Test User")
    group = Group(
        group_jid="123456789-123456@g.us",
        group_name="Test Group",
        owner_jid="1234567890@s.whatsapp.net",
    )

    mock_session.add(sender)
    mock_session.add(group)
    await mock_session.commit()

    # Create message from webhook payload
    payload = WhatsAppWebhookPayload(
        from_="1234567890@s.whatsapp.net in 123456789-123456@g.us",
        timestamp=datetime.now(timezone.utc),
        pushname="Test User",
        message={
            "id": "test_message_id",
            "text": "Hello @bot how are you?",
            "replied_id": None,
        },
    )

    message = Message.from_webhook(payload)
    assert message.message_id == "test_message_id"
    assert message.text == "Hello @bot how are you?"
    assert message.sender_jid == "1234567890@s.whatsapp.net"
    assert message.group_jid == "123456789-123456@g.us"

    # Test database persistence
    mock_session.add(message)
    await mock_session.commit()
    await mock_session.refresh(message)

    # Query and verify
    stmt = select(Message).where(Message.message_id == "test_message_id")
    result = await mock_session.execute(stmt)
    db_message = result.scalar_one()

    assert db_message.text == "Hello @bot how are you?"
    assert db_message.sender.push_name == "Test User"
    assert db_message.group.group_name == "Test Group"


@pytest.mark.asyncio
async def test_message_mentions(mock_session):
    message = Message(
        message_id="test_mention",
        text="Hey @1234567890 check this out",
        chat_jid="group@g.us",
        sender_jid="sender@s.whatsapp.net",
    )

    assert message.has_mentioned("1234567890@s.whatsapp.net")
    assert not message.has_mentioned("9876543210@s.whatsapp.net") 