import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP

from tools.gmail.gmail_api_calls import (
    check_connection,
    fetch_last_emails,
    gmail_search_emails,
    get_email as gmail_get_email,
    count_by_label as gmail_count_by_label,
    send_email as gmail_send_email,
)
from tools.google.config import GMAIL_ACCOUNTS

mcp = FastMCP()
token_path = Path(__file__).parent

@mcp.tool()
def test_tool() -> str:
    return "testing tool is working"

@mcp.tool()
def gmail_primary_status_check() -> str:
    """
    Check the connection status to the gmail api
    """
    connection_status = check_connection(GMAIL_ACCOUNTS[0].token_path)
    return f"connection status: {connection_status}"

@mcp.tool()
def list_recent_emails(count:int=3)->list[dict]:
    """
        fetch last 3 emails for testing
    """
    return fetch_last_emails(GMAIL_ACCOUNTS[0].token_path,count)

@mcp.tool()
def search_emails(query: str, max_results: int = 10) -> list[dict]:
    """
    Search Gmail using Gmail's native search syntax, e.g.:
    'from:someone@example.com', 'subject:invoice', 'is:unread', 'after:2026/01/01'
    returns trimmed email without a body
    """
    return gmail_search_emails(GMAIL_ACCOUNTS[0].token_path, query, max_results)

@mcp.tool()
def fetch_full_gmail(message_id: str) -> dict:
    """
    Fetch ONE email in full, including its body, by its id.
    Get the id from list_recent_emails or search_emails results first.
    """
    result = gmail_get_email(GMAIL_ACCOUNTS[0].token_path, message_id)
    return result if result else {"error": "Email not found."}

@mcp.tool()
def count_unread(label: str = "UNREAD") -> dict:
    """
    Fast count of messages for a Gmail label — no pagination, instant.
    label: 'UNREAD' (default), 'INBOX', 'SENT', 'SPAM', 'TRASH', or any other Gmail label id.
    """
    return gmail_count_by_label(GMAIL_ACCOUNTS[0].token_path, label)

@mcp.tool()
def compose_email(to: str, subject: str, body: str) -> str:
    """
    Show a draft email to the user for review. Does NOT send anything.
    Always call this first. Only call send_email after the user has
    explicitly confirmed they want to send this exact draft.
    """
    return (
        f"Draft ready for review:\n\n"
        f"To: {to}\n"
        f"Subject: {subject}\n\n"
        f"{body}\n\n"
        f"Ask the user to confirm before calling send_email."
    )

@mcp.tool()
def send_email(to: str, subject: str, body: str) -> str:
    """
    Actually send an email. Only call this after compose_email showed the
    draft AND the user explicitly confirmed they want it sent.
    """
    success = gmail_send_email(GMAIL_ACCOUNTS[0].token_path, to, subject, body)
    return f"Email sent to {to}." if success else "Failed to send email — Gmail API error."

if __name__ == "__main__":
    mcp.run()