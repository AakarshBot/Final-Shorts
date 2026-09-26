"""Function 07: YouTube upload and public-comment handoff."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


TOKEN_PATH = Path(__file__).resolve().with_name("token.json")
YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube"
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_COMMENT_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
SPORTS_CATEGORY_ID = "17"


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def compose_description(description: str, hashtags: str | list[str]) -> str:
    base = _clean(description)
    if isinstance(hashtags, str):
        items = re.split(r"[,\s]+", hashtags.strip())
    else:
        items = [str(item).strip() for item in hashtags]

    tags = []
    for item in items:
        item = item.strip()
        if not item:
            continue
        if not item.startswith("#"):
            item = "#" + item
        if " " not in item:
            tags.append(item)

    hashtag_line = " ".join(tags)
    if base and hashtag_line:
        return f"{base}\n\n{hashtag_line}"
    return base or hashtag_line


def _load_credentials(
    token_path: str | Path = TOKEN_PATH,
    require_comments: bool = False,
) -> Credentials:
    path = Path(token_path)
    if not path.exists():
        raise RuntimeError(
            f"YouTube token not found: {path}. Place your authorized token.json in the project root."
        )

    try:
        credentials = Credentials.from_authorized_user_file(str(path))
    except (OSError, ValueError) as exc:
        raise RuntimeError("token.json is invalid or unreadable.") from exc

    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            path.write_text(credentials.to_json(), encoding="utf-8")
        except Exception as exc:
            raise RuntimeError("YouTube authentication could not be refreshed.") from exc

    if not credentials.valid:
        raise RuntimeError("YouTube token.json is not valid. Create a fresh authorized token.")

    scopes = set(credentials.scopes or ())
    if YOUTUBE_SCOPE not in scopes:
        required = YOUTUBE_COMMENT_SCOPE if require_comments else YOUTUBE_UPLOAD_SCOPE
        if required not in scopes:
            action = "upload videos and add public comments" if require_comments else "upload videos"
            raise RuntimeError(
                f"token.json does not grant permission to {action}. "
                f"Use a token authorized with {YOUTUBE_UPLOAD_SCOPE} and "
                f"{YOUTUBE_COMMENT_SCOPE} (or the full {YOUTUBE_SCOPE} scope)."
            )

    return credentials


def youtube_client(
    token_path: str | Path = TOKEN_PATH,
    require_comments: bool = False,
) -> Resource:
    credentials = _load_credentials(token_path, require_comments=require_comments)
    return build("youtube", "v3", credentials=credentials)


def upload_video(
    video_path: str | Path,
    title: str,
    description: str,
    hashtags: str | list[str],
    comment: str,
    privacy_status: str,
    *,
    youtube: Resource | None = None,
    token_path: str | Path = TOKEN_PATH,
) -> dict[str, Any]:
    privacy = _clean(privacy_status).casefold()
    if privacy not in {"public", "private"}:
        raise ValueError("Privacy must be public or private.")

    path = Path(video_path)
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError("The rendered video file is missing or empty.")

    final_title = _clean(title)
    if not final_title:
        raise ValueError("A video title is required.")
    if len(final_title) > 100:
        raise ValueError("YouTube titles can be at most 100 characters.")

    final_description = compose_description(description, hashtags)
    if len(final_description.encode("utf-8")) > 5000:
        raise ValueError("The YouTube description is too long.")

    final_comment = _clean(comment)
    if privacy == "public":
        youtube = youtube or youtube_client(token_path, require_comments=True)
    else:
        youtube = youtube or youtube_client(token_path)

    body = {
        "snippet": {
            "title": final_title,
            "description": final_description,
            "categoryId": SPORTS_CATEGORY_ID,
        },
        "status": {
            "privacyStatus": privacy,
        },
    }

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(
            str(path),
            mimetype="video/*",
            resumable=True,
        ),
    )

    response = None
    while response is None:
        _, response = request.next_chunk(num_retries=3)

    video_id = str(response.get("id") or "").strip()
    if not video_id:
        raise RuntimeError("YouTube accepted the upload request but returned no video ID.")

    actual_privacy = (
        str(response.get("status", {}).get("privacyStatus") or privacy)
        .strip()
        .casefold()
    )

    result = {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "requested_privacy": privacy,
        "privacy_status": actual_privacy,
        "comment_posted": False,
        "comment_error": "",
    }

    if privacy == "public" and actual_privacy == "public" and final_comment:
        try:
            youtube.commentThreads().insert(
                part="snippet",
                body={
                    "snippet": {
                        "channelId": response.get("snippet", {}).get("channelId"),
                        "videoId": video_id,
                        "topLevelComment": {
                            "snippet": {
                                "textOriginal": final_comment,
                            }
                        },
                    }
                },
            ).execute(num_retries=3)
            result["comment_posted"] = True
        except HttpError as exc:
            result["comment_error"] = str(exc)

    return result
