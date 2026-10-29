"""The review chair must receive its own persona and all five audience reviews."""

import json
from pathlib import Path

import pytest

from backend import advisors
from backend.personas import Persona
from backend.settings import Settings, _normalize_advisor_presets


@pytest.mark.asyncio
async def test_five_original_audience_prompts_and_separate_chair(monkeypatch):
    bundle = json.loads((Path(__file__).resolve().parents[2] / "desktop/role_bundle.json").read_text(encoding="utf-8"))
    personas = {pid: Persona(id=pid, is_custom=True, **value) for pid, value in bundle["personas"].items()}
    settings = Settings(**bundle["settings"])
    ids = [pid for pid in personas if pid != "source-editor"]
    captured = []

    async def fake_query(model, messages, **kwargs):
        captured.append(messages)
        return {"content": "评分（1-10）：7\n问题：需补充依据。\nCONSENSUS_SCORE: 2", "error": False}

    monkeypatch.setattr(advisors, "get_settings", lambda: settings)
    monkeypatch.setattr(advisors, "get_persona", lambda pid: personas.get(pid))
    monkeypatch.setattr(advisors, "get_personas_by_ids", lambda values: [personas[pid] for pid in values])
    monkeypatch.setattr(advisors, "query_model", fake_query)
    events = [event async for event in advisors.run_debate("独立测试原稿", ids + ["source-editor"], default_model="custom:fixture", max_rounds=3)]
    result = next(event["data"] for event in events if event["type"] == "advisor_complete")
    assert len(result["rounds"]) == 3
    assert all(len(item["responses"]) == 5 for item in result["rounds"])
    systems = [messages[0]["content"] for messages in captured if messages[0]["role"] == "system"]
    assert len(systems) == 16
    for pid in ids:
        assert systems.count(personas[pid].system_prompt) == 3
    assert systems.count(personas["source-editor"].system_prompt) == 1
    assert result["verdict"]["persona_name"] == "主编"
    chair_call = next(messages for messages in captured if messages[0]["content"] == personas["source-editor"].system_prompt)
    assert all(personas[pid].name in chair_call[-1]["content"] for pid in ids)


def test_saved_panel_keeps_all_five_reviewers():
    ids = ["tech", "practical", "surfer", "thinker", "beginner"]
    saved = _normalize_advisor_presets([{"id": "five", "name": "五位观众", "persona_ids": ids}])
    assert saved[0]["persona_ids"] == ids
