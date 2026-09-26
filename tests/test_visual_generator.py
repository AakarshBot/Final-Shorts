from PIL import Image

import visual_generator


def test_generate_images_runs_configured_providers(monkeypatch):
    image = Image.new("RGB", (10, 10), "green")

    def fake_one(_query):
        return {"bytes": b"one", "hash": "one", "source": "One", "model": "m1"}

    def fake_two(_query):
        return {"bytes": b"two", "hash": "two", "source": "Two", "model": "m2"}

    monkeypatch.setenv("HF_TOKEN", "test")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "test")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test")
    monkeypatch.setattr(visual_generator, "PROVIDERS", (
        ("Hugging Face", fake_one),
        ("Cloudflare Workers AI", fake_two),
    ))

    result = visual_generator.generate_images("cricket stadium")

    assert [item["source"] for item in result["assets"]] == ["One", "Two"]


def test_generate_images_requires_manual_prompt(monkeypatch):
    result = visual_generator.generate_images("")

    assert result["assets"] == []
    assert result["providers"] == {}
