"""Function 07: YouTube upload and public-comment handoff."""

from __future__ import annotations

from pathlib import Path
from difflib import SequenceMatcher
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import tempfile
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from google.auth.exceptions import RefreshError
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
UPLOAD_HISTORY_PATH = Path(__file__).resolve().parent / "output" / "factory_upload_history.json"
ORIGINALITY_AUDIT_WINDOW = 50
ORIGINALITY_HISTORY_LIMIT = 200
CHANNEL_HISTORY_SEED_LIMIT = 50


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalise_history_url(value: Any) -> str:
    url = _clean(value)
    if not url:
        return ""
    try:
        parsed = urlsplit(url)
        if not parsed.scheme or not parsed.netloc:
            return url.rstrip("/").casefold()
        return urlunsplit((
            parsed.scheme.casefold(),
            parsed.netloc.casefold().removeprefix("www."),
            parsed.path.rstrip("/"),
            "",
            "",
        ))
    except ValueError:
        return url.rstrip("/").casefold()


def _originality_tokens(value: Any) -> list[str]:
    return re.findall(r"\w+", str(value or "").casefold(), flags=re.UNICODE)


def _originality_trigrams(tokens: list[str]) -> set[tuple[str, ...]]:
    return {
        tuple(tokens[index:index + 3])
        for index in range(max(0, len(tokens) - 2))
    }


def _perceptual_image_hash(raw: bytes | bytearray) -> str:
    """Return a dependency-free dHash that tolerates common resize/re-encode changes."""
    try:
        from io import BytesIO
        from PIL import Image

        with Image.open(BytesIO(bytes(raw))) as source:
            image = source.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(image.getdata())
    except Exception:
        return ""
    bits = []
    for y in range(8):
        row = y * 9
        for x in range(8):
            bits.append("1" if pixels[row + x] > pixels[row + x + 1] else "0")
    return "".join(bits)


def _perceptual_visual_overlap(first: list[str], second: list[str]) -> float:
    """Greedily match close 64-bit dHashes once, ignoring unreadable/legacy images."""
    left = [value for value in first if isinstance(value, str) and len(value) == 64]
    right = [value for value in second if isinstance(value, str) and len(value) == 64]
    if not left or not right:
        return 0.0
    pairs = []
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            distance = sum(bit_a != bit_b for bit_a, bit_b in zip(a, b))
            pairs.append((distance, i, j))
    used_left, used_right = set(), set()
    matches = 0
    for distance, i, j in sorted(pairs):
        if distance > 6:
            break
        if i in used_left or j in used_right:
            continue
        used_left.add(i)
        used_right.add(j)
        matches += 1
    return matches / min(len(left), len(right))


