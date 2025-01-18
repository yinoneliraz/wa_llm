import os
from claude_wrapper import prompt

def route_message(message: str) -> str:
    if message.startswith("hey @username"):
        return "who calls my name music"
    return ""

    #call claude api
    claude = init_claude(os.getenv("ANTHROPIC_API_KEY"))
    response = prompt(claude, message)
    # return response



    # if I am in the message mention then:
    if check_if_i_am_mentioned() "who calls my name music"
    # if the message includes "hey @username" I reply "its the voice of my mother"
    # if the message includes "someone is looking for you on the phone" If its not I don't aggrees "



def check_if_i_am_mentioned(message: str) -> bool:
    MY_NUMBER = os.getenv("MY_NUMBER")
    return f"@{MY_NUMBER}" in message