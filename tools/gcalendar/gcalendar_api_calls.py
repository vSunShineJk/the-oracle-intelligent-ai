from datetime import datetime, timedelta, timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from tools.google.config import SCOPES, PRIMARY_PERSONAL_TOKEN_PATH


def _get_service(token_path: str = PRIMARY_PERSONAL_TOKEN_PATH) -> object:
    print("[gcalendar_api_calls._get_service] loading tokens from file")
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if creds.expired and creds.refresh_token:
        print("[gcalendar.get_service] tokens expired, refreshing")
        creds.refresh(Request())
        open(token_path, "w").write(creds.to_json())

    return build("calendar", "v3", credentials=creds)

# !RISK! What happens if the token expires while the server is running? We should handle token refresh in each function call to be safe, but for simplicity we load once at import and assume it will be valid for the duration of the session. In a production system, you'd want a more robust token management strategy.
_server = _get_service()  # Load once at module import to reuse across calls

def list_calendars() -> list[dict]:
    """Return all calendars the user has access to."""
    service = _server
    result = service.calendarList().list().execute()
    return [
        {
            "id": cal["id"],
            "name": cal.get("summary", "(unnamed)"),
            "description": cal.get("description", ""),
            "primary": cal.get("primary", False),
            "access_role": cal.get("accessRole", ""),
        }
        for cal in result.get("items", [])
    ]


def _get_all_calendar_ids() -> list[tuple[str, str]]:
    """Return list of (calendar_id, calendar_name) for all calendars."""
    return [(cal["id"], cal["name"]) for cal in list_calendars()]


def _resolve_calendar_id(calendar_id: str) -> str:
    """
    Resolve a calendar_id that may be a display name instead of a real ID.
    If the value matches a calendar name, returns its actual ID.
    Otherwise returns the value unchanged (assumed to already be a valid ID).
    """
    for cal in list_calendars():
        if cal["name"].lower() == calendar_id.lower():
            print(f"[gcalendar] resolved calendar name '{calendar_id}' → id='{cal['id']}'")
            return cal["id"]
    return calendar_id


def _format_event(event: dict, calendar_id: str = "", calendar_name: str = "") -> dict:
    """Convert a raw Calendar API event to a clean dict."""
    start = event.get("start", {})
    end = event.get("end", {})
    return {
        "id": event.get("id"),
        "calendar_id": calendar_id,
        "calendar_name": calendar_name,
        "summary": event.get("summary", "(no title)"),
        "description": event.get("description", ""),
        "location": event.get("location", ""),
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
        "is_all_day": "date" in start and "dateTime" not in start,
        "attendees": [a.get("gmail") for a in event.get("attendees", [])],
        "status": event.get("status"),
        "html_link": event.get("htmlLink"),
    }


