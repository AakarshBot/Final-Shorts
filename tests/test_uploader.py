from pathlib import Path

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
