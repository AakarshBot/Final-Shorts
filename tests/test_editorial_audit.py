import json

import editorial_audit


def test_record_publication_keeps_only_editorial_metadata(tmp_path, monkeypatch):
    path = tmp_path / "history.json"
    monkeypatch.setattr(editorial_audit, "HISTORY_PATH", path)
    editorial_audit.record_publication(
        {
            "story_angle": "What he said",
            "narrative_structure": "reaction-led",
            "script": [
                {"narrative_role": "reaction"},
                {"narrative_role": "context"},
            ],
        },
        {
            1: {"result_key": "manual-crawler"},
            2: {"card_studio": {"type": "Quote / Reaction", "data": {"composition": "Quote Lead"}}},
        },
        title="Alcaraz Explains Tokyo Win",
        line="deep_dive",
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data[0]["narrative_structure"] == "reaction-led"
    assert data[0]["narrative_roles"] == ["reaction", "context"]
    assert data[0]["visual_treatments"] == [
        "image:manual-crawler",
        "card:Quote / Reaction:Quote Lead",
    ]
    assert "url" not in data[0]


def test_audit_warns_without_blocking(tmp_path, monkeypatch):
    path = tmp_path / "history.json"
    monkeypatch.setattr(editorial_audit, "HISTORY_PATH", path)
    for index in range(4):
        editorial_audit.record_publication(
            {
                "story_angle": f"Angle {index}",
                "narrative_structure": "reaction-led",
                "script": [{"narrative_role": "reaction"}, {"narrative_role": "context"}],
            },
            {1: {"result_key": "auto"}, 2: {"result_key": "auto"}},
            title=f"Story {index}",
            line="deep_dive",
        )
    audit = editorial_audit.audit_recent()
    assert audit["count"] == 4
    assert audit["warnings"]
