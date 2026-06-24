from sqlmodel import Session, select, col
from sqlalchemy import Engine
from data.models import Gmail
from typing import Optional


def _email_to_dict(email: Gmail) -> dict:
    return {
        "id": email.id,
        "account": email.account,
        "thread_id": email.thread_id,
        "subject": email.subject,
        "sender_name": email.sender_name,
        "sender_email": email.sender_email,
        "to_email": email.to_email,
        "date": email.date,
        "internal_date": email.internal_date,
        "labels": email.labels,
        "snippet": email.snippet,
        "body": email.body,
        "mime_type": email.mime_type,
        "is_read": email.is_read,
    }


def _email_to_slim_dict(email: Gmail) -> dict:
    return {
        "id": email.id,
        "thread_id": email.thread_id,
        "subject": email.subject,
        "sender_name": email.sender_name,
        "sender_email": email.sender_email,
        "to_email": email.to_email,
        "date": email.date,
        "labels": email.labels,
        "snippet": email.snippet,
        "is_read": email.is_read,
    }


def get_recent_emails(engine: Engine, limit: int = 10) -> list[dict]:
    with Session(engine) as session:
        statement = select(Gmail).order_by(col(Gmail.internal_date).desc()).limit(limit)
        results = session.exec(statement).all()
        return [_email_to_slim_dict(e) for e in results]


def get_unread_emails(engine: Engine, limit: int = 20) -> list[dict]:
    with Session(engine) as session:
        statement = (
            select(Gmail)
            .where(Gmail.is_read == False)
            .order_by(col(Gmail.internal_date).desc())
            .limit(limit)
        )
        results = session.exec(statement).all()
        return [_email_to_slim_dict(e) for e in results]


def search_emails_by_sender(engine: Engine, sender: str, limit: int = 20) -> list[dict]:
    with Session(engine) as session:
        statement = (
            select(Gmail)
            .where(
                (Gmail.sender_email.ilike(f"%{sender}%")) |
                (Gmail.sender_name.ilike(f"%{sender}%"))
            )
            .order_by(col(Gmail.internal_date).desc())
            .limit(limit)
        )
        results = session.exec(statement).all()
        return [_email_to_slim_dict(e) for e in results]


def search_emails_by_subject(engine: Engine, keyword: str, limit: int = 20) -> list[dict]:
    with Session(engine) as session:
        statement = (
            select(Gmail)
            .where(Gmail.subject.ilike(f"%{keyword}%"))
            .order_by(col(Gmail.internal_date).desc())
            .limit(limit)
        )
        results = session.exec(statement).all()
        return [_email_to_slim_dict(e) for e in results]


def search_emails_by_body(engine: Engine, keyword: str, limit: int = 20) -> list[dict]:
    with Session(engine) as session:
        statement = (
            select(Gmail)
            .where(Gmail.body.ilike(f"%{keyword}%"))
            .order_by(col(Gmail.internal_date).desc())
            .limit(limit)
        )
        results = session.exec(statement).all()
        return [_email_to_slim_dict(e) for e in results]


def get_emails_by_label(engine: Engine, label: str, limit: int = 20) -> list[dict]:
    with Session(engine) as session:
        statement = (
            select(Gmail)
            .where(Gmail.labels.ilike(f"%{label}%"))
            .order_by(col(Gmail.internal_date).desc())
            .limit(limit)
        )
        results = session.exec(statement).all()
        return [_email_to_slim_dict(e) for e in results]


def get_email_by_id(engine: Engine, email_id: str) -> Optional[dict]:
    with Session(engine) as session:
        email = session.get(Gmail, email_id)
        return _email_to_dict(email) if email else None


def get_emails_by_thread(engine: Engine, thread_id: str) -> list[dict]:
    with Session(engine) as session:
        statement = (
            select(Gmail)
            .where(Gmail.thread_id == thread_id)
            .order_by(col(Gmail.internal_date).asc())
        )
        results = session.exec(statement).all()
        return [_email_to_dict(e) for e in results]


def count_emails(engine: Engine, unread_only: bool = False) -> int:
    with Session(engine) as session:
        statement = select(Gmail)
        if unread_only:
            statement = statement.where(Gmail.is_read == False)
        results = session.exec(statement).all()
        return len(results)