def get_upcoming_events(days: int = 7, calendar_id: str = None) -> list[dict]:
    """
    Fetch events from now through the next `days` days.
    If calendar_id is None, queries ALL calendars and merges results.
    """
    service = _server
    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=days)
    calendars = [(calendar_id, "")] if calendar_id else _get_all_calendar_ids()

    all_events = []
    for cal_id, cal_name in calendars:
        try:
            result = service.events().list(
                calendarId=cal_id,
                timeMin=now.isoformat(),
                timeMax=time_max.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            for e in result.get("items", []):
                all_events.append(_format_event(e, cal_id, cal_name))
        except Exception as ex:
            print(f"[gcalendar] skipping calendar '{cal_name}' ({cal_id}): {ex}")

    all_events.sort(key=lambda e: e["start"] or "")
    return all_events


def get_events_by_date(date_str: str, calendar_id: str = None) -> list[dict]:
    """
    Fetch all events on a specific date. date_str format: YYYY-MM-DD
    If calendar_id is None, queries ALL calendars.
    """
    service = _server
    date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    time_min = date
    time_max = date + timedelta(days=1)
    calendars = [(calendar_id, "")] if calendar_id else _get_all_calendar_ids()

    all_events = []
    for cal_id, cal_name in calendars:
        try:
            result = service.events().list(
                calendarId=cal_id,
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            for e in result.get("items", []):
                all_events.append(_format_event(e, cal_id, cal_name))
        except Exception as ex:
            print(f"[gcalendar] skipping calendar '{cal_name}' ({cal_id}): {ex}")

    all_events.sort(key=lambda e: e["start"] or "")
    return all_events


def search_events(keyword: str, max_results: int = 20, calendar_id: str = None) -> list[dict]:
    """
    Search events by keyword in title or description.
    If calendar_id is None, queries ALL calendars.
    """
    service = _server
    calendars = [(calendar_id, "")] if calendar_id else _get_all_calendar_ids()

    all_events = []
    for cal_id, cal_name in calendars:
        try:
            result = service.events().list(
                calendarId=cal_id,
                q=keyword,
                singleEvents=True,
                orderBy="startTime",
                maxResults=max_results,
            ).execute()
            for e in result.get("items", []):
                all_events.append(_format_event(e, cal_id, cal_name))
        except Exception as ex:
            print(f"[gcalendar] skipping calendar '{cal_name}' ({cal_id}): {ex}")

    return all_events


def get_event_by_id(event_id: str, calendar_id: str = "primary") -> dict | None:
    """Fetch full details of a single event. calendar_id must match the event's calendar."""
    service = _server
    try:
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        return _format_event(event, calendar_id)
    except Exception as e:
        print(f"[gcalendar.get_event_by_id] error: {e}")
        return None


def create_event(
    summary: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    attendees: list[str] | None = None,
    calendar_id: str = "primary",
    reminder_minutes: int | None = None,
) -> dict:
    """
    Create a calendar event on the specified calendar (default: primary).
    start/end: ISO 8601 datetime e.g. '2026-03-25T14:00:00+05:00'
               or date-only for all-day events: '2026-03-25'
    reminder_minutes: minutes before the event to show a popup notification, or None for calendar default.
    """
    service = _server
    calendar_id = _resolve_calendar_id(calendar_id)

    def _time_field(dt_str: str) -> dict:
        if "T" in dt_str:
            return {"dateTime": dt_str, "timeZone": "UTC"}
        return {"date": dt_str}

    body = {
        "summary": summary,
        "description": description,
        "location": location,
        "start": _time_field(start),
        "end": _time_field(end),
    }
    if attendees:
        body["attendees"] = [{"gmail": email} for email in attendees]
    if reminder_minutes is not None:
        body["reminders"] = {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": reminder_minutes}],
        }

    try:
        event = service.events().insert(calendarId=calendar_id, body=body).execute()
    except Exception as e:
        raise ValueError(
            f"Failed to create event on calendar '{calendar_id}': {e}. "
            "The calendar may be read-only. Use tool_list_calendars and pick one with access_role 'owner' or 'writer'."
        ) from e
    print(f"[gcalendar.create_event] created event id={event.get('id')} on calendar={calendar_id}")
    return _format_event(event, calendar_id)


def update_event(event_id: str, calendar_id: str = "primary", **kwargs) -> dict:
    """
    Patch an existing event. Pass only the fields to change.
    calendar_id must match the event's calendar (from calendar_id field in list results).
    Accepts optional reminder_minutes kwarg to set a popup notification.
    """
    service = _server
    calendar_id = _resolve_calendar_id(calendar_id)

    patch_body = {}
    if "summary" in kwargs:
        patch_body["summary"] = kwargs["summary"]
    if "description" in kwargs:
        patch_body["description"] = kwargs["description"]
    if "location" in kwargs:
        patch_body["location"] = kwargs["location"]
    if "start" in kwargs:
        s = kwargs["start"]
        patch_body["start"] = {"dateTime": s, "timeZone": "UTC"} if "T" in s else {"date": s}
    if "end" in kwargs:
        e = kwargs["end"]
        patch_body["end"] = {"dateTime": e, "timeZone": "UTC"} if "T" in e else {"date": e}
    if "reminder_minutes" in kwargs and kwargs["reminder_minutes"] is not None:
        patch_body["reminders"] = {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": kwargs["reminder_minutes"]}],
        }

    try:
        event = service.events().patch(
            calendarId=calendar_id, eventId=event_id, body=patch_body
        ).execute()
    except Exception as e:
        raise ValueError(
            f"Failed to update event '{event_id}' on calendar '{calendar_id}': {e}. "
            "The calendar may be read-only. Use tool_list_calendars and pick one with access_role 'owner' or 'writer'."
        ) from e
    print(f"[gcalendar.update_event] updated event id={event_id} on calendar={calendar_id}")
    return _format_event(event, calendar_id)


def delete_event(event_id: str, calendar_id: str = "primary") -> bool:
    """Permanently delete a calendar event by ID."""
    service = _server
    calendar_id = _resolve_calendar_id(calendar_id)
    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        print(f"[gcalendar.delete_event] deleted event id={event_id} from calendar={calendar_id}")
        return True
    except Exception as e:
        print(f"[gcalendar.delete_event] error: {e}")
        return False

if __name__ == "__main__":
    print("Testing Google Calendar API calls...")
    print("Calendars:", list_calendars())
    print("Upcoming events:", get_upcoming_events())

