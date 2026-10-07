"""Non-blocking editorial repetition audit for published Final-Shorts packages."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

HISTORY_PATH = Path("output/editorial_history.json")
MAX_HISTORY = 30


def _clean(value) -> str:
    return " ".join(str(value or "").split()).strip()


def _visual_treatment(assignment: dict) -> str:
    if not isinstance(assignment, dict):
        return "unknown"
    if assignment.get("manual_subject_cutout") is not None:
        return "text-subject-cutout"
    card = assignment.get("card_studio")
    if isinstance(card, dict):
        data = card.get("data") if isinstance(card.get("data"), dict) else {}
        card_type = _clean(card.get("type"))
        composition = _clean(data.get("composition"))
        return f"card:{card_type}:{composition or 'unspecified'}"
    return f"image:{_clean(assignment.get('result_key')) or 'retrieval'}"


def _load_history() -> list[dict]:
    if not HISTORY_PATH.is_file():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    return data if isinstance(data, list) else []


def _save_history(history: list[dict]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps(history[-MAX_HISTORY:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def record_publication(script: dict, visual_assignments, *, title: str, line: str) -> None:
    scenes = list(script.get("script") or []) if isinstance(script, dict) else []
    if not scenes:
        scenes = list(script.get("slides") or []) if isinstance(script, dict) else []
    assignments = visual_assignments or {}
    if isinstance(assignments, list):
        assignments = {index + 1: item for index, item in enumerate(assignments)}

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "title": _clean(title),
        "line": _clean(line),
        "story_angle": _clean(script.get("story_angle")) if isinstance(script, dict) else "",
        "narrative_structure": _clean(script.get("narrative_structure")) if isinstance(script, dict) else "top5-package" if script else "",
        "narrative_roles": [
            _clean(scene.get("narrative_role"))
            for scene in scenes
            if isinstance(scene, dict) and _clean(scene.get("narrative_role"))
        ],
        "visual_treatments": [
            _visual_treatment(assignments.get(index))
            for index in sorted(assignments)
        ],
    }
    history = _load_history()
    history.append(entry)
    _save_history(history)


def audit_recent(limit: int = 20) -> dict:
    history = _load_history()[-max(1, int(limit)):]
    warnings = []

    structures = [_clean(item.get("narrative_structure")) for item in history if _clean(item.get("narrative_structure"))]
    if len(structures) >= 4:
        counts = {value: structures.count(value) for value in set(structures)}
        value, count = max(counts.items(), key=lambda pair: pair[1])
        if count >= 4:
            warnings.append(f"Narrative structure is repeating: {count} of the last {len(history)} use {value}.")

    role_sequences = [
        " → ".join(_clean(role) for role in item.get("narrative_roles") or [])
        for item in history
        if item.get("narrative_roles")
    ]
    if len(role_sequences) >= 4:
        counts = {value: role_sequences.count(value) for value in set(role_sequences)}
        value, count = max(counts.items(), key=lambda pair: pair[1])
        if count >= 4:
            warnings.append(f"Slide-role sequence is repeating: {count} of the last {len(history)} match.")

    visual_sequences = [
        " → ".join(_clean(value) for value in item.get("visual_treatments") or [])
        for item in history
        if item.get("visual_treatments")
    ]
    if len(visual_sequences) >= 4:
        counts = {value: visual_sequences.count(value) for value in set(visual_sequences)}
        value, count = max(counts.items(), key=lambda pair: pair[1])
        if count >= 4:
            warnings.append(f"Visual treatment sequence is repeating: {count} of the last {len(history)} match.")

    cards = [
        value
        for item in history
        for value in item.get("visual_treatments") or []
        if value.startswith("card:")
    ]
    if len(cards) >= 5:
        counts = {value: cards.count(value) for value in set(cards)}
        value, count = max(counts.items(), key=lambda pair: pair[1])
        if count >= 4:
            warnings.append(f"Card treatment is repeating: {count} recent cards use {value}.")

    return {"count": len(history), "warnings": warnings, "items": history}
