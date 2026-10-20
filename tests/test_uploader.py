import uploader


def test_compose_description_adds_hashtags():
    result = uploader.compose_description(
        "A quick cricket update.",
        ["#Cricket", "#IndiaCricket"],
    )

    assert result == "A quick cricket update.\n\n#Cricket #IndiaCricket"


def test_compose_description_accepts_editable_text():
    result = uploader.compose_description(
        "A quick cricket update.",
        "#Cricket #IndiaCricket",
    )

    assert result.endswith("#Cricket #IndiaCricket")


def test_upload_originality_audit_starts_with_clear_baseline(tmp_path):
    record = uploader.build_upload_originality_record(
        {"script": [{"voiceover": "A specific and original sports explanation."}]},
        "A specific title",
    )

    report = uploader.assess_upload_distinctiveness(record, tmp_path / "history.json")

    assert report["level"] == "baseline"
    assert "cannot assess older videos" in report["message"]


def test_upload_originality_audit_warns_on_repeated_narration_and_source(tmp_path):
    history_path = tmp_path / "history.json"
    script = {
        "source_title": "Confirmed player fitness update",
        "story_angle": "selection consequences",
        "script": [
            {"voiceover": "Shubman Gill's fitness now affects India's next selection decision."},
            {"voiceover": "The medical review will determine whether he is available for the next ODI."},
        ],
    }
    first = uploader.build_upload_originality_record(
        script,
        "Shubman Gill fitness and India selection",
        source_url="https://example.com/cricket/story?id=1",
        visuals=[{"bytes": b"same visual bytes"}],
    )
    assert uploader.record_upload_success(
        first,
        {"video_id": "previous123", "url": "https://youtube.com/watch?v=previous123", "privacy_status": "public"},
        history_path,
    )

    second = uploader.build_upload_originality_record(
        script,
        "India selection after Gill fitness update",
        source_url="https://example.com/cricket/story?id=2",
        visuals=[{"bytes": b"same visual bytes"}],
    )
    report = uploader.assess_upload_distinctiveness(second, history_path)

    assert report["level"] == "warning"
    assert report["closest"]["video_id"] == "previous123"
    assert report["closest"]["narration_similarity"] == 1.0
    assert report["closest"]["visual_overlap"] == 1.0


def test_upload_originality_audit_does_not_flag_materially_different_story(tmp_path):
    history_path = tmp_path / "history.json"
    first = uploader.build_upload_originality_record(
        {"script": [{"voiceover": "The captain changed the field to target a specific weakness."}]},
        "The tactical switch that decided the contest",
        source_url="https://example.com/story-a",
    )
    uploader.record_upload_success(
        first,
        {"video_id": "previous456", "url": "https://youtube.com/watch?v=previous456", "privacy_status": "private"},
        history_path,
    )
    second = uploader.build_upload_originality_record(
        {"script": [{"voiceover": "A young sprinter broke the championship record with a powerful finish."}]},
        "A new championship record",
        source_url="https://example.com/story-b",
    )

    report = uploader.assess_upload_distinctiveness(second, history_path)

    assert report["level"] == "ok"
    assert "advisory" in report["message"]


def test_upload_originality_audit_reviews_metadata_only_channel_import(tmp_path):
    history_path = tmp_path / "history.json"
    existing = {
        "title": "Gill injury update and India selection decision",
        "source_title": "Gill injury update and India selection decision",
        "source_url": "",
        "story_angle": "",
        "narration": "",
        "metadata_text": "Gill injury update and India selection decision. The fitness report could decide India's next ODI selection.",
        "visual_hashes": [],
        "format": "existing-channel-metadata",
        "video_id": "old001",
        "url": "https://www.youtube.com/watch?v=old001",
    }
    assert uploader.record_upload_success(
        existing,
        {"video_id": "old001", "url": "https://www.youtube.com/watch?v=old001", "privacy_status": "public"},
        history_path,
    )

    current = uploader.build_upload_originality_record(
        {
            "source_title": "Gill injury report shapes India's ODI selection",
            "seo_description": "The fitness report could decide India's next ODI selection.",
            "script": [{"voiceover": "A completely new tactical explanation with fresh context."}],
        },
        "Gill injury update and India selection decision",
        description="The fitness report could decide India's next ODI selection.",
    )
    report = uploader.assess_upload_distinctiveness(current, history_path)

    assert report["level"] == "review"
    assert report["closest"]["metadata_only_history"] is True
    assert "metadata-only review signal" in report["message"]


