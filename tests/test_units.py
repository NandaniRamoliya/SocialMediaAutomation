from datetime import datetime, timezone

from smm.agents import qa
from smm.agents.research import google_news_url, parse_feed
from smm.agents.strategist import _pillar_plan, open_days, platforms_for_day
from smm.creative import render_card
from smm.llm import extract_json
from smm.publishers.linkedin import escape_commentary

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>AI tools for small business</title><link>https://n.example/1</link><pubDate>Fri</pubDate></item>
</channel></rss>"""
ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
<entry><title>Competitor video</title><link href="https://youtube.com/watch?v=1"/>
<published>2026-11-20</published><media:group><media:community>
<media:statistics views="12345"/></media:community></media:group></entry></feed>"""


def test_parse_rss_and_atom():
    rss = parse_feed(RSS, "news")
    atom = parse_feed(ATOM, "yt")
    assert rss[0]["title"] == "AI tools for small business"
    assert atom[0]["link"] == "https://youtube.com/watch?v=1"
    assert atom[0]["views"] == "12345"
    assert parse_feed("not xml", "x") == []


def test_google_news_url():
    url = google_news_url("ai tools", {"hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
    assert url.startswith("https://news.google.com/rss/search?q=ai%20tools&hl=en-IN")


def test_extract_json_variants():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! {"a": 2} hope this helps') == {"a": 2}


def test_x_length_weights():
    assert qa.x_weighted_length("hello") == 5
    assert qa.x_weighted_length("see https://example.com/very/long/path") == 4 + 23
    assert qa.x_weighted_length("🚀") == 2


def test_qa_checks(cfg):
    errors, _ = qa.check(cfg, "x", "a" * 300)
    assert any("too long" in e for e in errors)
    errors, _ = qa.check(cfg, "instagram", "This is guaranteed to work")
    assert any("banned" in e for e in errors)
    errors, _ = qa.check(cfg, "linkedin", "Read more at [insert link]")
    assert any("placeholder" in e for e in errors)
    _, warnings = qa.check(cfg, "instagram", "Visit https://example.com today")
    assert any("not clickable" in w for w in warnings)
    errors, _ = qa.check(cfg, "facebook", "Exactly the same post as last week!",
                         recent=["Exactly the same post as last week!"])
    assert any("identical" in e for e in errors)
    errors, warnings = qa.check(cfg, "threads", "Clean short post #one")
    assert errors == [] and warnings == []


def test_linkedin_escaping():
    assert escape_commentary("Hi (all) #ai @me") == r"Hi \(all\) \#ai \@me"


def test_schedule(cfg, db):
    monday = datetime(2026, 11, 23).date()
    assert set(platforms_for_day(cfg, monday)) == {"instagram", "facebook", "threads", "x"}
    assert set(platforms_for_day(cfg, monday.replace(day=24))) == {"linkedin", "threads", "x"}
    assert platforms_for_day(cfg, monday.replace(day=29)) == []  # Sunday, YouTube disabled
    now = datetime(2026, 11, 23, 2, 0, tzinfo=timezone.utc)  # Mon 07:30 IST
    days = open_days(cfg, db, now)
    assert days[0] == monday and len(days) == 10  # 14 days, weekends have no slots


def test_pillar_plan_respects_weights(cfg):
    seq = _pillar_plan(cfg, 10)
    assert len(seq) == 10
    assert seq.count("Education") == 4 and seq.count("Offer") == 2
    assert all(a != b for a, b in zip(seq, seq[1:]))


def test_render_card(cfg, tmp_path):
    path = render_card(cfg, "Three AI tools that save 5 hours a week",
                       "No coding needed. Free to start.", tmp_path / "c.png")
    from PIL import Image
    assert Image.open(path).size == (1080, 1080)
