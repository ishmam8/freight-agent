import base64
from pathlib import Path
import os
from email.message import EmailMessage
from typing import Optional, Dict, Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]

BASE_DIR = Path(__file__).resolve().parents[3]
CREDENTIALS_PATH = BASE_DIR / "app" / "config" / "client_secret_credentials.json"
TOKEN_PATH = BASE_DIR / "app" / "config" / "token.json"


def get_gmail_service():
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def build_raw_message(
    to_email: str,
    subject: str,
    body: str,
    from_email: Optional[str] = None,
) -> str:
    message = EmailMessage()
    message["To"] = to_email
    message["Subject"] = subject

    if from_email:
        message["From"] = from_email

    message.set_content(body)

    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    return encoded


def create_gmail_draft(
    to_email: str,
    subject: str,
    body: str,
    from_email: Optional[str] = None,
) -> Dict[str, Any]:
    service = get_gmail_service()
    raw_message = build_raw_message(
        to_email=to_email,
        subject=subject,
        body=body,
        from_email=from_email,
    )

    draft_body = {
        "message": {
            "raw": raw_message
        }
    }

    draft = service.users().drafts().create(userId="me", body=draft_body).execute()
    return draft