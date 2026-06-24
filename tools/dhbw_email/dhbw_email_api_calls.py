import imaplib as imap
import smtplib as smtp
import email
import os
from html.parser import HTMLParser
from email.utils import parsedate_to_datetime

from dotenv import load_dotenv

# TODO: real-time automatic gmail synchronization to a local database with Polling each N minutes OR using IMAP IDLE

def get_server():
    print("[get_server] Connecting to DHBW email server...")
    load_dotenv()
    username = os.getenv("DHBW_USERNAME")
    password = os.getenv("DHBW_PASSWORD")

    try:
        connection = imap.IMAP4_SSL('imap.dhbw-loerrach.de')
        connection.login(username, password)
        print(f"[_get_dhbw_email_server] Successfully connected to DHBW email server with the {connection} protocol!")
        return connection
    except Exception as e:
        print(f"[_get_dhbw_email_server] Error connecting to DHBW email server: {e}")
        return None

def fetch_new_dhbw_emails(since_date: str | None = None) -> list[dict]:
    """
    Fetches DHBW emails newer than since_date.
    since_date: IMAP format 'DD-Mon-YYYY' e.g. '05-May-2026'.
    If None, fetches everything (first sync).
    """
    connection = get_server()
    connection.select("INBOX")

    if since_date:
        print(f"[dhbw] fetching emails since {since_date}...")
        status, data = connection.search(None, f"SINCE {since_date}")
    else:
        print("[dhbw] DB is empty — fetching all emails...")
        status, data = connection.search(None, "ALL")

    email_ids = data[0].split()
    print(f"[dhbw] {len(email_ids)} emails to fetch")

    emails = []
    for i, email_id in enumerate(email_ids, start=1):
        print(f"[dhbw] fetching {i}/{len(email_ids)}...")
        result, msg_data = connection.fetch(email_id, "(RFC822)")
        emails.append(_decode_email(msg_data[0][1]))

    connection.logout()
    print(f"[dhbw] done — {len(emails)} emails fetched")
    return emails

def _decode_email(raw_email):
    msg = email.message_from_bytes(raw_email)
    subject = _decode_email_header(msg["Subject"])
    sender = _decode_email_header(msg["From"])
    receiver = _decode_email_header(msg["To"])
    date = msg["Date"]
    try:
        internal_date = int(parsedate_to_datetime(date).timestamp() * 1000)
    except Exception:
        internal_date = None
    message_id = msg["Message-ID"]
    in_reply_to = msg["In-Reply-To"]

    body = _decode_body(msg)
    attachments = _decode_email_attachments(msg)

    return {
        "subject": subject,
        "sender": sender,
        "receiver": receiver,
        "date": date,
        "message_id": message_id,
        "body": body,
        "in_reply_to": in_reply_to,
        "internal_date": internal_date,
        "attachments": attachments,
    }

def _decode_email_attachments(msg):
    attachments = []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = part.get_filename()
        if filename:
            raw = part.get_payload(decode=True) or b""
            attachments.append({
                "filename": _decode_email_header(filename),
                "mime_type": part.get_content_type(),
                "raw_bytes": raw,
                "size": len(raw),
            })
    return attachments

def _decode_email_header(raw_value):
    if raw_value is None:
        return ""
    else:
        return str(email.header.make_header(email.header.decode_header(raw_value)))

class _StripHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self._text.append(data)

    def get_text(self):
        return " ".join(self._text)

def _strip_html(html: str) -> str:
    parser = _StripHTML()
    parser.feed(html)
    return parser.get_text()

def _decode_body(msg):
    if msg.is_multipart():
        # first pass — prefer plain text
        parts = []
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    parts.append(payload.decode("utf-8", errors="ignore"))

        if parts:
            return "\n".join(parts)

        # second pass — fallback to HTML if no plain text found
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    return _strip_html(payload.decode("utf-8", errors="ignore"))

        return ""
    else:
        payload = msg.get_payload(decode=True)
        if payload is None:
            return ""
        text = payload.decode("utf-8", errors="ignore")
        if msg.get_content_type() == "text/html":
            return _strip_html(text)
        return text