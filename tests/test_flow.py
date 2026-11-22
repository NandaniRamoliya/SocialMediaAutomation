"""End-to-end: research -> plan -> draft -> QA -> Telegram approval -> publish, all faked."""
import json

from smm import db as S
from smm.llm import FakeLLM
from smm.orchestrator import Autopilot
from smm.publishers import NotConfigured, Result


def responder(system, prompt, schema):
    props = schema.get("properties", {})
    if "trends" in props:
        return {"trends": [{"topic": "AI agents", "why_now": "everyone talks", "our_angle": "practical"}],
                "competitor_notes": ["they post long videos"],
                "content_ideas": [{"idea": "3 tools", "pillar": "Education", "hook": "Stop wasting time"}]}
    if "items" in props:
        n = props["items"]["minItems"]
        days = [line.split('"day": "')[1][:10] for line in prompt.splitlines() if '"day": "' in line]
        return {"items": [{"day": days[i], "pillar": "Education", "topic": f"Topic {i}",
                           "hook": f"Hook {i}", "angle": "Angle"} for i in range(n)]}
    if "variants" in props:
        plats = props["variants"]["required"]
        topic = prompt.split("Topic: ")[1].splitlines()[0]
        return {"card": {"headline": f"Big idea {topic}", "subtext": "Short support line"},
                "variants": {p: {"text": f"{p} post about {topic}. Useful tip inside. #tip"} for p in plats}}
    if "score" in props:
        return {"score": 9, "issues": [], "risk": "low"}
    raise AssertionError(f"unexpected schema {schema}")


def at(monkeypatch, when):
    monkeypatch.setenv("SMM_FAKE_NOW", when)


def test_full_week(cfg, db, tg, monkeypatch, tmp_path):
    published = []

    class FakePublisher:
        def __init__(self, platform):
            self.platform = platform

        def publish(self, post):
            if self.platform == "linkedin":
                raise NotConfigured("LINKEDIN_ACCESS_TOKEN not set")
            published.append((self.platform, post.text, bool(post.image_path)))
            return Result(remote_id=f"{self.platform}-1", url=f"https://example.com/{self.platform}")

    llm = FakeLLM(responder)
    ap = Autopilot(cfg, db, llm=llm, telegram=tg, publisher_factory=lambda c, d, p: FakePublisher(p))

    # Monday 07:30 IST: research, plan 14 days, draft the first 3 and send them for approval.
    at(monkeypatch, "2026-11-23T02:00:00+00:00")
    ap.cycle()
    items = db.items()
    assert len(items) == 10
    awaiting = db.items(S.AWAITING)
    assert len(awaiting) == 3
    monday = awaiting[0]
    assert monday["day"] == "2026-11-23"
    assert {v["platform"] for v in db.variants(monday["id"])} == {"instagram", "facebook", "threads", "x"}
    assert any(m.get("photo") for m in tg.sent)  # image preview sent
    control = [m for m in tg.sent if m.get("buttons")]
    assert len(control) == 3

    # Approver taps Approve on Monday's post and replies with a change to Tuesday's.
    tuesday = awaiting[1]
    tue_msg = json.loads(tuesday["tg_msg_ids"])[1]
    tg.updates = [
        {"update_id": 1, "callback_query": {"id": "c1", "data": f"ap:{monday['id']}", "from": {"username": "boss"},
                                            "message": {"message_id": 999, "chat": {"id": 42}}}},
        {"update_id": 2, "message": {"chat": {"id": 42}, "text": "Make it more fun",
                                     "reply_to_message": {"message_id": tue_msg}}},
        {"update_id": 3, "message": {"chat": {"id": 7}, "text": "/pause"}},  # stranger: ignored
    ]
    # Monday 13:10 IST: approvals processed; Threads (13:00) is due and gets posted.
    at(monkeypatch, "2026-11-23T07:40:00+00:00")
    ap.cycle()
    assert db.item(monday["id"])["status"] == S.APPROVED
    assert [p for p, _, _ in published] == ["threads"]
    assert db.get_setting("paused", "0") == "0"
    # Tuesday was redrafted with the feedback and re-sent.
    assert db.item(tuesday["id"])["status"] == S.AWAITING
    assert any("Make it more fun" in prompt for _, prompt in llm.calls)

    # Monday 20:00 IST: everything for Monday is out except nothing unapproved.
    tg.updates = []
    at(monkeypatch, "2026-11-23T14:30:00+00:00")
    ap.cycle()
    assert sorted(p for p, _, _ in published) == ["facebook", "instagram", "threads", "x"]
    assert dict((p, img) for p, _, img in published)["instagram"] is True
    assert dict((p, img) for p, _, img in published)["x"] is False  # free tier: text only
    assert db.item(monday["id"])["status"] == S.PUBLISHED

    # Tuesday is never approved: at its first slot it expires and is NOT posted.
    at(monkeypatch, "2026-11-24T05:00:00+00:00")  # Tue 10:30 IST, after LinkedIn 09:30
    ap.cycle()
    assert db.item(tuesday["id"])["status"] == S.EXPIRED
    assert all(p != "linkedin" for p, _, _ in published)

    # Kill switch from the real approver chat stops drafting and posting.
    tg.updates = [{"update_id": 10, "message": {"chat": {"id": 42}, "text": "/pause"}}]
    before = len(llm.calls)
    at(monkeypatch, "2026-11-25T02:00:00+00:00")
    report = ap.cycle()
    assert db.get_setting("paused") == "1"
    assert len(llm.calls) == before
    assert any("paused" in r for r in report)


