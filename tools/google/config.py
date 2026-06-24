import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/calendar",
]

_CREDS_DIR = os.path.dirname(os.path.abspath(__file__))

PRIMARY_PERSONAL_CREDENTIALS_PATH = os.path.join(_CREDS_DIR, "credentials", "credentials_primary_personal.json")
PRIMARY_PERSONAL_TOKEN_PATH = os.path.join(_CREDS_DIR, "credentials", "token_primary_personal.json")

SECONDARY_PERSONAL_CREDENTIALS_PATH = os.path.join(_CREDS_DIR, "credentials", "credentials_secondary_personal.json")
SECONDARY_PERSONAL_TOKEN_PATH = os.path.join(_CREDS_DIR, "credentials", "token_secondary_personal.json")


# ── Gmail accounts ────────────────────────────────────────────────────────────
# To add a new account: add one GmailAccount line to GMAIL_ACCOUNTS. That's it.
# Email addresses are loaded from .env to avoid committing personal data.

@dataclass
class GmailAccount:
    name: str        # short label — must match "status" in semantic_memory.json
    token_path: str  # path to the OAuth token .json file
    email: str       # the actual email address

GMAIL_ACCOUNTS = [
    GmailAccount("primary",   PRIMARY_PERSONAL_TOKEN_PATH,   os.getenv("GMAIL_PRIMARY_EMAIL", "")),
    GmailAccount("secondary", SECONDARY_PERSONAL_TOKEN_PATH, os.getenv("GMAIL_SECONDARY_EMAIL", "")),
]
