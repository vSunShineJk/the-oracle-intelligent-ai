import time
import os
from pydantic_ai import RunContext

from brain.utilities.azure_client import azure_agent
from brain.utilities.system_prompts import build_oracle_prompt
from quality_check.latency_check import trace

# DATA
from sqlmodel import Session, text
from data.database import get_engine

# MEMORY
from memories.memory_manager import read_memory, append_memory

# TOOLS
from tools.google.config import GMAIL_ACCOUNTS
from tools.gmail.gmail_api_calls import send_email
from tools.gmail.gmail_database_queries import (
    get_email_by_id as gmail_get_email_by_id,
)
from tools.dhbw_email.dhbw_database_queries import (
    run_sql_query as dhbw_run_sql_query,
    read_attachment as dhbw_read_attachment,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

oracle = azure_agent()

def _get_account(account: str):
    for acc in GMAIL_ACCOUNTS:
        if acc.name == account:
            return acc
    raise ValueError(f"Unknown account: '{account}'.")

def _get_engine(account: str):
    db_path = os.path.join(BASE_DIR, "data", f"emails_{account}_account.db")
    return get_engine(db_path)

@oracle.system_prompt
def oracle_dynamic_prompt() -> str:
    return build_oracle_prompt()


@oracle.tool
def compose_email(ctx: RunContext, account: str, to: str, subject: str, body: str) -> str:
    """
    Compose a draft email and show it to the user for review.
    Always call this first before sending. Never send without user confirmation.
    """
    user_account = _get_account(account)
    return (
        f"📧 Draft ready for your review:\n\n"
        f"  From:    {user_account.email}\n"
        f"  To:      {to}\n"
        f"  Subject: {subject}\n"
        f"  Body:\n\n{body}\n\n"
        f"Reply with 'send it' to confirm, or describe what you'd like to adjust."
    )


@oracle.tool
def send_email_tool(ctx: RunContext, account: str, to: str, subject: str, body: str, confirmation_keyword: str) -> str:
    """
    Send an email after the user has confirmed the draft and typed their confirmation keyword.
    Only call this after compose_email was shown and the user confirmed.
    confirmation_keyword: exactly what the user typed in the chat.
    account: 'primary' or 'secondary' — must match a Gmail account name.
    """
    expected = os.getenv("SEND_CONFIRMATION_CODE", "")
    if confirmation_keyword.strip() != expected:
        return "Wrong confirmation keyword. Email was NOT sent."
    user_account = _get_account(account)
    success = send_email(token_path=user_account.token_path, to=to, subject=subject, body=body)
    if success:
        return f"Email sent from {user_account.email} to {to}."
    return "Failed to send email. Gmail API error."


@oracle.tool
def tool_get_email_by_id(ctx: RunContext, account: str, email_id: str) -> str:
    """
    Fetch the full body and details of a single Gmail email by its ID.
    Gmail only — not for DHBW emails.
    account: 'primary' or 'secondary'
    email_id: the 'id' column from a previous run_sql_query result.
    """
    t = time.perf_counter()
    result = gmail_get_email_by_id(_get_engine(account), email_id)
    trace(f"  ✓ tool_get_email_by_id  {(time.perf_counter()-t)*1000:.0f}ms")
    return str(result) if result else "Email not found."


@oracle.tool
def run_sql_query(ctx: RunContext, account: str, query: str) -> str:
    """
    Execute a raw read-only SQL SELECT statement against the active account's email database.
    The table is called 'gmail'. Only SELECT statements are allowed.
    Example: SELECT sender_email, COUNT(*) as total FROM gmail GROUP BY sender_email ORDER BY total DESC LIMIT 10
    account: 'primary' or 'secondary' — never use this for DHBW/university email.
    """
    q = query.strip().lower()
    if not q.startswith("select"):
        return "Error: only SELECT statements are allowed."
    for forbidden in ["drop", "delete", "insert", "update", "alter", "create"]:
        if forbidden in q:
            return f"Error: '{forbidden}' is not allowed."

    t = time.perf_counter()
    try:
        with Session(_get_engine(account)) as session:
            results = session.exec(text(query)).all()
            if not results:
                trace(f"  ✓ run_sql_query  {(time.perf_counter()-t)*1000:.0f}ms")
                return "No results found."
            rows = [dict(row._mapping) for row in results]
            trace(f"  ✓ run_sql_query  {(time.perf_counter()-t)*1000:.0f}ms")
            return str(rows)
    except Exception as e:
        return f"Query error: {e}"


@oracle.tool
def query_dhbw_email_db(ctx: RunContext, sql: str) -> list[dict]:
    """
    Execute a SELECT query against the DHBW university email database.
    Table name: 'dhbwemail' — NOT 'gmail'. Never use 'gmail' here.
    Columns: message_id, subject, sender, receiver, date, internal_date, body, in_reply_to
    Attachments table: 'dhbwattachment' — columns: id, message_id, filename, mime_type, size, extracted_text
    Example: SELECT subject, sender FROM dhbwemail ORDER BY internal_date DESC LIMIT 5
    """
    t = time.perf_counter()
    result = dhbw_run_sql_query(sql)
    trace(f"  ✓ query_dhbw_email_db  {(time.perf_counter()-t)*1000:.0f}ms")
    return result


@oracle.tool
def read_attachment(ctx: RunContext, message_id: str, filename: str) -> str:
    """
    Read the extracted text of a DHBW university email attachment.
    Only works for DHBW emails — not Gmail.
    message_id: the message_id column from dhbwemail (fetch it with query_dhbw_email_db first)
    filename: the filename column from dhbwattachment
    """

    t = time.perf_counter()
    result = dhbw_read_attachment(message_id, filename)
    trace(f"  ✓ read_attachment  {(time.perf_counter() - t) * 1000:.0f}ms")
    return result if result else "[No extracted text available for this attachment]"


# MEMERY TOOLS
@oracle.tool
def save_fact(ctx: RunContext, fact: str) -> str:
    """
    Save a fact you learned about the user to long-term memory.
    Use this when the user reveals something worth remembering across sessions.
    fact: a short, plain-English sentence. Example: 'User has an exam on 2026-05-28.'
    """
    import datetime
    entry = f"- [{datetime.datetime.now().strftime('%Y-%m-%d')}] {fact}"
    append_memory("facts.md", entry)
    return "Fact saved."


@oracle.tool
def read_sessions(ctx: RunContext) -> str:
    """
    Read the history of past sessions. Use when the user asks what you discussed before
    or how long you have been working together.
    """
    return read_memory("sessions.md")