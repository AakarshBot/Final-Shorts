from top5_script_writer import (
    BODY_MAX_WORDS,
    BODY_MIN_WORDS,
    SLIDE_1_MAX_WORDS,
    STORY_HEADLINE_MAX_WORDS,
    estimate_speech_seconds,
    validate_top5_script,
)


def stories():
    return [
        {
            "title": f"Story {index} cricket record confirmed",
            "url": f"https://example.com/story-{index}",
            "source": "Test",
            "published_at": "2026-09-27T10:00:00+00:00",
            "article": f"Player {index} confirmed the cricket record after the match. "
                       "The board published the result and gave the relevant context.",
        }
        for index in range(1, 6)
    ]


def valid_result():
    slides = [
        {
            "slide_number": 1,
            "story_index": 0,
            "headline": "Five cricket stories worth your time today",
            "body": "",
            "primary_entity": "India cricket",
            "visual_intent": "five selected cricket stories",
            "specific_search_prompt": "selected cricket stories montage",
            "sport_or_topic_category": "Cricket",
        }
    ]
    for index in range(1, 6):
        slides.append(
            {
                "slide_number": index + 1,
                "story_index": index,
                "headline": (
                    f"Story {index} confirmed the cricket record after the match, "
                    "with the board publishing the result"
                ),
                "body": (
                    f"Player {index} made the record official after the match. "
                    "The board published the result and supplied the supporting context."
                ),
                "primary_entity": f"Player {index}",
                "visual_intent": "player after cricket match",
                "specific_search_prompt": f"Player {index} cricket match",
                "sport_or_topic_category": "Cricket",
            }
        )
    return {"slides": slides, "hashtags": ["#Cricket", "#Top5", "#Shorts"]}


def test_valid_top5_script_contract():
    result = valid_result()
    valid, reason = validate_top5_script(result, stories())
    assert valid, reason


def test_exactly_six_slides_required():
    result = valid_result()
    result["slides"] = result["slides"][:5]
    valid, reason = validate_top5_script(result, stories())
    assert not valid
    assert "exactly six" in reason


def test_slide_one_has_fourteen_word_cap():
    result = valid_result()
    result["slides"][0]["headline"] = "One two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen"
    valid, reason = validate_top5_script(result, stories())
    assert not valid
    assert "Slide 1" in reason


def test_story_headline_is_below_fifteen_seconds():
    result = valid_result()
    result["slides"][1]["headline"] = "Story 1 confirmed the cricket record after the match, with the board publishing the result and explaining the decision to selectors this morning"
    valid, reason = validate_top5_script(result, stories())
    assert not valid
    assert "15 seconds" in reason


def test_body_is_not_a_headline_restatement():
    result = valid_result()
    result["slides"][1]["body"] = result["slides"][1]["headline"]
    valid, reason = validate_top5_script(result, stories())
    assert not valid
    assert "too similar" in reason


def test_body_bounds_are_fixed():
    assert BODY_MIN_WORDS > 0
    assert BODY_MAX_WORDS > BODY_MIN_WORDS


def test_speech_estimate_is_word_based_and_under_limit():
    assert estimate_speech_seconds(" ".join(["word"] * STORY_HEADLINE_MAX_WORDS)) < 15
