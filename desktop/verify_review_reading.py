"""A bounded real-model spot check of the new instructions on an existing review."""

import asyncio
import json
import os
import sys
from pathlib import Path

os.environ["AI_COUNSEL_DATA_DIR"] = str(Path(os.environ["LOCALAPPDATA"]) / "AICounselReview")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from backend.council import get_provider_for_model
from backend.prompts import apply_response_language


async def main():
    root = Path(__file__).resolve().parent.parent
    with httpx.Client(base_url="http://127.0.0.1:3340", trust_env=False, timeout=20) as client:
        settings = client.get("/api/settings").json()
        personas = client.get("/api/personas").json()
        conversation_id = "afaf1559-d39b-4cfe-a403-d9dc81feb9cf"
        conversation = client.get("/api/conversations/" + conversation_id).json()
    manuscript = conversation["messages"][0]["content"]
    old = conversation["messages"][-1]
    transcript = "\n\n".join(item["persona_name"] + ":\n" + item["content"] for item in old["rounds"][0]["responses"])
    model = settings["advisor_default_model"]
    provider = get_provider_for_model(model)
    checks = [
        ("较真技术党", settings["advisor_round1_prompt"].format(search_context_block="", question=manuscript, consensus_tag="")),
        ("主编", settings["advisor_verdict_prompt"].format(question=manuscript, debate_arc="以下为此前一轮观众意见的独立复核，不预设它们正确或错误。", transcript=transcript)),
    ]
    results = []
    for name, prompt in checks:
        persona = next(item for item in personas if item["name"] == name)
        result = await provider.query(model, [{"role": "system", "content": persona["system_prompt"]},
            {"role": "user", "content": apply_response_language(prompt, settings["response_language"])}], timeout=180, temperature=0.2)
        if result.get("error"):
            raise RuntimeError(name + ": " + result.get("error_message", "Model request failed"))
        results.append({"role": name, "content": result["content"], "usage": result.get("usage")})
        print("### " + name + "\n" + result["content"], flush=True)
    report = {"usesRealModel": True, "scope": "two-call spot check; not a complete new five-person review", "sourceConversation": conversation_id,
              "model": model, "results": results}
    (root / "build/reading-v2-real-spotcheck.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
