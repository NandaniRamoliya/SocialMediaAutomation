from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import requests

from ..config import Config
from ..db import DB


class PublishError(RuntimeError):
    pass


class NotConfigured(PublishError):
    pass


@dataclass
class Post:
    text: str
    title: str | None = None
    image_path: Path | None = None
    image_url: str | None = None
    video_path: Path | None = None
    alt_text: str | None = None


@dataclass
class Result:
    remote_id: str
    url: str | None = None


class Publisher:
    platform = "base"
    required_env: tuple[str, ...] = ()

    def __init__(self, cfg: Config, db: DB):
        self.cfg, self.db = cfg, db

    def missing(self) -> list[str]:
        from ..config import env
        return [name for name in self.required_env if not env(name)]

    def publish(self, post: Post) -> Result:  # pragma: no cover - interface
        raise NotImplementedError

    # Shared HTTP helper: raises PublishError with secrets redacted.
    def http(self, method: str, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", 120)
        try:
            resp = requests.request(method, url, **kwargs)
        except requests.RequestException as exc:
            raise PublishError(self.cfg.redact(f"{self.platform}: network error {exc}")) from None
        if resp.status_code >= 400:
            raise PublishError(self.cfg.redact(f"{self.platform} HTTP {resp.status_code}: {resp.text[:600]}"))
        return resp


class DryRunPublisher(Publisher):
    """Used when SMM_DRY_RUN=true (the default). Records what would be posted."""

    def __init__(self, cfg: Config, db: DB, platform: str):
        super().__init__(cfg, db)
        self.platform = platform

    def publish(self, post: Post) -> Result:
        self.db.log("dry_run_publish", detail={"platform": self.platform, "text": post.text[:500],
                                               "image": str(post.image_url or post.image_path or "")})
        return Result(remote_id=f"dry-run-{self.platform}", url=None)
