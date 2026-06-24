import os
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import SQLModel, create_engine, Session, select, col
from email.utils import parsedate_to_datetime

from data.models import Gmail, DHBWEmail, DHBWAttachment
from tools.gmail.gmail_api_calls import fetch_new_emails
from tools.dhbw_email.dhbw_email_api_calls import fetch_new_dhbw_emails
from skills.extractor.extractor import extract_text

ROOT = Path(__file__).resolve()
while not (ROOT / "pyproject.toml").exists():
    ROOT = ROOT.parent

DATA_DIR = ROOT / "data"
DHBW_EMAIL_DB_PATH = DATA_DIR / "emails_dhbw_account.db"

def get_engine(db_path: str) -> Engine:
    print(f"[get_engine] connecting to DB at {db_path}")

    return create_engine(f"sqlite:///{db_path}")

def _create_db(db_path, model):
    print(f"[_create_db] creating new DB at {db_path}")

    eng = get_engine(db_path)
    SQLModel.metadata.create_all(eng, tables=[model.__table__])

def sync_gmails(db_path: str, token_path: str, account_name: str) -> int:
    print(f"[sync_gmails] starting Gmail sync for {account_name} at {db_path}")

    if not os.path.exists(db_path):
        print(f"[sync_gmails] DB not found at {db_path}, creating new one...")
        _create_db(db_path, Gmail)

    engine = get_engine(db_path)

    # Find the most recent email already saved in the database.
    # internal_date is a Unix timestamp in milliseconds — the highest number = the newest email.
    # If the DB is empty, this returns None and we fetch everything.
    with Session(engine) as session:
        latest_date = session.exec(
            select(Gmail.internal_date).order_by(col(Gmail.internal_date).desc()).limit(1)
        ).first()

    if latest_date:
        print(f"[sync_gmails] most recent email in DB: timestamp {latest_date} — fetching only newer ones")
    else:
        print("[sync_gmails] DB is empty — will fetch all emails")

    emails = fetch_new_emails(token_path, latest_date)

    # Gmail's after: filter rounds to the day, so it may return emails already in the DB.
    # Check each returned ID against the DB and skip ones we already have.
    with Session(engine) as session:
        truly_new = []
        for e in emails:
            if session.get(Gmail, e["id"]):
                print(f"[sync_gmails] skipping duplicate: {e['id']} — {e['subject']}")
            else:
                truly_new.append(e)
        emails = truly_new

    if not emails:
        print("[sync_gmails] already up to date, nothing new.")
        return 0

    with Session(engine) as session:
        for email in emails:
            record = Gmail(
                id=email["id"],
                account=account_name,
                thread_id=email["thread_id"],
                subject=email["subject"],
                sender_name=email["from"].split("<")[0].strip(),
                sender_email=email["from"].split("<")[-1].replace(">", "").strip(),
                to_email=email["to"],
                date=email["date"],
                internal_date=email["internal_date"],
                labels=",".join(email["labels"]),
                snippet=email["snippet"],
                body=email["body"],
                mime_type=email["mime_type"],
                is_read=email["is_read"],
            )
            session.merge(record)
        session.commit()

    new_emails_count = len(emails)
    print(f"[sync_gmails] saved {new_emails_count} new emails to DB.")

    return new_emails_count

def sync_dhbw_emails() -> int:
    print("[sync_dhbw_emails] start...")

    if not os.path.exists(DHBW_EMAIL_DB_PATH):
        print("[sync_dhbw_emails] DB not found, creating...")
        eng = get_engine(DHBW_EMAIL_DB_PATH)
        SQLModel.metadata.create_all(eng, tables=[DHBWEmail.__table__, DHBWAttachment.__table__])

    engine = get_engine(DHBW_EMAIL_DB_PATH)
    SQLModel.metadata.create_all(engine, tables=[DHBWAttachment.__table__])

    # Find the latest email date already in the DB.
    # date is stored as a plain string so we can't sort in SQL — we parse them all in Python.
    with Session(engine) as session:
        date_strings = session.exec(select(DHBWEmail.date)).all()

    latest_dt = None
    for date_str in date_strings:
        try:
            dt = parsedate_to_datetime(date_str)
            if latest_dt is None or dt > latest_dt:
                latest_dt = dt
        except Exception:
            pass

    since_date = latest_dt.strftime("%d-%b-%Y") if latest_dt else None

    if since_date:
        print(f"[sync_dhbw_emails] most recent email in DB: {since_date} — fetching only newer ones")
    else:
        print("[sync_dhbw_emails] DB is empty — will fetch all emails")

    emails = fetch_new_dhbw_emails(since_date)

    with Session(engine) as session:
        truly_new = []
        for e in emails:
            if session.get(DHBWEmail, e["message_id"]):
                print(f"[sync_dhbw_emails] skipping duplicate: {e.get('subject', '')}")
            else:
                truly_new.append(e)
        emails = truly_new

    if not emails:
        print("[sync_dhbw_emails] already up to date, nothing new.")
        return 0

    with Session(engine) as session:
        for email in emails:
            print(f"[sync] saving: {email.get('subject', '(no subject)')}")
            record = DHBWEmail(
                message_id=email["message_id"],
                subject=email.get("subject", ""),
                sender=email.get("sender", ""),
                receiver=email.get("receiver", ""),
                date=email.get("date", ""),
                body=email.get("body", ""),
                in_reply_to=email.get("in_reply_to", ""),
                internal_date=email.get("internal_date")
            )
            session.add(record)

            for att in email.get("attachments", []):
                attachment = DHBWAttachment(
                    message_id=email["message_id"],
                    filename=att["filename"],
                    mime_type=att["mime_type"],
                    size=att["size"],
                    raw_bytes=att["raw_bytes"],
                    extracted_text=extract_text(att["filename"], att["raw_bytes"], att["mime_type"]),
                )
                session.add(attachment)

        session.commit()

    new_emails_count = len(emails)
    print(f"[sync_dhbw_emails] saved {new_emails_count} new emails to DB.")

    return new_emails_count

if __name__ == "__main__":
    sync_dhbw_emails()
