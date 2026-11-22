"""Copywriter: one idea -> a native post for every platform (not one text pasted 6 times)."""
from __future__ import annotations

from ..brand import system_prompt
from ..config import Config

PLATFORM_GUIDE = {
    "instagram": "Instagram feed post (image + caption). First line = the hook. Short paragraphs with line breaks, "
                 "value in the middle, a comment-bait CTA at the end. {hashtags} relevant hashtags at the very end. "
                 "No links (they aren't clickable in captions); say 'link in bio' if needed. Max ~1,200 characters.",
    "facebook": "Facebook Page post (image + text). Conversational, 2-5 short paragraphs, a question to drive comments. "
                "{hashtags} hashtags max. A link to our website is allowed. Max ~1,000 characters.",
    "linkedin": "LinkedIn post. Professional but human, first-person-plural (we). Hook line, then white space, "
                "short lines, one clear insight or lesson, end with a question. {hashtags} hashtags at the end. "
                "No emojis-as-bullets overload. 600-1,500 characters.",
    "threads": "Threads post. Casual, punchy, conversational, like texting a smart friend. HARD LIMIT 450 characters. "
               "At most 1 hashtag (Threads uses one topic tag).",
    "x": "X (Twitter) post. One strong standalone tweet, HARD LIMIT 260 characters including hashtags and spaces. "
         "{hashtags} hashtags max. No thread numbering.",
    "youtube": "YouTube video metadata. 'title' (max 70 characters, curiosity + keyword) and 'text' = description "
               "(first 2 lines hook + keyword, then summary, then CTA to subscribe, then 3 hashtags).",
}


def guide_for(cfg: Config, platform: str) -> str:
    tags = (cfg.platforms.get(platform) or {}).get("hashtags", 3)
    return PLATFORM_GUIDE[platform].replace("{hashtags}", str(tags))


def schema_for(platforms: list[str]) -> dict:
    variant = {"type": "object", "properties": {"text": {"type": "string"}, "title": {"type": "string"}},
               "required": ["text"]}
    return {
        "type": "object",
        "properties": {
            "card": {"type": "object", "properties": {
                "headline": {"type": "string"}, "subtext": {"type": "string"}},
                "required": ["headline", "subtext"]},
            "variants": {"type": "object", "properties": {p: variant for p in platforms}, "required": platforms},
        },
        "required": ["card", "variants"],
    }


def draft(cfg: Config, llm, item: dict, platforms: list[str], feedback: str | None = None) -> dict:
    guides = "\n".join(f"- {p}: {guide_for(cfg, p)}" for p in platforms)
    fix = f"\n\nIMPORTANT, a previous draft was rejected. Fix this:\n{feedback}\n" if feedback else ""
    prompt = f"""Write today's post.

Pillar: {item.get('pillar')}
Topic: {item.get('topic')}
Hook idea: {item.get('hook')}
Angle: {item.get('angle')}

1. card: the text for the post image. headline = max 8 words, huge and punchy. subtext = max 18 words.
2. variants: write a separate, native version for each platform, following its rules exactly:
{guides}{fix}"""
    return llm.complete_json(system_prompt(cfg, "senior copywriter"), prompt, schema_for(platforms))
