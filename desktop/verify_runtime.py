"""Exercise the packaged server against local protocol fixtures, never a real LLM."""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--server", required=True)
parser.add_argument("--output", default="build/runtime-verification.json")
parser.add_argument("--check-html", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
profile = root / "build" / ("qa-profile-" + str(time.time_ns()))
profile.mkdir(parents=True)
calls = []
role_names = ["普通读者", "结构编辑", "事实审查", "文风编辑"]
bundle_file = root / "desktop/role_bundle.json"
bundle = json.loads(bundle_file.read_text(encoding="utf-8")) if bundle_file.exists() else None
role_prompts = {p["name"]: p["system_prompt"] for pid, p in bundle["personas"].items() if pid != "source-editor"} if bundle else {}
chair_prompt = bundle["personas"]["source-editor"]["system_prompt"] if bundle else None
if bundle:
    role_names = list(role_prompts)
manuscript = "验收样稿：某公司说所有读者每天节省十小时，但没有给出样本与来源。请审查结构、措辞与证据。"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *unused):
        pass

    def send(self, body):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/v1/models":
            return self.send({"data": [{"id": "review-fixture"}, {"id": "review-fixture-2"}]})
        if self.path == "/api/tags":
            return self.send({"models": [{"name": "review-fixture", "modified_at": "2026-10-15T00:00:00Z"}, {"name": "review-fixture-2", "modified_at": "2026-10-15T00:00:00Z"}]})
        return self.send({})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        if self.path == "/bad/chat/completions":
            data = b"<!doctype html><html>API console instead of a chat response</html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        messages = body.get("messages", [])
        system = "\n".join(m.get("content", "") for m in messages if m.get("role") == "system")
        user = "\n".join(m.get("content", "") for m in messages if m.get("role") == "user")
        role = next((name for name in role_names if "你的角色名是「" + name + "」" in system), None)
        if role_prompts:
            role = next((name for name, prompt in role_prompts.items() if system == prompt), None)
        if role:
            content = f"{role}验收意见：原句“每天节省十小时”缺乏来源，建议补充样本与计算口径。\nCONSENSUS_SCORE: 2"
        elif (chair_prompt and system == chair_prompt) or "## 各角色关键意见" in user:
            content = "## 总体判断\n以下为接口验收模拟内容，不代表模型审稿质量。\n## 各角色关键意见\n" + "\n".join(f"- {name}：{name}验收意见保留。" for name in role_names)
        elif "提取各角色" in user or "简要提取共同问题" in user:
            content = "\n".join(f"{name}：{name}验收意见，来源待核实。" for name in role_names)
        else:
            content = "OK"
        calls.append({"path": self.path, "model": body.get("model"), "role": role, "user": user, "content": content, "isChair": bool(chair_prompt and system == chair_prompt)})
        if self.path == "/api/chat":
            self.send({"model": body.get("model"), "message": {"role": "assistant", "content": content}, "done": True, "prompt_eval_count": 20, "eval_count": 10})
        else:
            self.send({"choices": [{"message": {"role": "assistant", "content": content}}], "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}})


mock = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=mock.serve_forever, daemon=True).start()
mock_url = f"http://127.0.0.1:{mock.server_port}"
with socket.socket() as probe:
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
env = dict(os.environ, NO_PROXY="localhost,127.0.0.1,::1", no_proxy="localhost,127.0.0.1,::1",
           LLM_COUNCIL_PRICING_SOURCE_URL=mock_url + "/pricing", LLM_COUNCIL_LITELLM_PRICING_URL=mock_url + "/pricing")
process = subprocess.Popen([str(Path(args.server).resolve()), "--port", str(port), "--data-dir", str(profile)], env=env,
                           creationflags=subprocess.CREATE_NO_WINDOW)
results = []
try:
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=120, trust_env=False) as client:
        deadline = time.monotonic() + 90
        while True:
            try:
                if client.get("/api/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if process.poll() is not None:
                raise RuntimeError("Packaged server exited: " + (profile / "server.log").read_text(encoding="utf-8"))
            if time.monotonic() > deadline:
                raise TimeoutError("Packaged server did not become ready")
            time.sleep(0.3)
        assert "AI 审稿团" in client.get("/").text
        settings = client.get("/api/settings").json()
        assert settings["response_language"] == "Chinese (Simplified)"
        assert settings["advisor_presets"][0]["name"] == (bundle["name"] if bundle else "中文四角色审稿团")
        personas = client.get("/api/personas").json()
        ids = [p["id"] for p in personas if p["name"] in role_names]
        assert len(ids) == len(role_names)
        custom = client.post("/api/personas", json={"name": "验收临时角色", "role": "中文保存", "description": "编码检查", "system_prompt": "保留中文测试。"}).json()
        edited = client.patch("/api/personas/" + custom["id"], json={"name": "验收已编辑角色"}).json()
        assert edited["name"] == "验收已编辑角色"
        assert client.delete("/api/personas/" + custom["id"]).status_code == 200
        if args.check_html:
            client.put("/api/settings", json={"custom_endpoint_url": mock_url + "/bad", "enabled_providers": {"custom": True}}).raise_for_status()
            invalid = client.post("/api/ask", json={"content": "HTML fixture only", "models": ["custom:review-fixture"], "execution_mode": "chat_only"})
            assert invalid.status_code == 400
            assert "网页" in invalid.json()["detail"] and "/v1" in invalid.json()["detail"]
            assert "line 1 column 1" not in invalid.json()["detail"]
        for provider in ("custom", "ollama"):
            start = len(calls)
            update = {"enabled_providers": {"custom": provider == "custom", "ollama": provider == "ollama"},
                      "custom_endpoint_name": "本机验收", "custom_endpoint_url": mock_url + "/v1", "ollama_base_url": mock_url}
            response = client.put("/api/settings", json=update)
            response.raise_for_status()
            if provider == "custom":
                connection = client.post("/api/settings/test-custom-endpoint", json={"name": "验收", "url": mock_url + "/v1"}).json()
                assert connection["success"], connection
                models = client.get("/api/custom-endpoint/models").json()["models"]
            else:
                models = client.get("/api/ollama/tags").json()["models"]
            assert len(models) == 2, models
            conv = client.post("/api/conversations", json={"mode": "advisors"}).json()
            response = client.post(f"/api/conversations/{conv['id']}/debate/stream", json={
                "question": manuscript, "persona_ids": ids, "default_model": provider + ":review-fixture",
                "tiebreaker_model": provider + ":review-fixture", "max_rounds": 3,
                "model_assignments": {ids[-1]: provider + ":review-fixture-2"},
            })
            response.raise_for_status()
            events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
            assert not any(e["type"] == "advisor_error" for e in events), events
            completed = next(e["data"] for e in events if e["type"] == "advisor_complete")
            assert len(completed["rounds"]) == 3
            for round_data in completed["rounds"]:
                assert len(round_data["responses"]) == len(role_names)
                assert all(not item.get("error") for item in round_data["responses"])
            run_calls = calls[start:]
            reviewers = [c for c in run_calls if c["role"]]
            assert len(reviewers) == 3 * len(role_names), {"roles": [c["role"] for c in run_calls], "count": len(run_calls)}
            first_round = [c for c in reviewers if "这是独立审稿轮" in c["user"] or "这是独立审阅轮" in c["user"]]
            assert len(first_round) == len(role_names)
            assert all(manuscript in c["user"] and "验收意见" not in c["user"] for c in first_round)
            assert set(c["model"] for c in reviewers) == {"review-fixture", "review-fixture-2"}
            assert all(name in completed["verdict"]["content"] for name in role_names)
            if bundle:
                chair_calls = [c for c in run_calls if c["isChair"]]
                assert len(chair_calls) == 1
                assert all(name in chair_calls[0]["user"] for name in role_names)
                assert completed["verdict"]["persona_name"] == "主编"
                assert "不要改写句子或生成替代文案" in first_round[0]["user"]
            saved = client.get(f"/api/conversations/{conv['id']}").json()
            assert len(saved["messages"]) == 2
            results.append({"provider": provider, "modelCalls": len(run_calls), "reviewerCalls": 3 * len(role_names), "rounds": 3,
                            "chairUsesOriginalPersonaPrompt": bool(bundle), "originalReviewerPromptsPreserved": bool(role_prompts),
                            "independentFirstRound": True, "perRoleModelAssignment": True, "allRoleOpinionsInVerdict": True,
                            "conversationPersisted": True})
    output = {"packagedRuntime": True, "usesRealModel": False, "chineseSettings": True, "roleCrud": True, "htmlConsoleErrorExplained": args.check_html, "providers": results}
    target = root / args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False))
finally:
    (root / "build/fixture-calls.json").write_text(json.dumps(calls, ensure_ascii=False, indent=2), encoding="utf-8")
    process.terminate()
    process.wait(timeout=15)
    mock.shutdown()