def _read_upload_history(history_path: str | Path = UPLOAD_HISTORY_PATH) -> list[dict[str, Any]]:
    try:
        payload = json.loads(Path(history_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def build_upload_originality_record(
    script: dict,
    title: str,
    *,
    source_url: str = "",
    description: str = "",
    hashtags: str | list[str] = "",
    visuals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a local comparison record from the approved story and slide visuals."""
    script = script if isinstance(script, dict) else {}
    scenes = script.get("script")
    if not isinstance(scenes, list):
        scenes = script.get("slides")
    narration = []
    for scene in scenes if isinstance(scenes, list) else []:
        if not isinstance(scene, dict):
            continue
        text = _clean(scene.get("voiceover") or scene.get("headline") or scene.get("title"))
        if text:
            narration.append(text)

    image_hashes = []
    perceptual_hashes = []
    for visual in visuals or []:
        if not isinstance(visual, dict):
            continue
        raw = visual.get("preview_bytes") or visual.get("bytes")
        if isinstance(raw, (bytes, bytearray)) and raw:
            raw_bytes = bytes(raw)
            image_hashes.append(hashlib.sha256(raw_bytes).hexdigest())
            perceptual = _perceptual_image_hash(raw_bytes)
            if perceptual:
                perceptual_hashes.append(perceptual)

    hashtag_text = " ".join(hashtags) if isinstance(hashtags, list) else str(hashtags or "")
    metadata_text = " ".join(part for part in (
        _clean(title),
        _clean(description or script.get("seo_description")),
        _clean(hashtag_text),
    ) if part)
    return {
        "title": _clean(title),
        "source_title": _clean(script.get("source_title") or script.get("headline")),
        "source_url": _normalise_history_url(source_url or script.get("source_url") or ""),
        "story_angle": _clean(script.get("story_angle") or script.get("editorial_angle")),
        "narration": " ".join(narration),
        "metadata_text": metadata_text,
        "visual_hashes": list(dict.fromkeys(image_hashes)),
        "perceptual_visual_hashes": list(dict.fromkeys(perceptual_hashes)),
        "format": _clean(script.get("schema") or script.get("desk_profile") or ""),
    }


def assess_upload_distinctiveness(
    record: dict[str, Any],
    history_path: str | Path = UPLOAD_HISTORY_PATH,
) -> dict[str, Any]:
    """Advisory repeat-content check against the factory's latest successful uploads."""
    history = _read_upload_history(history_path)
    if not history:
        return {
            "level": "baseline",
            "history_count": 0,
            "message": (
                "No prior uploads are recorded locally yet. This comparison starts with uploads "
                "made after the audit is introduced; it cannot assess older videos that are not in this history."
            ),
            "closest": None,
        }

    tokens = _originality_tokens(record.get("narration"))
    title_tokens = _originality_tokens(record.get("title"))
    angle_tokens = _originality_tokens(record.get("story_angle"))
    metadata_tokens = _originality_tokens(record.get("metadata_text") or record.get("title"))
    source_url = _normalise_history_url(record.get("source_url"))
    visual_hashes = set(record.get("visual_hashes") or [])
    trigrams = _originality_trigrams(tokens)
    closest = None

    for previous in history[-ORIGINALITY_AUDIT_WINDOW:]:
        old_tokens = _originality_tokens(previous.get("narration"))
        old_title = _originality_tokens(previous.get("title"))
        old_angle_tokens = _originality_tokens(previous.get("story_angle"))
        old_metadata_tokens = _originality_tokens(previous.get("metadata_text") or previous.get("title"))
        old_source = _normalise_history_url(previous.get("source_url"))
        old_visuals = set(previous.get("visual_hashes") or [])
        old_perceptual_visuals = list(previous.get("perceptual_visual_hashes") or [])
        old_trigrams = _originality_trigrams(old_tokens)
        narration_similarity = (
            SequenceMatcher(None, tokens, old_tokens, autojunk=False).ratio()
            if tokens and old_tokens else 0.0
        )
        title_similarity = (
            SequenceMatcher(None, title_tokens, old_title, autojunk=False).ratio()
            if title_tokens and old_title else 0.0
        )
        angle_similarity = (
            SequenceMatcher(None, angle_tokens, old_angle_tokens, autojunk=False).ratio()
            if angle_tokens and old_angle_tokens else 0.0
        )
        metadata_similarity = (
            SequenceMatcher(None, metadata_tokens, old_metadata_tokens, autojunk=False).ratio()
            if metadata_tokens and old_metadata_tokens and not old_tokens else 0.0
        )
        union = trigrams | old_trigrams
        phrase_overlap = len(trigrams & old_trigrams) / len(union) if union else 0.0
        image_overlap = (
            len(visual_hashes & old_visuals) / min(len(visual_hashes), len(old_visuals))
            if visual_hashes and old_visuals else 0.0
        )
        perceptual_image_overlap = _perceptual_visual_overlap(
            list(record.get("perceptual_visual_hashes") or []),
            old_perceptual_visuals,
        )
        same_source = bool(source_url and old_source and source_url == old_source)
        candidate = {
            "title": _clean(previous.get("title")) or "Untitled upload",
            "video_id": _clean(previous.get("video_id")),
            "url": _clean(previous.get("url")),
            "narration_similarity": round(narration_similarity, 3),
            "phrase_overlap": round(phrase_overlap, 3),
            "title_similarity": round(title_similarity, 3),
            "story_angle_similarity": round(angle_similarity, 3),
            "metadata_similarity": round(metadata_similarity, 3),
            "metadata_only_history": not bool(old_tokens),
            "visual_overlap": round(image_overlap, 3),
            "perceptual_visual_overlap": round(perceptual_image_overlap, 3),
            "same_source": same_source,
        }
        rank = max(
            narration_similarity,
            phrase_overlap * 0.92,
            metadata_similarity * 0.86,
            title_similarity * 0.78,
            angle_similarity * 0.72,
            0.70 if same_source and narration_similarity >= 0.50 else 0.0,
            0.66 if image_overlap >= 0.75 else 0.0,
            0.68 if perceptual_image_overlap >= 0.75 else 0.0,
        )
        if closest is None or rank > closest["_rank"]:
            candidate["_rank"] = rank
            closest = candidate

    if closest is None:
        return {
            "level": "ok",
            "history_count": len(history),
            "message": "No comparable narration was available in the local upload history.",
            "closest": None,
        }

    similarity = closest["narration_similarity"]
    phrase_overlap = closest["phrase_overlap"]
    image_overlap = closest["visual_overlap"]
    perceptual_image_overlap = closest["perceptual_visual_overlap"]
    same_source = closest["same_source"]
    metadata_similarity = closest["metadata_similarity"]
    title_similarity = closest["title_similarity"]
    metadata_only = closest["metadata_only_history"]
    if similarity >= 0.82 or phrase_overlap >= 0.72 or (same_source and similarity >= 0.55):
        level = "warning"
        message = (
            f"High repeat-content signal versus “{closest['title']}”: narration similarity "
            f"{similarity:.0%}, phrase overlap {phrase_overlap:.0%}. Recheck the editorial angle, "
            "evidence, commentary and viewer value before publishing."
        )
    elif (
        similarity >= 0.62 or phrase_overlap >= 0.55 or same_source
        or image_overlap >= 0.50 or perceptual_image_overlap >= 0.75
        or title_similarity >= 0.86 or angle_similarity >= 0.90
        or (metadata_only and metadata_similarity >= 0.78)
    ):
        level = "review"
        if metadata_only:
            message = (
                f"Metadata resembles “{closest['title']}” (title similarity {title_similarity:.0%}, "
                f"metadata similarity {metadata_similarity:.0%}). The older video's narration is not in the local history, "
                "so this is a metadata-only review signal, not a duplicate-content finding."
            )
        else:
            message = (
                f"Review this upload against “{closest['title']}”: title similarity {title_similarity:.0%}, "
                f"editorial-angle similarity {angle_similarity:.0%}, narration similarity {similarity:.0%}, "
                f"phrase overlap {phrase_overlap:.0%}, exact-image overlap {image_overlap:.0%}, "
                f"perceptual-image overlap {perceptual_image_overlap:.0%}. "
                "The visual check tolerates some resize/re-encode changes but is not semantic image understanding. "
                "Similar formats can be fine; the substance still needs to differ."
            )
    else:
        level = "ok"
        message = (
            f"No strong repeat-content signal against the last "
            f"{min(len(history), ORIGINALITY_AUDIT_WINDOW)} factory-uploaded videos. "
            "This local check is advisory, not a prediction of YouTube's decision."
        )

    closest.pop("_rank", None)
    return {
        "level": level,
        "history_count": len(history),
        "message": message,
        "closest": closest,
    }


def record_upload_success(
    record: dict[str, Any],
    upload_result: dict[str, Any],
    history_path: str | Path = UPLOAD_HISTORY_PATH,
) -> bool:
    """Persist a successful factory upload; history I/O never undoes a successful upload."""
    if not isinstance(upload_result, dict) or not _clean(upload_result.get("video_id")):
        return False
    path = Path(history_path)
    history = _read_upload_history(path)
    entry = dict(record or {})
    entry.update({
        "video_id": _clean(upload_result.get("video_id")),
        "url": _clean(upload_result.get("url")),
        "privacy_status": _clean(upload_result.get("privacy_status") or upload_result.get("requested_privacy")),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    })
    history = (history + [entry])[-ORIGINALITY_HISTORY_LIMIT:]
    temp_path = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(history, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_path, path)
        return True
    except OSError:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        return False



def seed_existing_channel_upload_history(
    history_path: str | Path = UPLOAD_HISTORY_PATH,
    *,
    youtube: Resource | None = None,
) -> dict[str, Any]:
    """Best-effort import of the channel's latest upload titles/descriptions; never blocks upload."""
    path = Path(history_path)
    history = _read_upload_history(path)
    if any(item.get("format") == "existing-channel-metadata" for item in history):
        return {
            "seeded_count": sum(item.get("format") == "existing-channel-metadata" for item in history),
            "message": "Existing channel upload metadata is already included in the local audit.",
        }

    if youtube is None:
        if not TOKEN_PATH.is_file():
            return {
                "seeded_count": 0,
                "message": "Existing channel history was not imported because token.json is unavailable.",
            }
        try:
            youtube = youtube_client(require_comments=False)
        except Exception as exc:
            return {
                "seeded_count": 0,
                "message": f"Existing channel history could not be loaded ({type(exc).__name__}). Local history will still work.",
            }

    try:
        channel_result = youtube.channels().list(
            part="contentDetails",
            mine=True,
            maxResults=1,
        ).execute(num_retries=1)
        channels = channel_result.get("items") or []
        if not channels:
            return {"seeded_count": 0, "message": "The authorized YouTube account did not return a channel."}
        uploads_playlist = (
            channels[0].get("contentDetails", {})
            .get("relatedPlaylists", {})
            .get("uploads")
        )
        if not uploads_playlist:
            return {"seeded_count": 0, "message": "YouTube did not return the channel's uploads playlist."}
        playlist_result = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist,
            maxResults=CHANNEL_HISTORY_SEED_LIMIT,
        ).execute(num_retries=1)
        items = playlist_result.get("items") or []
    except Exception as exc:
        return {
            "seeded_count": 0,
            "message": (
                f"Existing channel history could not be imported ({type(exc).__name__}). "
                "Upload QC and the local comparison remain available."
            ),
        }

    known_ids = {_clean(item.get("video_id")) for item in history}
    imported = []
    # YouTube lists newest first; insert oldest-to-newest so later factory uploads
    # always remain the tail that the 50-video audit examines.
    for item in reversed(items):
        snippet = item.get("snippet") or {}
        content = item.get("contentDetails") or {}
        video_id = _clean(content.get("videoId") or (snippet.get("resourceId") or {}).get("videoId"))
        title = _clean(snippet.get("title"))
        description = _clean(snippet.get("description"))
        if not video_id or video_id in known_ids or not title:
            continue
        record = {
            "title": title,
            "source_title": title,
            "source_url": "",
            "story_angle": "",
            "narration": "",
            "metadata_text": " ".join(part for part in (title, description) if part),
            "visual_hashes": [],
            "perceptual_visual_hashes": [],
            "format": "existing-channel-metadata",
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "published_at": _clean(snippet.get("publishedAt") or content.get("videoPublishedAt")),
            "uploaded_at": _clean(snippet.get("publishedAt") or content.get("videoPublishedAt")),
            "privacy_status": "channel-upload",
        }
        imported.append(record)
        known_ids.add(video_id)

    if imported:
        # Channel-seeded metadata is older than existing factory records; prepend
        # it so the last-50 audit continues to prioritise the newest factory uploads.
        combined = (imported + history)[-ORIGINALITY_HISTORY_LIMIT:]
        temp_path = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                json.dump(combined, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(temp_path, path)
        except OSError as exc:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            return {
                "seeded_count": 0,
                "message": f"Channel metadata was retrieved but could not be saved locally ({type(exc).__name__}).",
            }

    return {
        "seeded_count": len(imported),
        "message": (
            f"Imported {len(imported)} existing channel uploads for title/description comparison. "
            "Their narration and visuals were not fetched, so any match against them is only a metadata signal."
            if imported else
            "No unseen uploads were found in the channel's latest upload page."
        ),
    }


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
        except RefreshError as exc:
            detail = _clean(str(exc))
            raise RuntimeError(
                "YouTube authentication could not be refreshed. "
                "The saved refresh token is expired, revoked, or no longer valid. "
                "Re-authorize token.json with YouTube upload permission and, for public comments, "
                "YouTube comment permission, then retry the upload."
                + (f" Provider detail: {detail}" if detail else "")
            ) from exc
        except Exception as exc:
            detail = _clean(str(exc))
            raise RuntimeError(
                "YouTube authentication could not be refreshed. "
                "Check token.json and re-authorize it if necessary."
                + (f" Provider detail: {detail}" if detail else "")
            ) from exc

    if not credentials.valid:
        raise RuntimeError("YouTube token.json is not valid. Create a fresh authorized token.")

    scopes = set(credentials.scopes or ())
    if YOUTUBE_SCOPE not in scopes:
        required = {YOUTUBE_UPLOAD_SCOPE}
        if require_comments:
            required.add(YOUTUBE_COMMENT_SCOPE)
        missing = sorted(scope for scope in required if scope not in scopes)
        if missing:
            action = (
                "upload videos and add public comments"
                if require_comments
                else "upload videos"
            )
            raise RuntimeError(
                f"token.json does not grant permission to {action}. "
                f"Missing scope(s): {', '.join(missing)}. "
                f"Use a token authorized with {YOUTUBE_UPLOAD_SCOPE} and, "
                f"when posting a comment, {YOUTUBE_COMMENT_SCOPE}; "
                f"the full {YOUTUBE_SCOPE} scope also covers both."
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
    if youtube is None:
        youtube = youtube_client(
            token_path,
            require_comments=privacy == "public" and bool(final_comment),
        )

    body = {
        "snippet": {
            "title": final_title,
            "description": final_description,
            "categoryId": SPORTS_CATEGORY_ID,
        },
        "status": {
            "privacyStatus": privacy,
            "containsSyntheticMedia": True,
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
