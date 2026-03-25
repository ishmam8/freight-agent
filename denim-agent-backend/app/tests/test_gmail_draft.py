import os
import base64
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
CREDENTIALS_PATH = "app/config/client_secret_credentials.json"
TOKEN_PATH = "app/config/token.json"

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

        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def create_test_draft():
    service = get_gmail_service()

    message = EmailMessage()
    message["To"] = "your-test-email@example.com"
    message["Subject"] = "Test Gmail Draft"
    message.set_content("This is a test draft created from Python.")

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    draft = service.users().drafts().create(
        userId="me",
        body={"message": {"raw": raw}},
    ).execute()

    print("Draft created:", draft["id"])


if __name__ == "__main__":
    create_test_draft()