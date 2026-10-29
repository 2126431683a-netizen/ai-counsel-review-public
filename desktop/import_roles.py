"""Idempotently import the prepared role bundle through the local application API."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import time
import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:3340")
parser.add_argument("--report", default="build/imported-roles.json")
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
bundle = json.loads((root / "desktop/role_bundle.json").read_text(encoding="utf-8"))
with httpx.Client(base_url=args.url, trust_env=False, timeout=30) as client:
    settings = client.get("/api/settings").json()
    if "advisor_chair_persona_id" not in settings:
        raise RuntimeError("Restart with the updated backend before importing the five-reader panel.")
    personas = client.get("/api/personas").json()
    backup = root / "build/role-backups" / str(time.time_ns())
    backup.mkdir(parents=True)
    # Deliberately back up only role/prompt configuration, never credentials.
    safe = {key: value for key, value in settings.items() if key.startswith("advisor_")}
    (backup / "settings.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    (backup / "personas.json").write_text(json.dumps(personas, ensure_ascii=False, indent=2), encoding="utf-8")
    mapping = {}
    for bundle_id, fields in bundle["personas"].items():
        existing = next((p for p in personas if p.get("is_custom") and p["name"] == fields["name"]), None)
        payload = {key: value for key, value in fields.items() if key != "color"}
        # Prompt refreshes preserve an explicit visual choice made in the UI.
        if existing and str(existing.get("avatar_emoji", "")).startswith("review:"):
            payload["avatar_emoji"] = existing["avatar_emoji"]
        if existing:
            response = client.patch("/api/personas/" + existing["id"], json=payload)
        else:
            response = client.post("/api/personas", json=payload)
        response.raise_for_status()
        saved = response.json()
        assert saved["system_prompt"] == fields["system_prompt"]
        mapping[bundle_id] = saved["id"]
    updates = copy.deepcopy(bundle["settings"])
    updates["advisor_chair_persona_id"] = mapping[updates["advisor_chair_persona_id"]]
    preset_id = "source-audience-review"
    presets = [dict(p, is_default=False) for p in settings["advisor_presets"] if p["id"] != preset_id]
    if len(presets) >= 20:
        raise RuntimeError("The existing preset list is full. Imported roles are saved; no presets were removed.")
    preset = {"id": preset_id, "name": bundle["name"], "persona_ids": [mapping[pid] for pid in bundle["personas"] if pid != "source-editor"],
              "mode": "simple", "default_model": settings["advisor_default_model"], "tiebreaker_model": settings["advisor_tiebreaker_model"],
              "max_rounds": 3, "is_default": True}
    updates["advisor_presets"] = [preset] + presets
    response = client.put("/api/settings", json=updates)
    response.raise_for_status()
    final = client.get("/api/settings").json()
    assert final["advisor_chair_persona_id"] == mapping["source-editor"]
    assert len(final["advisor_presets"][0]["persona_ids"]) == 5
    report = {"url": args.url, "preset": bundle["name"], "reviewers": [p["name"] for key, p in bundle["personas"].items() if key != "source-editor"],
              "chair": "主编", "roleIdMapping": mapping, "exactPromptContentVerified": True,
              "sourceHashes": bundle["sources"], "backup": str(backup), "usesRealModel": False}
    report_path = root / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in ("backup", "sourceHashes")}, ensure_ascii=False))
