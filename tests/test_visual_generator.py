import visual_generator


def test_generate_images_runs_configured_providers(monkeypatch):
    def fake_one(_query, _seed):
        return {"bytes": b"one", "hash": "one", "source": "One", "model": "m1"}

    def fake_two(_query, _seed):
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


def test_generate_images_uses_a_fresh_seed_each_time(monkeypatch):
    seeds = []
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