def test_seed_existing_channel_upload_history_imports_latest_fifty_oldest_to_newest(tmp_path):
    history_path = tmp_path / "history.json"

    class Request:
        def __init__(self, payload):
            self.payload = payload

        def execute(self, num_retries=0):
            return self.payload

    class Channels:
        def list(self, **kwargs):
            assert kwargs["mine"] is True
            assert kwargs["maxResults"] == 1
            return Request({
                "items": [{
                    "contentDetails": {
                        "relatedPlaylists": {"uploads": "uploads123"}
                    }
                }]
            })

    class PlaylistItems:
        def list(self, **kwargs):
            assert kwargs["playlistId"] == "uploads123"
            assert kwargs["maxResults"] == 50
            return Request({
                "items": [
                    {
                        "snippet": {
                            "title": "Newest upload",
                            "description": "A detailed and unique description.",
                            "publishedAt": "2026-10-19T10:00:00Z",
                            "resourceId": {"videoId": "new001"},
                        },
                        "contentDetails": {"videoId": "new001"},
                    },
                    {
                        "snippet": {
                            "title": "Oldest upload",
                            "description": "Another detailed description.",
                            "publishedAt": "2026-08-01T10:00:00Z",
                            "resourceId": {"videoId": "old001"},
                        },
                        "contentDetails": {"videoId": "old001"},
                    },
                ]
            })

    class FakeYoutube:
        def channels(self):
            return Channels()

        def playlistItems(self):
            return PlaylistItems()

    result = uploader.seed_existing_channel_upload_history(history_path, youtube=FakeYoutube())

    assert result["seeded_count"] == 2
    entries = uploader._read_upload_history(history_path)
    assert [entry["video_id"] for entry in entries] == ["old001", "new001"]
    assert all(entry["format"] == "existing-channel-metadata" for entry in entries)
    assert all(not entry["narration"] for entry in entries)
    assert "metadata only" in result["message"]


def test_seed_existing_channel_upload_history_is_idempotent(tmp_path):
    history_path = tmp_path / "history.json"

    class FakeYoutube:
        def channels(self):
            raise AssertionError("The channel should not be queried again after seed.")

    history = [{
        "video_id": "already-seeded",
        "format": "existing-channel-metadata",
        "title": "Existing upload",
    }]
    history_path.write_text(__import__("json").dumps(history), encoding="utf-8")

    result = uploader.seed_existing_channel_upload_history(history_path, youtube=FakeYoutube())

    assert result["seeded_count"] == 1
    assert "already included" in result["message"]


