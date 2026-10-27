"""Authorize a separate, read-only YouTube analytics token.

Run this from the Final-Shorts project folder. It leaves token.json (used for
uploads) untouched and writes analytics_token.json instead.
"""
from __future__ import annotations

import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = Path(__file__).resolve().parent
SOURCE_TOKEN_PATH = ROOT / "token.json"
ANALYTICS_TOKEN_PATH = ROOT / "analytics_token.json"
SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def authorize() -> Path:
    if not SOURCE_TOKEN_PATH.is_file():
        raise RuntimeError(
            "token.json was not found. Complete the factory's normal YouTube "
            "authorization setup first."
        )
    try:
        saved_token = json.loads(SOURCE_TOKEN_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("The existing token.json is invalid or unreadable.") from exc

    client_id = saved_token.get("client_id")
    client_secret = saved_token.get("client_secret")
    if not client_id or not client_secret:
        raise RuntimeError(
            "The existing token.json has no OAuth client details. "
            "Re-run the existing authorize_youtube.py setup first."
        )

    config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = InstalledAppFlow.from_client_config(config, SCOPES)
    credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    ANALYTICS_TOKEN_PATH.write_text(credentials.to_json(), encoding="utf-8")
    return ANALYTICS_TOKEN_PATH


if __name__ == "__main__":
    try:
        token_path = authorize()
    except Exception as exc:
        raise SystemExit(f"YouTube analytics authorization failed: {exc}") from exc
    print(f"Read-only analytics token saved to: {token_path}")
    print("The existing upload token.json was not changed.")
