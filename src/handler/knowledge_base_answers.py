import logging
from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, TypeAdapter, Field
from pydantic_ai import Agent
from sqlmodel import desc, select

from models import Message, KBTopic
from utils.voyage_embed_text import voyage_embed_text
from .base_handler import BaseHandler

# Creating an object
logger = logging.getLogger(__name__)


class KnowledgeBaseAnswers(BaseHandler):
    async def __call__(self, message: Message):
        await self.ask_question(message.text, message.chat_jid)

    async def ask_question(self, question: str, chat_jid: str):
        rephrased_agent = Agent(
            model="anthropic:claude-3-5-haiku-latest",
            system_prompt="Phrase the following sentence to retrieve information for the knowledge base. ONLY answer with the new phrased query, no other text",
        )

        # We obviously need to translate the question and turn the question vebality to a title / summary text to make it closer to the questions in the rag
        rephrased_response = await rephrased_agent.run(question)
        # Get query embedding
        embedded_question = (
            await voyage_embed_text(self.embedding_client, [rephrased_response.data])
        )[0]

        # query for user query
        retrieved_topics = await self.session.exec(
            select(KBTopic)
            .order_by(KBTopic.embedding.l2_distance(embedded_question))
            .limit(5)
        )

        similar_topics = []
        for result in retrieved_topics:
            similar_topics.append(f"{result.subject} \n {result.summary}")

        generation_agent = Agent(
            model="anthropic:claude-3-5-sonnet-latest",
            system_prompt="""Based on the topics attached, write a response to the query.
            - Write a casual direct response to the query. no need to repeat the query.
            - Answer in the same language as the query.
            - Only answer from the topics attached, no other text.
            - When answering, provide a complete answer to the message - telling the user everything they need to know. BUT not too much! remember - it's a chat.
            - Please do tag users while talking about them (e.g., @972536150150). ONLY answer with the new phrased query, no other text.""",
        )

        prompt_template = f"""
        question: {rephrased_response.data}

        topics related to the query:
        {"\n---\n".join(similar_topics)}
        """

        generation_response = await generation_agent.run(prompt_template)
        logger.info(
            "RAG Query Results:\n"
            f"Question: {question}\n"
            f"Chat JID: {chat_jid}\n"
            f"Retrieved Topics: {len(similar_topics)}\n"
            "Topics:\n"
            + "\n".join(f"- {topic[:100]}..." for topic in similar_topics)
            + "\n"
            f"Generated Response: {generation_response.data}"
        )
        await self.send_message(chat_jid, generation_response.data)
