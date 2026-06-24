from sqlmodel import SQLModel, Field
from typing import Optional

class DHBWEmail(SQLModel, table=True):
    message_id: str = Field(primary_key=True)
    subject: Optional[str] = None
    sender: Optional[str] = None
    receiver: Optional[str] = None
    date: str
    body: Optional[str] = None
    in_reply_to: Optional[str] = None
    internal_date: Optional[int] = None


class DHBWAttachment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    message_id: str = Field(foreign_key="dhbwemail.message_id")
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    size: Optional[int] = None
    raw_bytes: Optional[bytes] = None
    extracted_text: Optional[str] = None


class Gmail(SQLModel, table=True):
    id:str = Field(primary_key=True)
    account:str
    thread_id:str
    subject:Optional[str]=None
    sender_name:Optional[str]=None
    sender_email:Optional[str]=None
    to_email:Optional[str]=None
    date:Optional[str]=None
    internal_date:Optional[int]=None
    labels:Optional[str]=None
    snippet:Optional[str]=None
    body:Optional[str]=None
    mime_type:Optional[str]=None
    is_read:bool = True