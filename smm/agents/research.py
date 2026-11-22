"""Market Radar: free sources only (no API keys, no quota).

- Google News RSS search for each niche keyword
- Competitors' YouTube channels via their public RSS feed (no YouTube API quota used)
- Any extra RSS/Atom feeds (competitor blogs, industry news)

The raw headlines are summarised by the LLM into a short brief the Strategist uses.
"""
from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET

import requests

from ..brand import system_prompt
from ..config import Config
from ..db import DB

UA = {"User-Agent": "Mozilla/5.0 (compatible; SocialMediaAutomation/0.1)"}
ATOM = "{http://www.w3.org/2005/Atom}"
MEDIA = "{http://search.yahoo.com/mrss/}"

BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "trends": {"type": "array", "items": {"type": "object", "properties": {
            "topic": {"type": "string"}, "why_now": {"type": "string"}, "our_angle": {"type": "string"}},
            "required": ["topic", "why_now", "our_angle"]}},
        "competitor_notes": {"type": "array", "items": {"type": "string"}},
        "content_ideas": {"type": "array", "items": {"type": "object", "properties": {
            "idea": {"type": "string"}, "pillar": {"type": "string"}, "hook": {"type": "string"}},
            "required": ["idea", "pillar", "hook"]}},
    },
    "required": ["trends", "competitor_notes", "content_ideas"],
}


def parse_feed(xml_text: str, source: str) -> list[dict]:
    """Parse RSS 2.0 or Atom into [{title, link, published, source}]."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out = []
    for item in root.iter("item"):  # RSS
        out.append({
            "title": (item.findtext("title") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "published": (item.findtext("pubDate") or "").strip(),
            "source": source,
        })
    for entry in root.iter(f"{ATOM}entry"):  # Atom (YouTube channel feeds, many blogs)
        link_el = entry.find(f"{ATOM}link")
        group = entry.find(f"{MEDIA}group")
        views = None
        if group is not None:
            stats = group.find(f"{MEDIA}community/{MEDIA}statistics")
            if stats is not None:
                views = stats.get("views")
        out.append({
            "title": (entry.findtext(f"{ATOM}title") or "").strip(),
            "link": link_el.get("href", "") if link_el is not None else "",
            "published": (entry.findtext(f"{ATOM}published") or "").strip(),
            "source": source,
            **({"views": views} if views else {}),
        })
    return [x for x in out if x["title"]]


def google_news_url(keyword: str, region: dict) -> str:
    q = urllib.parse.quote(keyword)
    hl = region.get("hl", "en-US")
    gl = region.get("gl", "US")
    ceid = region.get("ceid", f"{gl}:{hl.split('-')[0]}")
    return f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"


def gather(cfg: Config, fetch=None) -> list[dict]:
    fetch = fetch or (lambda url: requests.get(url, headers=UA, timeout=20).text)
    research = cfg.section("research")
    region = research.get("news_region") or {}
    feeds: list[tuple[str, str]] = []
    for kw in research.get("keywords") or []:
        feeds.append((google_news_url(kw, region), f"news:{kw}"))
    for channel_id in research.get("competitor_youtube_channel_ids") or []:
        feeds.append((f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}", f"youtube:{channel_id}"))
    for url in research.get("rss_feeds") or []:
        feeds.append((url, f"rss:{urllib.parse.urlparse(url).netloc}"))

    seen, items = set(), []
    for url, source in feeds:
        try:
            entries = parse_feed(fetch(url), source)
        except requests.RequestException:
            continue  # one broken feed never stops the run
        for e in entries[:12]:
            key = e["title"].lower()
            if key not in seen:
                seen.add(key)
                items.append(e)
    return items[:80]


def run_research(cfg: Config, db: DB, llm, fetch=None) -> dict:
    items = gather(cfg, fetch)
    headlines = "\n".join(
        f"- [{i['source']}] {i['title']}" + (f" ({i['views']} views)" if i.get("views") else "")
        for i in items
    ) or "(no headlines found today; use evergreen knowledge of the niche)"
    pillars = ", ".join(p["name"] for p in cfg.brand.get("pillars") or [])
    prompt = f"""Here is today's raw market scan (news for our keywords, competitors' latest YouTube videos, industry feeds):

{headlines}

Write a short research brief for our content strategist:
1. trends: up to 5 topics our audience cares about right now, why now, and the angle WE should take.
2. competitor_notes: up to 5 observations about what competitors are publishing (formats, hooks, gaps we can fill).
3. content_ideas: 8 concrete post ideas, each tied to one of our content pillars ({pillars}), with a scroll-stopping hook.
Ignore headlines that are irrelevant to our audience."""
    brief = llm.complete_json(system_prompt(cfg, "market research analyst"), prompt, BRIEF_SCHEMA)
    brief["source_count"] = len(items)
    db.add_research(brief)
    db.log("research", detail={"headlines": len(items), "ideas": len(brief.get("content_ideas", []))})
    return brief
