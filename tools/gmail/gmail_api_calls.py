import base64
import socket

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from tools.google.config import SCOPES


socket.setdefaulttimeout(30)


# ═══════════════════════════════════════════════════════════════
# STEP 1 — Connect to Gmail
#
# Gmail requires an OAuth token stored in a .json file.
# This function loads it, refreshes it if expired, and returns
# a "service" object — the thing we use to make API calls.
# ═══════════════════════════════════════════════════════════════

def _get_service(token_path: str):
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def check_connection(token_path: str) -> bool:
    """Quick check: can we reach Gmail with this token?"""
    try:
        _get_service(token_path)
        return True
    except Exception as e:
        return e


# ═══════════════════════════════════════════════════════════════
# STEP 2 — Parse a raw Gmail response into a clean dict
#
# Gmail returns emails as a big nested dict with headers buried
# inside. These two helpers extract the fields we care about.
# ═══════════════════════════════════════════════════════════════

def _decode_body(payload: dict) -> str:
    """Extract the plain-text body from a Gmail message payload."""

    # Case 1: simple email — body data is right here
    if "data" in payload.get("body", {}):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")

    # Case 2: multipart email — body is in one of the "parts"
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    return ""


def _parse_email(raw: dict) -> dict:
    """Turn a raw Gmail API response into a clean flat dict."""
    headers = {h["name"]: h["value"] for h in raw["payload"]["headers"]}
    return {
        "id":            raw["id"],
        "thread_id":     raw["threadId"],
        "from":          headers.get("From", ""),
        "to":            headers.get("To", ""),
        "subject":       headers.get("Subject", ""),
        "date":          headers.get("Date", ""),
        "internal_date": int(raw.get("internalDate", 0)),
        "labels":        raw.get("labelIds", []),
        "snippet":       raw.get("snippet", ""),
        "body":          _decode_body(raw["payload"]),
        "mime_type":     raw["payload"].get("mimeType", ""),
        "is_read":       "UNREAD" not in raw.get("labelIds", []),
    }


def _parse_email_slim(raw: dict) -> dict:
    """
    Same as _parse_email but WITHOUT the full body — used for list/search
    results so we don't blow up context with full bodies for every result.
    Use _parse_email (via a "get one email" tool) when the full body is needed.
    """
    email = _parse_email(raw)
    email.pop("body", None)
    return email


# ═══════════════════════════════════════════════════════════════
# STEP 3 — Get a list of message IDs from Gmail
#
# Gmail returns IDs in pages (up to 500 per page).
# This function follows the pages until there are no more,
# collecting all matching IDs into one flat list.
#
# The `query` parameter is a Gmail search string, e.g.:
#   ""              → all emails
#   "after:1700000000" → emails received after that timestamp
# ═══════════════════════════════════════════════════════════════

def _list_message_ids(service, query: str = "") -> list[str]:
    ids = []
    response = service.users().messages().list(userId="me", q=query, maxResults=500).execute()

    while True:
        for msg in response.get("messages", []):
            ids.append(msg["id"])

        next_page = response.get("nextPageToken")
        if not next_page:
            break

        response = service.users().messages().list(
            userId="me", q=query, maxResults=500, pageToken=next_page
        ).execute()

    return ids


# ═══════════════════════════════════════════════════════════════
# STEP 4 — Fetch only NEW emails (the main sync function)
#
# `since_internal_date` is a number like 1700000000000 —
# a Unix timestamp in *milliseconds* (that's what Gmail stores).
#
# We convert it to seconds to use in the Gmail search query,
# because Gmail's `after:` filter works in seconds.
#
# If since_internal_date is None (first ever sync), we fetch
# everything — no date filter.
# ═══════════════════════════════════════════════════════════════

def fetch_new_emails(token_path: str, since_internal_date: int | None = None) -> list[dict]:
    service = _get_service(token_path)

    if since_internal_date:
        # internalDate is milliseconds → seconds. +1 skips the email we already have
        seconds = (since_internal_date // 1000) + 1
        query = f"after:{seconds}"
    else:
        query = ""

    ids = _list_message_ids(service, query)

    if not ids:
        return []

    emails = []
    for i, msg_id in enumerate(ids, start=1):
        raw = service.users().messages().get(userId="me", id=msg_id).execute()
        emails.append(_parse_email(raw))

    return emails


# ═══════════════════════════════════════════════════════════════
# QUICK PEEK — for testing, not for sync
# ═══════════════════════════════════════════════════════════════

def fetch_last_emails(token_path: str, count: int = 5) -> list[dict]:
    """Fetch the most recent N emails. Useful for quick tests."""
    service = _get_service(token_path)
    response = service.users().messages().list(userId="me", maxResults=count).execute()

    emails = []
    for msg in response.get("messages", []):
        raw = service.users().messages().get(userId="me", id=msg["id"]).execute()
        emails.append(_parse_email_slim(raw))

    return emails


# ═══════════════════════════════════════════════════════════════
# SEND AN EMAIL
# ═══════════════════════════════════════════════════════════════

def send_email(token_path: str, to: str, subject: str, body: str) -> bool:
    service = _get_service(token_path)
    message = f"To: {to}\r\nSubject: {subject}\r\n\r\n{body}"
    encoded = base64.urlsafe_b64encode(message.encode("utf-8")).decode("utf-8")
    try:
        service.users().messages().send(userId="me", body={"raw": encoded}).execute()
        return True
    except Exception as e:
        return False


def gmail_search_emails(token_path: str, query: str, max_results: int = 10) -> list[dict]:
    service = _get_service(token_path)
    response = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()

    emails = []
    for msg in response.get("messages", []):
        raw = service.users().messages().get(userId="me", id=msg["id"]).execute()
        emails.append(_parse_email_slim(raw))
    return emails


def get_email(token_path: str, message_id: str) -> dict | None:
    """Fetch ONE email in full (including body) by its id. Use after a search/list call."""
    service = _get_service(token_path)
    try:
        raw = service.users().messages().get(userId="me", id=message_id).execute()
    except Exception:
        return None
    return _parse_email(raw)


def count_by_label(token_path: str, label: str = "UNREAD") -> dict:
    """
    Fast count using Gmail's label metadata directly — no pagination needed.
    label: a Gmail label id, e.g. 'UNREAD', 'INBOX', 'SENT', 'SPAM', 'TRASH'.
    Returns {"label": ..., "messages_total": ..., "messages_unread": ...}.
    """
    service = _get_service(token_path)
    result = service.users().labels().get(userId="me", id=label).execute()
    return {
        "label": label,
        "messages_total": result.get("messagesTotal", 0),
        "messages_unread": result.get("messagesUnread", 0),
    }