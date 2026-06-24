from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart

def manage_conversation(conversation_history: list, new_messages: list, history_limit: int = 30):
    cleaned = _clean_history(new_messages)

    conversation_history.extend(cleaned)

    if len(conversation_history) > history_limit:
        conversation_history = conversation_history[-history_limit:]

    return conversation_history

def _clean_history(history: list) -> list:
    """
    Strip tool call and tool return parts from history messages.
    The LLM only needs the user/assistant text exchange for context —
    keeping tool parts causes it to re-run every tool call from previous turns.
    """
    clean = []
    for message in history:
        if isinstance(message, ModelRequest):
            # Keep only UserPromptPart (user text), drop tool return parts
            text_parts = [p for p in message.parts if isinstance(p, UserPromptPart)]
            if text_parts:
                clean.append(ModelRequest(parts=text_parts))
        elif isinstance(message, ModelResponse):
            # Keep only TextPart (assistant text), drop tool call parts
            text_parts = [p for p in message.parts if isinstance(p, TextPart)]
            if text_parts:
                clean.append(ModelResponse(parts=text_parts, model_name=message.model_name, timestamp=message.timestamp))
    return clean