def test_auto_mode_and_not_connected(cfg, db, monkeypatch):
    cfg.brand["approval"]["mode"] = "auto"
    calls = []

    class Pub:
        def __init__(self, p):
            self.p = p

        def publish(self, post):
            calls.append(self.p)
            if self.p == "x":
                raise NotConfigured("X keys missing")
            return Result(remote_id="1")

    ap = Autopilot(cfg, db, llm=FakeLLM(responder), telegram=None, publisher_factory=lambda c, d, p: Pub(p))
    at(monkeypatch, "2026-11-23T02:00:00+00:00")
    ap.cycle()
    assert len(db.items(S.APPROVED)) == 3  # clean + low risk -> auto approved
    at(monkeypatch, "2026-11-23T14:30:00+00:00")
    ap.cycle()
    monday = [i for i in db.items() if i["day"] == "2026-11-23"][0]
    assert monday["status"] == S.PARTIAL  # X skipped (not connected), the rest posted
    states = {v["platform"]: v["status"] for v in db.variants(monday["id"])}
    assert states["x"] == "skipped" and states["instagram"] == "published"


def test_qa_failure_blocks_platform_and_rewrites_once(cfg, db, tg, monkeypatch):
    def bad(system, prompt, schema):
        out = responder(system, prompt, schema)
        if "variants" in schema.get("properties", {}):
            out["variants"]["x"]["text"] = "x" * 400  # always too long
        return out

    llm = FakeLLM(bad)
    ap = Autopilot(cfg, db, llm=llm, telegram=tg, publisher_factory=lambda c, d, p: None)
    at(monkeypatch, "2026-11-23T02:00:00+00:00")
    ap.cycle()
    monday = [i for i in db.items() if i["day"] == "2026-11-23"][0]
    states = {v["platform"]: v["status"] for v in db.variants(monday["id"])}
    assert states["x"] == "blocked" and states["instagram"] == "ready"
    assert monday["status"] == S.AWAITING
    rewrite_prompts = [p for _, p in llm.calls if "QA found these problems" in p]
    assert len(rewrite_prompts) == 3  # one automatic rewrite per drafted item
    assert any("BLOCKED" in m["text"] for m in tg.sent)


def test_step_failure_is_isolated(cfg, db, tg, monkeypatch):
    def broken(system, prompt, schema):
        if "trends" in schema.get("properties", {}):
            raise RuntimeError("research source down")
        return responder(system, prompt, schema)

    ap = Autopilot(cfg, db, llm=FakeLLM(broken), telegram=tg, publisher_factory=lambda c, d, p: None)
    at(monkeypatch, "2026-11-23T02:00:00+00:00")
    ap.cycle()
    assert len(db.items()) == 10  # planning still ran
    assert any("research" in m["text"] and "failed" in m["text"] for m in tg.sent)
