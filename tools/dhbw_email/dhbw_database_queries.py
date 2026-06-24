import sqlite3
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve()
while not (ROOT / "pyproject.toml").exists():
    ROOT = ROOT.parent

DHBW_DB_PATH = ROOT / "data" / "emails_dhbw_account.db"


def run_sql_query(sql: str) -> list[dict]:
    """Execute a SELECT query against the DHBW email database. Returns rows as dicts."""
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed.")
    conn = sqlite3.connect(DHBW_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(sql)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_email_by_id(message_id: str) -> Optional[dict]:
    """Fetch a single email with full body by its message_id."""
    conn = sqlite3.connect(DHBW_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT * FROM dhbwemail WHERE message_id = ?", (message_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_email_attachments(message_id: str) -> list[dict]:
    """List all attachments for an email. Returns filename, mime_type and size for each."""
    conn = sqlite3.connect(DHBW_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT filename, mime_type, size FROM dhbwattachment WHERE message_id = ?",
            (message_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def read_attachment(message_id: str, filename: str) -> Optional[str]:
    """Read the extracted text content of a specific attachment by filename."""
    conn = sqlite3.connect(DHBW_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT extracted_text FROM dhbwattachment WHERE message_id = ? AND filename = ?",
            (message_id, filename)
        )
        row = cursor.fetchone()
        return row["extracted_text"] if row else None
    finally:
        conn.close()
