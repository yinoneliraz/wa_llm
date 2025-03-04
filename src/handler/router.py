import logging
from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, TypeAdapter, Field
from pydantic_ai import Agent
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession
from voyageai.client_async import AsyncClient

from handler.knowledge_base_answers import KnowledgeBaseAnswers
from models import Message
from whatsapp import WhatsAppClient
from .base_handler import BaseHandler

# Creating an object
logger = logging.getLogger(__name__)


class IntentEnum(str, Enum):
    summarize = "summarize"
    ask_question = "ask_question"


class Intent(BaseModel):
    intent: IntentEnum = Field(
        description="""The intent of the message.
- summarize: The user wants to summarize the chat messages, or to catch up on the chat messages.
- ask_question: The user wants to ask a question about the chat messages or learn from the collective knowledge of the group."""
    )


class Router(BaseHandler):
    def __init__(
        self,
        session: AsyncSession,
        whatsapp: WhatsAppClient,
        embedding_client: AsyncClient,
    ):
        self.ask_knowledge_base = KnowledgeBaseAnswers(
            session, whatsapp, embedding_client
        )
        super().__init__(session, whatsapp, embedding_client)

    async def __call__(self, message: Message):
        route = await self._route(message.text)
        match route:
            case IntentEnum.summarize:
                await self.summarize(message.chat_jid)
            case IntentEnum.ask_question:
                await self.ask_knowledge_base(message)

    async def _route(self, message: str) -> IntentEnum:
        agent = Agent(
            model="anthropic:claude-3-5-haiku-latest",
            system_prompt="What is the intent of the message? What does the user want us to help with?",
            result_type=Intent,
        )

        result = await agent.run(message)
        return result.data.intent

    async def summarize(self, chat_jid: str):
        time_24_hours_ago = datetime.now() - timedelta(hours=24)
        stmt = (
            select(Message)
            .where(Message.chat_jid == chat_jid)
            .where(Message.timestamp >= time_24_hours_ago)
            .order_by(desc(Message.timestamp))
            .limit(60)
        )
        res = await self.session.exec(stmt)
        messages: list[Message] = res.all()

        agent = Agent(
            model="anthropic:claude-3-5-sonnet-latest",
            system_prompt="Summarize the following group chat messages in a few words.",
            result_type=str,
        )

        # TODO: format messages in a way that is easy for the LLM to read
        response = await agent.run(
            TypeAdapter(list[Message]).dump_json(messages).decode()
        )
        await self.send_message(chat_jid, response.data)
