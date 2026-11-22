"""X (Twitter) API v2, free tier: posting only (write-only, small monthly cap).

Uses OAuth 1.0a user-context keys, which do not expire. Text posts only for now: media upload
on the free tier is limited, so the image card is not attached on X.
"""
from __future__ import annotations

from requests_oauthlib import OAuth1

from ..config import env
from .base import NotConfigured, Post, Publisher, Result


class XPublisher(Publisher):
    platform = "x"
    required_env = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")

    def publish(self, post: Post) -> Result:
        if self.missing():
            raise NotConfigured(f"missing {', '.join(self.missing())}")
        auth = OAuth1(env("X_API_KEY"), env("X_API_SECRET"), env("X_ACCESS_TOKEN"), env("X_ACCESS_SECRET"))
        data = self.http("POST", "https://api.x.com/2/tweets", auth=auth, json={"text": post.text}).json()
        tweet_id = data["data"]["id"]
        return Result(remote_id=tweet_id, url=f"https://x.com/i/web/status/{tweet_id}")
