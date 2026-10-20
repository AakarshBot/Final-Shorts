import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


TOKEN_PATH = Path("token.json")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.readonly",
]


old_token = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))

client_id = old_token.get("client_id")
client_secret = old_token.get("client_secret")

if not client_id or not client_secret:
    raise RuntimeError(
        "The existing token.json does not contain the OAuth client details."
    )

client_config = {
    "installed": {
        "client_id": client_id,
        "client_secret": client_secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

flow = InstalledAppFlow.from_client_config(
    client_config,
    SCOPES,
)

credentials = flow.run_local_server(
    port=0,
    access_type="offline",
    prompt="consent",
)

TOKEN_PATH.write_text(
    credentials.to_json(),
    encoding="utf-8",
)

print("New token.json created successfully.")