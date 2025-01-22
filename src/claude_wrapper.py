from anthropic import Anthropic
from anthropic.types import Message
from config import Settings

# TODO: make class latter..
# def init_claude(api_key: str) -> Anthropic:
#     anthropic = Anthropic(api_key=api_key)
#     return anthropic


def prompt(message: str, system: str = "You are a helpful assistant") -> str:

    settings = Settings()
    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

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
    print(f"message is {message}, system is {system}, response is {response}")
    # Get Claude's response
    if not response.content:
        return ""
    return response.content[0].text