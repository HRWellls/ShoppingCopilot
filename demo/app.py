"""Chat-style local demo backed by real public evaluation samples."""
from __future__ import annotations
import json, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from evaluator.local_evaluator import coarse_category, load_jsonl, materialize_hidden_fields, initial_message, customer_reply
from starter.agent import Agent

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/catalog.jsonl" if (ROOT / "data/catalog.jsonl").exists() else ROOT / "data/catalog_sample_100.jsonl"
DATASET = ROOT / "data/public_set.jsonl" if (ROOT / "data/public_set.jsonl").exists() else ROOT / "data/public_smoke.jsonl"
agent = Agent(CATALOG)
samples = load_jsonl(DATASET)
sample_by_id = {str(s["sample_id"]): s for s in samples}
SUCCESSFUL_SAMPLE_IDS = (
    "public_0004", "public_0005", "public_0007", "public_0010", "public_0011",
    "public_0013", "public_0014", "public_0021", "public_0023", "public_0025",
)
demo_samples = [sample_by_id[sample_id] for sample_id in SUCCESSFUL_SAMPLE_IDS if sample_id in sample_by_id]
products = {p.parent_asin: p for p in agent._core.catalog}
evaluator_products = {
    p.parent_asin: {"parent_asin": p.parent_asin, "title": p.title, "features": list(p.features),
                    "description": p.description, "price": p.price, "categories": list(p.categories),
                    "details": dict(p.metadata), "store": p.brand or ""}
    for p in agent._core.catalog
}
sessions = {}

def start(sample_id):
    sample = sample_by_id.get(sample_id) or samples[0]
    sid = "demo-" + uuid.uuid4().hex
    agent.reset(sid, sample["user_profile"])
    card, behavior = materialize_hidden_fields(sample, evaluator_products)
    disclosed = set()
    target = str(sample["ground_truth"]["parent_asin"])
    category = coarse_category(list(evaluator_products[target]["categories"]))
    msg = initial_message({**sample, "intent_card": card, "behavior": behavior}, category, disclosed)
    effective = {**sample, "intent_card": card, "behavior": behavior}
    sessions[sid] = {
        "sample": effective, "target": target,
        "turn": 0, "disclosed": disclosed, "boundary": False,
        "override_applied": sample["scenario_type"] != "intent_override", "next_user": msg,
    }
    return {"session_id": sid, "sample_id": sample["sample_id"], "scenario_type": sample["scenario_type"], "target": sessions[sid]["target"], "user_message": msg, "fallback": not bool(agent._core.dense)}

def run_turn(sid):
    state = sessions[sid]; state["turn"] += 1; n = state["turn"]; message = state["next_user"]
    response = agent.respond(sid, message, n, 10); rows = []
    for item in response.get("recommendations", []):
        p = products.get(item.get("parent_asin"))
        if p: rows.append({"parent_asin": p.parent_asin, "title": p.title, "price": p.price, "target": p.parent_asin == state["target"]})
    hit_rank = next((index for index, row in enumerate(rows, 1) if row["target"]), None)
    hit = hit_rank is not None
    next_user = None
    if not hit and n < 10:
        override = state["sample"].get("behavior", {}).get("override") or {}
        if not state["override_applied"] and n + 1 == int(override.get("turn", 3)):
            state["override_applied"] = True
            next_user = str(override.get("message", "Actually, please ignore my earlier preference."))
            new_value = str(override.get("new_value", ""))
            if new_value: state["disclosed"].add(new_value)
        else:
            next_user, state["boundary"] = customer_reply(
                state["sample"], response.get("ask_attribute"), state["disclosed"], state["boundary"]
            )
        state["next_user"] = next_user
    return {"turn": n, "user": message, "agent": response.get("message", ""), "ask_attribute": response.get("ask_attribute"), "recommendations": rows, "next_user": next_user, "hit": hit, "hit_rank": hit_rank, "done": n >= 10 or hit}

HTML = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")
class Handler(BaseHTTPRequestHandler):
    def send_payload(self, value, status=200, content="application/json; charset=utf-8"):
        body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode(); self.send_response(status); self.send_header("Content-Type", content); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/scenarios": self.send_payload([{"sample_id": s["sample_id"], "scenario_type": s["scenario_type"], "difficulty": s.get("difficulty_bucket", "")} for s in demo_samples]); return
        if path == "/api/start": self.send_payload(start(parse_qs(urlparse(self.path).query).get("sample_id", [samples[0]["sample_id"]])[0])); return
        self.send_payload(HTML.encode(), content="text/html; charset=utf-8")
    def do_POST(self):
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0")))); self.send_payload(run_turn(str(data["session_id"])))
        except Exception as exc: self.send_payload({"error": "invalid session or message", "detail": str(exc)}, 400)
    def log_message(self, *_): pass

if __name__ == "__main__":
    print("Demo running at http://127.0.0.1:8765"); HTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
