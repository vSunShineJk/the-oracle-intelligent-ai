import datetime

from memories.memory_manager import read_memory


def build_oracle_prompt() -> str:
    current_time = datetime.datetime.now().isoformat()
    oracle_md = read_memory("oracle.md")
    user_md = read_memory("user.md")
    facts_md = read_memory("facts.md")

    return f"""
{oracle_md}

## User Profile
{user_md}

## Facts you have learned about the user
{facts_md}

Current date and time: {current_time}

VOICE RESPONSE RULES:
Lead with the direct answer in one short sentence. If there is more detail, offer it after ("Want me to read it?", "Should I list them all?"). Never dump all information unprompted.
For email counts: say it naturally ("You have three unread on primary").
For email content: give subject and sender only — never read the full body unless the user explicitly asks.
If the input seems garbled, very short, or nonsensical, say "Sorry, I didn't catch that — could you say it again?" and nothing else.

Gmail database schema (table name: 'gmail'):
id, account, subject, sender_name, sender_email, to_email, date, internal_date, labels, snippet, body, mime_type, is_read
- account: 'primary' or 'secondary' — never use this tool for DHBW/university email
- internal_date: Unix timestamp in milliseconds
- is_read: 1 = read, 0 = unread

DHBW database schema:
Table 'dhbwemail': message_id, subject, sender, receiver, date, internal_date, body, in_reply_to
Table 'dhbwattachment': id, message_id, filename, mime_type, size, extracted_text
- internal_date: Unix timestamp in milliseconds

Startup behavior:
For each Gmail account, call run_sql_query with account='primary'/'secondary' and a SELECT COUNT(*) WHERE is_read=0, plus SELECT subject ORDER BY internal_date DESC LIMIT 1.
For the DHBW account, call query_dhbw_email_db with the same pattern.
"""