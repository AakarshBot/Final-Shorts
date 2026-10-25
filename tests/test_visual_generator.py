from io import BytesIO

from PIL import Image

import visual_generator


def test_generate_images_runs_configured_providers(monkeypatch):
    def fake_one(_query, _seed):
        return {"bytes": b"one", "hash": "one", "source": "One", "model": "m1"}

    def fake_two(_query, _seed):
        return {"bytes": b"two", "hash": "two", "source": "Two", "model": "m2"}

    monkeypatch.setenv("VISUAL_ALLOW_METERED_PROVIDERS", "true")
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


def test_generate_images_uses_a_fresh_seed_each_time(monkeypatch):
    seeds = []
    monkeypatch.setenv("VISUAL_ALLOW_METERED_PROVIDERS", "true")
    monkeypatch.setenv("HF_TOKEN", "test")

    def fake_provider(query, seed):
        seeds.append((query, seed))
        payload = f"{query}:{seed}".encode()
        return {
            "bytes": payload,
            "hash": visual_generator.hashlib.sha256(payload).hexdigest(),
            "source": "Hugging Face",
            "model": "test",
        }

    monkeypatch.setattr(
        visual_generator,
        "PROVIDERS",
        (("Hugging Face", fake_provider),),
    )
    seeds_to_return = iter((101, 202))
    monkeypatch.setattr(
        visual_generator.secrets,
        "randbelow",
        lambda _limit: next(seeds_to_return),
    )

    first = visual_generator.generate_images("player celebrating")
    second = visual_generator.generate_images("player batting")

    assert seeds == [
        ("player celebrating", 101),
        ("player batting", 202),
    ]
    assert first["assets"][0]["hash"] != second["assets"][0]["hash"]


def test_generate_images_includes_pollinations_only_after_explicit_metered_opt_in(monkeypatch):
    monkeypatch.setenv("VISUAL_ALLOW_METERED_PROVIDERS", "true")
    monkeypatch.setenv("POLLINATIONS_API_KEY", "test")
    monkeypatch.delenv("POLLINATIONS_API_TOKEN", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.setattr(
        visual_generator,
        "PROVIDERS",
        (("Pollinations.ai", lambda q, seed: {
            "bytes": b"flux", "hash": "flux1", "source": "Pollinations.ai", "model": "Flux"
        }),),
    )

    result = visual_generator.generate_images("cricket match")
    assert any(item["source"] == "Pollinations.ai" for item in result["assets"])


def test_pollinations_uses_authenticated_current_endpoint(monkeypatch):
    monkeypatch.setenv("POLLINATIONS_API_KEY", "test-secret")
    captured = {}

    class Response:
        headers = {"Content-Type": "image/png"}
        content = b"image-data"

        def raise_for_status(self):
            return None

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(visual_generator.requests, "get", fake_get)
    monkeypatch.setattr(visual_generator, "_valid_image", lambda data: data == b"image-data")

    result = visual_generator._pollinations("cricket player celebrating", 123)

    assert result["source"] == "Pollinations.ai"
    assert captured["url"].startswith("https://gen.pollinations.ai/image/")
    assert captured["headers"]["Authorization"] == "Bearer test-secret"
    assert captured["params"]["width"] == 576
    assert captured["params"]["height"] == 1024


def test_ai_horde_is_default_free_provider():
    assert ("AI Horde", visual_generator._ai_horde) in visual_generator.PROVIDERS


def test_ai_provider_failures_are_returned_as_actionable_diagnostics(monkeypatch):
    def unavailable(_query, _seed):
        raise RuntimeError("worker queue unavailable")

    monkeypatch.setattr(visual_generator, "PROVIDERS", (("AI Horde", unavailable),))
    result = visual_generator.generate_images("cricket match")

    assert result["assets"] == []
    assert "AI Horde" in result["errors"]
    assert "worker queue unavailable" in result["message"]


def test_ai_horde_decodes_a_completed_data_uri(monkeypatch):
    image = Image.new("RGB", (8, 8), (30, 50, 70))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = visual_generator.base64.b64encode(buffer.getvalue()).decode()

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    requests_seen = {"post": 0, "get": 0}

    def fake_post(_url, **kwargs):
        requests_seen["post"] += 1
        assert kwargs["headers"]["apikey"] == "0000000000"
        return Response({"id": "job-1"})

    def fake_get(url, **kwargs):
        requests_seen["get"] += 1
        if url.endswith("/generate/check/job-1"):
            return Response({"done": True, "faulted": False})
        return Response({"generations": [{"img": "data:image/png;base64," + encoded, "model": "TestModel"}]})

    monkeypatch.delenv("AI_HORDE_API_KEY", raising=False)
    monkeypatch.setattr(visual_generator.requests, "post", fake_post)
    monkeypatch.setattr(visual_generator.requests, "get", fake_get)
    monkeypatch.setattr(visual_generator.time, "sleep", lambda _seconds: None)

    result = visual_generator._ai_horde("a test image", 7)

    assert result["source"] == "AI Horde"
    assert result["model"] == "TestModel"
    assert result["bytes"] == buffer.getvalue()
    assert requests_seen == {"post": 1, "get": 2}


def test_optional_provider_credentials_do_not_enable_metered_generation_by_default(monkeypatch):
    called = []

    def fake_horde(query, seed, **kwargs):
        called.append(("AI Horde", kwargs))
        return {"bytes": b"free", "hash": "free", "source": "AI Horde", "model": "test"}

    def fake_metered(query, seed):
        called.append(("metered", {}))
        return {"bytes": b"paid", "hash": "paid", "source": "Metered", "model": "test"}

    monkeypatch.delenv("VISUAL_ALLOW_METERED_PROVIDERS", raising=False)
    monkeypatch.setenv("POLLINATIONS_API_KEY", "test")
    monkeypatch.setenv("HF_TOKEN", "test")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "test")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test")
    monkeypatch.setattr(visual_generator, "PROVIDERS", (
        ("AI Horde", fake_horde),
        ("Pollinations.ai", fake_metered),
        ("Hugging Face", fake_metered),
        ("Cloudflare Workers AI", fake_metered),
    ))

    result = visual_generator.generate_images("India cricket stadium")

    assert [asset["source"] for asset in result["assets"]] == ["AI Horde"]
    assert [name for name, _ in called] == ["AI Horde"]
    assert result["free_mode"] is True


def test_generate_images_passes_landscape_dimensions_and_bounded_timeout(monkeypatch):
    captured = {}

    def fake_horde(query, seed, *, width=576, height=1024, timeout_seconds=None):
        captured.update(width=width, height=height, timeout_seconds=timeout_seconds)
        return {"bytes": b"landscape", "hash": "landscape", "source": "AI Horde", "model": "test"}

    monkeypatch.delenv("VISUAL_ALLOW_METERED_PROVIDERS", raising=False)
    monkeypatch.setattr(visual_generator, "PROVIDERS", (("AI Horde", fake_horde),))

    result = visual_generator.generate_images(
        "cricket documentary stadium",
        orientation="landscape",
        timeout_seconds=120,
    )

    assert captured == {"width": 1024, "height": 576, "timeout_seconds": 120}
    assert result["orientation"] == "landscape"
    assert result["assets"][0]["source"] == "AI Horde"
