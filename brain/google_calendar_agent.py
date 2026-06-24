import asyncio

from brain.utilities.azure_client import azure_agent
from brain.utilities.system_prompts import google_calendar_agent_system_prompt

from tools.gcalendar.gcalendar_api_calls import (
    list_calendars,
    get_upcoming_events,
    get_events_by_date,
    get_event_by_id,
    search_events,
    create_event,
    update_event,
    delete_event
)

google_calendar_agent = azure_agent(google_calendar_agent_system_prompt)

def run_gcalendar(task: str) -> str:
    result = asyncio.run(google_calendar_agent.run(task))
    return result.output

  # ┌──────────────────────────────────┬─────────────────────────────────────────────┐
  # │              Tool                │                What it does                 │
  # ├──────────────────────────────────┼─────────────────────────────────────────────┤
  # │ tool_list_calendars              │ List all calendars the user has access to   │
  # ├──────────────────────────────────┼─────────────────────────────────────────────┤
  # │ tool_get_upcoming_events         │ Events in the next N days (default 7)       │
  # ├──────────────────────────────────┼─────────────────────────────────────────────┤
  # │ tool_get_events_by_date          │ All events on a specific date               │
  # ├──────────────────────────────────┼─────────────────────────────────────────────┤
  # │ tool_search_events               │ Search events by keyword                    │
  # ├──────────────────────────────────┼─────────────────────────────────────────────┤
  # │ tool_get_event_by_id             │ Full details of one event                   │
  # ├──────────────────────────────────┼─────────────────────────────────────────────┤
  # │ compose_event                    │ Show a draft event to the user for review   │
  # ├──────────────────────────────────┼─────────────────────────────────────────────┤
  # │ tool_create_event                │ Actually create after user confirms         │
  # ├──────────────────────────────────┼─────────────────────────────────────────────┤
  # │ compose_event_update             │ Show proposed changes to the user           │
  # ├──────────────────────────────────┼─────────────────────────────────────────────┤
  # │ tool_update_event                │ Actually update after user confirms         │
  # ├──────────────────────────────────┼─────────────────────────────────────────────┤
  # │ tool_delete_event                │ Delete after user provides keyword          │
  # └──────────────────────────────────┴─────────────────────────────────────────────┘


@google_calendar_agent.tool_plain
def tool_list_calendars() -> str:
    """List all calendars the user has access to."""
    return str(list_calendars())


@google_calendar_agent.tool_plain
def tool_get_upcoming_events(days: int = 7) -> str:
    """
        Fetch events from now through the next `days` days.
        If calendar_id is None, queries ALL calendars and merges results.
    """
    return str(get_upcoming_events(days))


@google_calendar_agent.tool_plain
def tool_get_events_by_date(date: str, calendar_id: str = None) -> str:
    """
        Fetch all events on a specific date. date_str format: YYYY-MM-DD
        If calendar_id is None, queries ALL calendars.
    """
    return str(get_events_by_date(date, calendar_id))


@google_calendar_agent.tool_plain
def tool_search_events(keyword: str, max_results: int = 20, calendar_id: str = None) -> str:
    """
        Search events by keyword in title or description.
        If calendar_id is None, queries ALL calendars.
    """
    return str(search_events(keyword, max_results, calendar_id))


@google_calendar_agent.tool_plain
def tool_get_event_by_id(event_id: str, calendar_id: str = None) -> str:
    """Fetch full details of a single event. calendar_id must match the event's calendar."""
    return str(get_event_by_id(event_id, calendar_id))

# --------> Safety rules need to be applied to use these tools. <--------
# @google_calendar_agent.tool_plain
# def tool_create_event(
#     summary: str,
#     start: str,
#     end: str,
#     description: str = "",
#     location: str = "",
#     attendees: list[str] | None = None,
#     calendar_id: str = "primary",
#     reminder_minutes: int | None = None,
# ) -> str:
#     """
#         Create a calendar event on the specified calendar (default: primary).
#         start/end: ISO 8601 datetime e.g. '2026-03-25T14:00:00+05:00'
#                    or date-only for all-day events: '2026-03-25'
#         reminder_minutes: minutes before the event to show a popup notification, or None for calendar default.
#     """
#     return str(create_event(summary, start, end, description, location, attendees, calendar_id, reminder_minutes))
#
#
# @google_calendar_agent.tool_plain
# def tool_update_event(
#     event_id: str, calendar_id: str = "primary"
# ) -> str:
#     """
#         Patch an existing event. Pass only the fields to change.
#         calendar_id must match the event's calendar (from calendar_id field in list results).
#         Accepts optional reminder_minutes kwarg to set a popup notification.
#     """
#     return str(update_event(event_id,calendar_id))
#
#
# @google_calendar_agent.tool_plain
# def tool_delete_event(event_id: str, calendar_id: str = "primary") -> str:
#     """Permanently delete a calendar event by ID."""
#     return str(delete_event(event_id, calendar_id))