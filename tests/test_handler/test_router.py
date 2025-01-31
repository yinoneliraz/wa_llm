from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic_ai import Agent
from pydantic_ai.result import RunResult

from handler.router import Router, RouteEnum
from models import Message
from whatsapp import SendMessageRequest
from .mock_session import mock_session


@pytest.fixture
def mock_whatsapp():
    client = AsyncMock()
    client.send_message = AsyncMock()
    client.get_my_jid = AsyncMock(return_value="bot@s.whatsapp.net")
    return client


@pytest.fixture
def test_message():
    return Message(
        message_id="test_id",
        text="Hello bot!",
        chat_jid="user@s.whatsapp.net",
        sender_jid="user@s.whatsapp.net",
        timestamp=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_router_hey_route(mock_session, mock_whatsapp, test_message, monkeypatch):
    # Mock the Agent class
    mock_agent = Mock()
    mock_agent.run = AsyncMock(return_value=RunResult([], 0, RouteEnum.hey, None, None))

    monkeypatch.setattr(Agent, "__init__", lambda *args, **kwargs: None)
    monkeypatch.setattr(Agent, "run", mock_agent.run)

    # Set up mock response for send_message
    mock_whatsapp.send_message.return_value.results.message_id = "response_id"

    # Create router instance
    router = Router(mock_session, mock_whatsapp)

    # Test the route
    await router(test_message)

    # Verify the message was sent
    mock_whatsapp.send_message.assert_called_once_with(
        SendMessageRequest(
            phone="user@s.whatsapp.net",
            message="its the voice of my mother",
        )
    )


@pytest.mark.asyncio
async def test_router_summarize_route(mock_session, mock_whatsapp, test_message, monkeypatch):
    # Mock the Agent class for routing
    mock_route_agent = Mock()
    mock_route_agent.run = AsyncMock(return_value=RunResult([], 0, RouteEnum.summarize, None, None))

    # Mock the Agent class for summarization
    mock_summarize_agent = Mock()
    mock_summarize_agent.run = AsyncMock(return_value="Summary of messages")

    # Setup agent mocks
    agents = {"route": mock_route_agent, "summarize": mock_summarize_agent}
    agent_counter = 0

    def mock_agent_init(*args, **kwargs):
        nonlocal agent_counter
        return None

    def mock_agent_run(*args, **kwargs):
        nonlocal agent_counter
        agent = list(agents.values())[agent_counter]
        agent_counter = (agent_counter + 1) % len(agents)
        return agent.run(*args, **kwargs)

    monkeypatch.setattr(Agent, "__init__", mock_agent_init)
    monkeypatch.setattr(Agent, "run", mock_agent_run)

    # Mock session.exec() for message history
    mock_exec = AsyncMock()
    mock_exec.all.return_value = [test_message]
    mock_session.exec.return_value = mock_exec

    # Set up mock response for send_message
    mock_whatsapp.send_message.return_value.results.message_id = "response_id"

    # Create router instance
    router = Router(mock_session, mock_whatsapp)

    # Test the route
    await router(test_message)

    # Verify the summary was sent
    mock_whatsapp.send_message.assert_called_once_with(
        SendMessageRequest(
            phone="user@s.whatsapp.net",
            message="Summary of messages",
        )
    )


@pytest.mark.asyncio
async def test_router_ignore_route(mock_session, mock_whatsapp, test_message, monkeypatch):
    # Mock the Agent class
    mock_agent = Mock()
    mock_agent.run = AsyncMock(return_value=RouteEnum.ignore)
    monkeypatch.setattr(Agent, "__init__", lambda *args, **kwargs: None)
    monkeypatch.setattr(Agent, "run", mock_agent.run)

    # Create router instance
    router = Router(mock_session, mock_whatsapp)

    # Test the route
    await router(test_message)

    # Verify no message was sent
    mock_whatsapp.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_message(mock_session, mock_whatsapp):
    # Set up mock response
    mock_whatsapp.send_message.return_value.results.message_id = "response_id"
    mock_session.get.return_value = None  # Simulate sender doesn't exist

    # Create router instance
    router = Router(mock_session, mock_whatsapp)

    # Test sending a message
    await router.send_message(
        SendMessageRequest(
            phone="user@s.whatsapp.net",
            message="Test message",
        )
    )

    # Verify the message was sent and stored
    mock_whatsapp.send_message.assert_called_once()
    mock_session.flush.assert_called() 