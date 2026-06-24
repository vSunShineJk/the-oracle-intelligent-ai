from pydantic_ai import Agent
from pydantic_ai.messages import ToolCallPart, ToolReturnPart, ModelRequest, ModelResponse, UserPromptPart, TextPart
from openai import  AsyncAzureOpenAI
import os
import asyncio
from dotenv import load_dotenv
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlmodel import Session, text
from agent_memory.database import engine
from tools.gcalendar.gcalendar_api_calls import (
    list_calendars,
    get_upcoming_events,
    get_events_by_date,
    search_events,
    get_event_by_id,
    create_event,
    update_event,
    delete_event,
)

from tools.internet_search.search import web_search
load_dotenv()

azure_client =  AsyncAzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

provider = OpenAIProvider(openai_client=azure_client)
model = OpenAIChatModel(os.getenv("AZURE_OPENAI_DEPLOYMENT"), provider=provider)
agent = Agent(
    model=model,
    system_prompt=(
        "You are an gmail assistant. You have access to a local SQLite database "
        "with a table called 'gmail' that has the following columns: "
        "id (str, primary key), account (str), thread_id (str), subject (str), "
        "sender_name (str), sender_email (str), to_email (str), "
        "date (str, human-readable string like 'Mon, 23 Mar 2026 10:00:00 +0000' — do NOT use this for date filtering), "
        "internal_date (int, unix timestamp in MILLISECONDS — always use this for date/time filtering, divide by 1000 for SQLite unixepoch), "
        "labels (str, comma-separated e.g. 'INBOX,UNREAD'), "
        "snippet (str), body (str), mime_type (str), is_read (bool, 1=read 0=unread). "
        "When the user asks about emails, use the available tools to answer. "
        "For complex or specific queries not covered by a dedicated tool, "
        "use the run_sql_query tool and write a SELECT statement yourself. "
        "Never run INSERT, UPDATE, DELETE or DROP statements. "
        "\n\n"
        "IMPORTANT — sending emails: "
        "When the user wants to send or compose an gmail, you MUST always follow this flow: "
        "Step 1: call compose_email to generate the draft and show it to the user. "
        "Step 2: wait for the user to explicitly confirm (e.g. 'send it', 'yes') or request adjustments. "
        "Step 3: ask the user to type their confirmation keyword. "
        "Step 4: only after the user provides the keyword, call send_email_tool passing the keyword they typed. "
        "NEVER skip steps. NEVER call send_email_tool without first asking for the confirmation keyword. "
        "If the user asks for changes, call compose_email again with the updated content and show the new draft."
        "\n\n"
        "CALENDAR — You also manage the user's Google Calendar (primary personal account). "
        "The user has multiple calendars. Use tool_list_calendars to discover them. "
        "Events have the following fields: id, calendar_id, calendar_name, summary (title), description, location, "
        "start (ISO 8601 datetime or date), end (ISO 8601 datetime or date), "
        "is_all_day (bool), attendees (list of emails), status, html_link. "
        "All datetimes are in ISO 8601 format. For timed events use 'YYYY-MM-DDTHH:MM:SS+HH:MM'. "
        "For all-day events use 'YYYY-MM-DD'. Always infer the user's timezone from context or ask if unclear. "
        "Read tools (get_upcoming, get_by_date, search) query ALL calendars by default. "
        "For create/update/delete, the calendar_id field from the event or list result tells you which calendar to target. "
        "\n\n"
        "IMPORTANT — creating calendar events: "
        "When the user wants to create an event, always follow this flow: "
        "Step 1: call compose_calendar_event to show a draft to the user. "
        "Step 2: wait for the user to confirm or request adjustments. "
        "Step 3: only after confirmation, call create_calendar_event to actually create it. "
        "\n\n"
        "IMPORTANT — deleting calendar events: "
        "Deletion is irreversible. Always ask the user to type their confirmation keyword before deleting. "
        "Only after they provide it, call delete_calendar_event passing the keyword they typed. "
        "NEVER delete an event without first asking for the confirmation keyword. "
        "\n\n"
        "For updates: show the user what will change before calling update_calendar_event."
    )
)




def llm(prompt: str, history=None) -> tuple[str, list]:
    result = asyncio.run(agent.run(prompt, message_history=_clean_history(history or [])))

    # Print tool calls and returns to the console for debugging
    for message in result.all_messages():
        for part in message.parts:
            if isinstance(part, ToolCallPart):
                print(f"[tool call]   {part.tool_name}  args={part.args}")
            elif isinstance(part, ToolReturnPart):
                print(f"[tool return] {part.tool_name}  → {str(part.content)[:120]}")

    return result.output, result.new_messages()

# ── Calendar tools ────────────────────────────────────────────────────────────

@agent.tool_plain
def tool_list_calendars() -> str:
    """List all calendars on the user's Google account with their id, name, and access_role.
    For creating or updating events, only use calendars where access_role is 'owner' or 'writer'.
    Calendars with access_role 'reader' or 'freeBusyReader' are read-only."""
    calendars = list_calendars()
    if not calendars:
        return "No calendars found."
    return str(calendars)


@agent.tool_plain
def tool_get_upcoming_events(days: int = 7) -> str:
    """Get upcoming events across ALL calendars for the next N days (default 7). Each event includes calendar_name and calendar_id."""
    events = get_upcoming_events(days)
    if not events:
        return f"No events in the next {days} days."
    return str(events)


