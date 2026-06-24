import os
import datetime

LOG_FILE = os.path.join(os.path.dirname(__file__), "conversations_history.txt")

def log_user_message(user_message: str) -> None:
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    full_message = f"{current_time} - You: {user_message}\n"
    print(full_message.strip())

    with open(LOG_FILE, "a") as f:
        f.write(full_message)


def log_assistant_message(ai_message: str) -> None:
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    full_message = f"{current_time} - AI: {ai_message}\n"
    print(full_message.strip())

    with open(LOG_FILE, "a") as f:
        f.write(full_message)