def test_upload_rejects_unlisted(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")

    try:
        uploader.upload_video(
            video,
            "Test title",
            "Test description",
            "#Cricket",
            "Test comment",
            "unlisted",
            youtube=object(),
        )
    except ValueError as exc:
        assert "public or private" in str(exc)
    else:
        raise AssertionError("Unlisted should not be accepted.")


def test_upload_public_posts_comment(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    calls = []

    class Videos:
        def insert(self, **kwargs):
            return Request()

    class Comments:
        def insert(self, **kwargs):
            calls.append(kwargs["body"])
            return self

        def execute(self, num_retries=0):
            return {"id": "comment1"}

    class FakeYoutube:
        def videos(self):
            return Videos()

        def commentThreads(self):
            return Comments()

    class Request:
        def next_chunk(self, num_retries=0):
            return None, {
                "id": "abc123",
                "snippet": {"channelId": "channel"},
                "status": {"privacyStatus": "public"},
            }

    result = uploader.upload_video(
        video,
        "Test title",
        "Test description",
        "#Cricket",
        "Test comment",
        "public",
        youtube=FakeYoutube(),
    )

    assert result["video_id"] == "abc123"
    assert result["privacy_status"] == "public"
    assert result["comment_posted"] is True
    assert calls[0]["snippet"]["videoId"] == "abc123"
    assert calls[0]["snippet"]["channelId"] == "channel"


def test_upload_sets_private_metadata_and_skips_comments(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")

    class Videos:
        def insert(self, **kwargs):
            assert kwargs["body"]["snippet"]["categoryId"] == "17"
            assert kwargs["body"]["status"]["privacyStatus"] == "private"
            return Request()

    class FakeYoutube:
        def videos(self):
            return Videos()

    class Request:
        def next_chunk(self, num_retries=0):
            return None, {
                "id": "abc123",
                "snippet": {"channelId": "channel"},
                "status": {"privacyStatus": "private"},
            }

    result = uploader.upload_video(
        video,
        "Test title",
        "Test description",
        "#Cricket",
        "Test comment",
        "private",
        youtube=FakeYoutube(),
    )

    assert result["video_id"] == "abc123"
    assert result["comment_posted"] is False


def test_refresh_failure_explains_reauthorization(monkeypatch, tmp_path):
    token = tmp_path / "token.json"
    token.write_text("{}", encoding="utf-8")

    class FakeCredentials:
        scopes = [
            uploader.YOUTUBE_UPLOAD_SCOPE,
            uploader.YOUTUBE_COMMENT_SCOPE,
        ]
        expired = True
        refresh_token = "refresh-token"
        valid = False

        def refresh(self, request):
            raise uploader.RefreshError("invalid_grant: Token has been expired or revoked.")

    monkeypatch.setattr(
        uploader.Credentials,
        "from_authorized_user_file",
        classmethod(lambda cls, path: FakeCredentials()),
    )

    try:
        uploader._load_credentials(token, require_comments=True)
    except RuntimeError as exc:
        message = str(exc)
        assert "Re-authorize token.json" in message
        assert "expired, revoked, or no longer valid" in message
        assert "invalid_grant" in message
    else:
        raise AssertionError("Refresh failure should explain reauthorization.")


def test_public_upload_requires_upload_and_comment_scopes(monkeypatch, tmp_path):
    token = tmp_path / "token.json"
    token.write_text("{}", encoding="utf-8")

    class FakeCredentials:
        scopes = [uploader.YOUTUBE_COMMENT_SCOPE]
        expired = False
        refresh_token = None
        valid = True

    monkeypatch.setattr(
        uploader.Credentials,
        "from_authorized_user_file",
        classmethod(lambda cls, path: FakeCredentials()),
    )

    try:
        uploader._load_credentials(token, require_comments=True)
    except RuntimeError as exc:
        assert uploader.YOUTUBE_UPLOAD_SCOPE in str(exc)
    else:
        raise AssertionError("Public upload validation must require the upload scope.")


def test_public_upload_without_comment_does_not_require_comment_scope(monkeypatch, tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    captured = {}

    class Request:
        def next_chunk(self, num_retries=0):
            return None, {
                "id": "abc123",
                "snippet": {"channelId": "channel"},
                "status": {"privacyStatus": "public"},
            }

    class Videos:
        def insert(self, **kwargs):
            return Request()

    class FakeYoutube:
        def videos(self):
            return Videos()

    def fake_client(token_path, require_comments=False):
        captured["require_comments"] = require_comments
        return FakeYoutube()

    monkeypatch.setattr(uploader, "youtube_client", fake_client)

    result = uploader.upload_video(
        video,
        "Test title",
        "Test description",
        "#Cricket",
        "",
        "public",
    )

    assert result["video_id"] == "abc123"
    assert captured["require_comments"] is False
