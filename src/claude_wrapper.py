import os
from anthropic import Anthropic
from anthropic.types import Message

# TODO: make class latter..
# def init_claude(api_key: str) -> Anthropic:
#     anthropic = Anthropic(api_key=api_key)
#     return anthropic


def prompt(message: str, system: str = "You are a helpful assistant") -> str:
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Call Claude
    response: Message = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=1000,
        system=system,
        messages=[{
            "role": "user",
            "content": message
        }]
    )

    # Get Claude's response
    if not response.content:
        return ""
    return response.content[0].text