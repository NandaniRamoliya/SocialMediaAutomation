"""Strategist: turns the posting schedule + research into a dated content calendar.

Posting slots are computed in code (deterministic: which platforms post on which weekday,
at what local time). The LLM only chooses what to say in each slot.
One calendar item = one idea for one day, adapted later for every platform posting that day.
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta

from ..brand import system_prompt
from ..config import WEEKDAYS, Config, iso
from ..db import DB


def platforms_for_day(cfg: Config, day: date) -> list[str]:
    wd = WEEKDAYS[day.weekday()]
    return [name for name, conf in cfg.platforms.items()
            if wd in [d.lower()[:3] for d in conf.get("days") or WEEKDAYS]]


def slot_time(cfg: Config, platform: str, day: date) -> datetime:
    hh, mm = (cfg.platforms[platform].get("time") or "10:00").split(":")
    return datetime.combine(day, time(int(hh), int(mm)), tzinfo=cfg.tz)


def open_days(cfg: Config, db: DB, now: datetime) -> list[date]:
    """Days in the planning window that have posting slots but no calendar item yet."""
    days_ahead = int(cfg.setting("planning", "plan_days", 14))
    today = cfg.local(now).date()
    taken = db.item_days()
    out = []
    for offset in range(days_ahead):
        day = today + timedelta(days=offset)
        plats = platforms_for_day(cfg, day)
        if not plats or day.isoformat() in taken:
            continue
        # Skip today if every slot has already passed.
        if offset == 0 and all(slot_time(cfg, p, day) <= cfg.local(now) for p in plats):
            continue
        out.append(day)
    return out


def _pillar_plan(cfg: Config, n: int) -> list[str]:
    """Spread pillars over n slots according to their weights (largest remainder)."""
    pillars = cfg.brand.get("pillars") or [{"name": "General", "weight": 1}]
    total = sum(float(p.get("weight", 1)) for p in pillars)
    counts = {p["name"]: int(n * float(p.get("weight", 1)) / total) for p in pillars}
    rest = n - sum(counts.values())
    by_remainder = sorted(pillars, key=lambda p: (n * float(p.get("weight", 1)) / total) % 1, reverse=True)
    for p in by_remainder[:rest]:
        counts[p["name"]] += 1
    seq: list[str] = []
    order = [p["name"] for p in pillars]
    while len(seq) < n:  # most-remaining first, never the same pillar twice in a row (if avoidable)
        choices = sorted((name for name in order if counts[name] > 0),
                         key=lambda name: (-counts[name], order.index(name)))
        pick = next((c for c in choices if not seq or c != seq[-1]), choices[0])
        seq.append(pick)
        counts[pick] -= 1
    return seq


def plan(cfg: Config, db: DB, llm, now: datetime) -> list[str]:
    days = open_days(cfg, db, now)
    if not days:
        return []
    pillars = _pillar_plan(cfg, len(days))
    research = db.latest_research() or {}
    research.pop("_created_at", None)
    slots = [{"day": d.isoformat(), "weekday": d.strftime("%A"), "pillar": pillars[i],
              "platforms": platforms_for_day(cfg, d)} for i, d in enumerate(days)]
    pillar_desc = "\n".join(f"- {p['name']}: {p.get('description', '')}" for p in cfg.brand.get("pillars") or [])
    events = cfg.setting("planning", "key_dates") or []
    formats = cfg.setting("planning", "formats") or ["single image post with caption"]
    schema = {
        "type": "object",
        "properties": {"items": {"type": "array", "minItems": len(slots), "maxItems": len(slots), "items": {
            "type": "object",
            "properties": {"day": {"type": "string"}, "pillar": {"type": "string"}, "topic": {"type": "string"},
                           "hook": {"type": "string"}, "angle": {"type": "string"}},
            "required": ["day", "pillar", "topic", "hook", "angle"]}}},
        "required": ["items"],
    }
    prompt = f"""Plan our content calendar. Fill EVERY slot below, in the same order, keeping its day and pillar.

Content pillars:
{pillar_desc}

Slots:
{json.dumps(slots, indent=1)}

Key dates / campaigns to use when they fall in this window:
{json.dumps(events, ensure_ascii=False) if events else '(none)'}

Latest research brief:
{json.dumps(research, ensure_ascii=False)[:6000] if research else '(none yet: use evergreen topics)'}

Topics we already covered recently (do NOT repeat them):
{json.dumps(db.recent_topics(), ensure_ascii=False)}

For each slot give: topic (specific, not generic), hook (the first line that stops the scroll, max 12 words),
angle (2-3 sentences on what the post says and the takeaway). Keep it varied across the week.
Formats we can produce right now: {', '.join(formats)}. Plan ONLY these formats (no carousels, reels or videos
unless they are listed), and don't write the format name into the topic."""
    result = llm.complete_json(system_prompt(cfg, "content strategist"), prompt, schema)
    created = []
    planned = result.get("items") or []
    for slot, entry in zip(slots, planned):
        created.append(db.add_item(slot["day"], slot["pillar"], entry.get("topic", ""),
                                   entry.get("hook", ""), entry.get("angle", "")))
    db.log("plan", detail={"days": [s["day"] for s in slots], "created": len(created)})
    return created


def schedule_for(cfg: Config, day_str: str) -> dict[str, str]:
    """{platform: scheduled_at (UTC ISO)} for a calendar day."""
    day = date.fromisoformat(day_str)
    return {p: iso(slot_time(cfg, p, day)) for p in platforms_for_day(cfg, day)}
