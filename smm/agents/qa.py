"""QA & Compliance: deterministic checks first (free, instant), then an optional LLM brand review."""
from __future__ import annotations

import difflib
import json
import re

from ..brand import system_prompt
from ..config import Config

LIMITS = {"x": 280, "threads": 500, "instagram": 2200, "linkedin": 3000, "facebook": 63206, "youtube": 5000}
URL_RE = re.compile(r"https?://\S+")
HASHTAG_RE = re.compile(r"(?<!\w)#\w+", re.UNICODE)
MENTION_RE = re.compile(r"(?<!\w)@\w+")
PLACEHOLDER_RE = re.compile(r"\[(insert|link|name|your)[^\]]*\]|\{\{.*?\}\}|\bTODO\b|lorem ipsum", re.I)


def x_weighted_length(text: str) -> int:
    """Approximation of X's weighted count: URLs = 23, CJK/emoji = 2, most other scripts = 1."""
    total = 0
    for url in URL_RE.findall(text):
        text = text.replace(url, "", 1)
        total += 23
    for ch in text:
        cp = ord(ch)
        light = cp <= 4351 or 8192 <= cp <= 8205 or 8208 <= cp <= 8223 or 8242 <= cp <= 8247
        total += 1 if light else 2
    return total


def check(cfg: Config, platform: str, text: str, title: str | None = None,
          recent: list[str] | None = None) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors block a platform; warnings are shown to the approver."""
    errors, warnings = [], []
    text = (text or "").strip()
    if not text:
        return ["empty post"], []
    length = x_weighted_length(text) if platform == "x" else len(text)
    if length > LIMITS[platform]:
        errors.append(f"too long for {platform}: {length}/{LIMITS[platform]} characters")
    if PLACEHOLDER_RE.search(text) or (title and PLACEHOLDER_RE.search(title)):
        errors.append("contains a placeholder")
    lowered = text.lower()
    for word in (cfg.section("rules").get("banned_words") or []):
        if word.lower() in lowered:
            errors.append(f"banned phrase: '{word}'")
    tags = HASHTAG_RE.findall(text)
    if platform == "instagram":
        if len(tags) > 30:
            errors.append(f"{len(tags)} hashtags (Instagram allows 30)")
        if len(MENTION_RE.findall(text)) > 20:
            errors.append("more than 20 @mentions")
        if URL_RE.search(text):
            warnings.append("link in Instagram caption is not clickable")
    if platform == "threads" and len(tags) > 1:
        warnings.append("Threads uses only one topic tag; extra hashtags show as plain text")
    wanted = (cfg.platforms.get(platform) or {}).get("hashtags")
    if wanted is not None and len(tags) > int(wanted) + 2:
        warnings.append(f"{len(tags)} hashtags (brand setting: {wanted})")
    if platform == "youtube":
        if not title:
            errors.append("YouTube needs a title")
        elif len(title) > 100:
            errors.append("YouTube title over 100 characters")
    for old in recent or []:
        if old and difflib.SequenceMatcher(None, old.lower(), lowered).ratio() > 0.85:
            errors.append("almost identical to a recent post")
            break
    return errors, warnings


REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 1, "maximum": 10},
        "issues": {"type": "array", "items": {"type": "string"}},
        "risk": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["score", "issues", "risk"],
}


def llm_review(cfg: Config, llm, item: dict, variants: dict) -> dict:
    prompt = f"""Review these drafts before they go to the approver. Be strict.

Topic: {item.get('topic')}
Drafts:
{json.dumps(variants, ensure_ascii=False, indent=1)}

Score 1-10 on: matches our voice, strong hook, clear value, native to each platform, no made-up facts or claims,
no rule violations. List concrete issues (empty list if none). risk = high if anything could be legally risky,
offensive, a false claim, or about pricing/offers/competitors."""
    return llm.complete_json(system_prompt(cfg, "brand and compliance reviewer"), prompt, REVIEW_SCHEMA)
