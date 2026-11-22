from __future__ import annotations

from ..config import Config
from ..db import DB
from .base import DryRunPublisher, NotConfigured, Post, PublishError, Publisher, Result
from .linkedin import LinkedInPublisher
from .meta import FacebookPublisher, InstagramPublisher, ThreadsPublisher
from .x import XPublisher
from .youtube import YouTubePublisher

REGISTRY: dict[str, type[Publisher]] = {
    "facebook": FacebookPublisher,
    "instagram": InstagramPublisher,
    "threads": ThreadsPublisher,
    "linkedin": LinkedInPublisher,
    "x": XPublisher,
    "youtube": YouTubePublisher,
}


def get_publisher(cfg: Config, db: DB, platform: str) -> Publisher:
    if cfg.dry_run:
        return DryRunPublisher(cfg, db, platform)
    return REGISTRY[platform](cfg, db)


__all__ = ["get_publisher", "Post", "Result", "PublishError", "NotConfigured", "REGISTRY"]