@agent.tool_plain
def tool_get_events_by_date(date: str) -> str:
    """Get all events across ALL calendars on a specific date. Date format: YYYY-MM-DD"""
    events = get_events_by_date(date)
    if not events:
        return f"No events found on {date}."
    return str(events)


@agent.tool_plain
def tool_search_events(keyword: str) -> str:
    """Search across ALL calendars for events matching a keyword in title or description."""
    events = search_events(keyword)
    if not events:
        return f"No events found matching '{keyword}'."
    return str(events)


@agent.tool_plain
def tool_get_event_by_id(event_id: str, calendar_id: str = "primary") -> str:
    """Get full details of a specific calendar event by its ID. Use the calendar_id from the event's listing result."""
    event = get_event_by_id(event_id, calendar_id)
    return str(event) if event else "Event not found."


@agent.tool_plain
def compose_calendar_event(
    summary: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    attendees: str = "",
    reminder_minutes: int = 0,
) -> str:
    """
    Show a draft calendar event to the user for review.
    Always call this before create_calendar_event.
    attendees: comma-separated gmail addresses, or empty string if none.
    start/end: ISO 8601 datetime ('2026-03-25T14:00:00+05:00') or date ('2026-03-25') for all-day.
    reminder_minutes: minutes before the event to show a popup notification. 0 means no reminder.
    """
    attendee_display = attendees if attendees else "None"
    reminder_display = f"{reminder_minutes} minutes before" if reminder_minutes else "None"
    return (
        f"📅 Calendar event draft:\n\n"
        f"  Title:       {summary}\n"
        f"  Start:       {start}\n"
        f"  End:         {end}\n"
        f"  Location:    {location or 'None'}\n"
        f"  Description: {description or 'None'}\n"
        f"  Attendees:   {attendee_display}\n"
        f"  Reminder:    {reminder_display}\n\n"
        f"Reply with 'create it' to confirm, or describe what you'd like to adjust."
    )


@agent.tool_plain
def create_calendar_event(
    summary: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    attendees: str = "",
    calendar_id: str = "primary",
    reminder_minutes: int = 0,
) -> str:
    """
    Create a calendar event. Only call after the user confirmed the draft from compose_calendar_event.
    calendar_id: the 'id' field from tool_list_calendars — NOT the calendar name. Defaults to primary.
    attendees: comma-separated gmail addresses, or empty string if none.
    start/end: ISO 8601 datetime or date string.
    reminder_minutes: minutes before the event for a popup notification. 0 means no reminder.
    """
    attendee_list = [a.strip() for a in attendees.split(",") if a.strip()] if attendees else None
    event = create_event(
        summary=summary,
        start=start,
        end=end,
        description=description,
        location=location,
        attendees=attendee_list,
        calendar_id=calendar_id,
        reminder_minutes=reminder_minutes if reminder_minutes else None,
    )
    return (
        f"✅ Event created!\n\n"
        f"  Title:    {event['summary']}\n"
        f"  Calendar: {event['calendar_name'] or calendar_id}\n"
        f"  Start:    {event['start']}\n"
        f"  End:      {event['end']}\n"
        f"  Link:     {event['html_link']}"
    )


@agent.tool_plain
def update_calendar_event(
    event_id: str,
    calendar_id: str = "primary",
    summary: str = "",
    start: str = "",
    end: str = "",
    description: str = "",
    location: str = "",
    reminder_minutes: int = -1,
) -> str:
    """
    Update an existing calendar event. Only pass the fields that should change.
    event_id: from the event's listing result.
    calendar_id: the 'id' field from the event's listing result — NOT the calendar name.
    start/end if provided: ISO 8601 datetime or date string.
    reminder_minutes: set a new popup reminder (minutes before event). -1 means leave unchanged.
    """
    kwargs = {}
    if summary:
        kwargs["summary"] = summary
    if start:
        kwargs["start"] = start
    if end:
        kwargs["end"] = end
    if description:
        kwargs["description"] = description
    if location:
        kwargs["location"] = location
    if reminder_minutes >= 0:
        kwargs["reminder_minutes"] = reminder_minutes

    if not kwargs:
        return "No fields provided to update."

    event = update_event(event_id, calendar_id=calendar_id, **kwargs)
    return f"✅ Event updated.\n\n  Title: {event['summary']}\n  Start: {event['start']}\n  End: {event['end']}"


@agent.tool_plain
def delete_calendar_event(event_id: str, calendar_id: str, summary: str, confirmation_keyword: str) -> str:
    """
    Permanently delete a calendar event after the user confirmed and typed their confirmation keyword.
    event_id and calendar_id: both required — use values from the event's listing result.
    summary: the event title, shown back to the user.
    confirmation_keyword: exactly what the user typed in the chat.
    """
    expected = os.getenv("SEND_CONFIRMATION_CODE", "")
    if confirmation_keyword.strip() != expected:
        return "❌ Wrong confirmation keyword. Event was NOT deleted."
    success = delete_event(event_id, calendar_id=calendar_id)
    if success:
        return f"✅ Event '{summary}' deleted."
    return "❌ Failed to delete event. Calendar API error."


# ── Web search ─────────────────────────────────────────────────────────────────

@agent.tool_plain
def tool_search_web(query: str, max_results: int = 5) -> str:
    """Search the internet using DuckDuckGo. Use this for current events, facts, or anything not in the local database."""
    results = web_search(query, max_results=max_results)
    if not results:
        return "No results found."
    return str(results)
