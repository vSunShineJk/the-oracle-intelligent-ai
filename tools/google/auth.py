"""
One-time OAuth authorization script.

Run this whenever you add a new scope or need to re-authorize an account:
    uv run tools/google/auth.py

A browser window will open asking you to sign in and grant permissions.
The unified token (covering all scopes in config.py) is saved to:
    tools/google/credentials/token_primary_personal.json   ← FIX: updated path (was tools/credentials/primary_personal/token.json)

You only need to re-run this when:
  - You add a new Google API scope to config.py
  - The refresh token is revoked (e.g. after changing Google account password)
"""

from google_auth_oauthlib.flow import InstalledAppFlow
from tools.google.config import (
    SCOPES,
    PRIMARY_PERSONAL_CREDENTIALS_PATH,
    PRIMARY_PERSONAL_TOKEN_PATH,
    SECONDARY_PERSONAL_CREDENTIALS_PATH,
    SECONDARY_PERSONAL_TOKEN_PATH,
    )


def authorize_google_accounts(credentials_path:str, token_path:str, scopes:str) -> None:
    print(f"Requesting authorization for scopes:\n  " + "\n  ".join(SCOPES))
    print()

    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
    creds = flow.run_local_server(port=0)

    with open(token_path, "w") as f:
        f.write(creds.to_json())

    print(f"\nToken saved to: {token_path}")
    print("Authorization complete.")

if __name__ == "__main__":
    print("Authorizing PRIMARY personal account...")
    authorize_google_accounts(PRIMARY_PERSONAL_CREDENTIALS_PATH, PRIMARY_PERSONAL_TOKEN_PATH, SCOPES)

    print("\nAuthorizing SECONDARY personal account...")
    authorize_google_accounts(SECONDARY_PERSONAL_CREDENTIALS_PATH, SECONDARY_PERSONAL_TOKEN_PATH, SCOPES)
