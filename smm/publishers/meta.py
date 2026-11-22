"""Facebook Page, Instagram (Business/Creator) and Threads: all free Meta APIs.

For your own accounts, a Meta app in Development mode works without App Review as long as
you (the account owner) have a role on the app. See docs/SETUP_FREE.md.
"""
from __future__ import annotations

import time

from ..config import env
from ..media_host import fetch_bytes
from .base import NotConfigured, Post, PublishError, Publisher, Result


def graph_version() -> str:
    return env("META_GRAPH_VERSION") or "v24.0"


class FacebookPublisher(Publisher):
    platform = "facebook"
    required_env = ("META_PAGE_ID", "META_PAGE_TOKEN")

    def publish(self, post: Post) -> Result:
        page, token = env("META_PAGE_ID"), env("META_PAGE_TOKEN")
        if not page or not token:
            raise NotConfigured("META_PAGE_ID / META_PAGE_TOKEN not set")
        base = f"https://graph.facebook.com/{graph_version()}/{page}"
        if post.image_url:
            data = self.http("POST", f"{base}/photos",
                             data={"url": post.image_url, "caption": post.text, "access_token": token}).json()
        elif post.image_path:
            with open(post.image_path, "rb") as fh:
                data = self.http("POST", f"{base}/photos", files={"source": fh},
                                 data={"caption": post.text, "access_token": token}).json()
        else:
            data = self.http("POST", f"{base}/feed", data={"message": post.text, "access_token": token}).json()
        post_id = data.get("post_id") or data.get("id")
        return Result(remote_id=post_id, url=f"https://www.facebook.com/{post_id}")


class InstagramPublisher(Publisher):
    platform = "instagram"
    required_env = ("IG_USER_ID",)

    def publish(self, post: Post) -> Result:
        user = env("IG_USER_ID")
        token = env("IG_ACCESS_TOKEN") or env("META_PAGE_TOKEN")
        if not user or not token:
            raise NotConfigured("IG_USER_ID and IG_ACCESS_TOKEN (or META_PAGE_TOKEN) not set")
        if not post.image_url:
            raise PublishError("Instagram needs a public image URL: set MEDIA_HOST (see docs/SETUP_FREE.md)")
        host = env("IG_GRAPH_HOST") or "graph.facebook.com"  # graph.instagram.com for Instagram Login tokens
        base = f"https://{host}/{graph_version()}"
        container = self.http("POST", f"{base}/{user}/media", data={
            "image_url": post.image_url, "caption": post.text, "access_token": token,
            **({"alt_text": post.alt_text} if post.alt_text else {}),
        }).json()["id"]
        for _ in range(20):  # wait until Instagram has fetched and processed the image
            status = self.http("GET", f"{base}/{container}",
                               params={"fields": "status_code", "access_token": token}).json()
            code = status.get("status_code")
            if code == "FINISHED":
                break
            if code in ("ERROR", "EXPIRED"):
                raise PublishError(f"instagram container {code}")
            time.sleep(3)
        media_id = self.http("POST", f"{base}/{user}/media_publish",
                             data={"creation_id": container, "access_token": token}).json()["id"]
        try:
            link = self.http("GET", f"{base}/{media_id}",
                             params={"fields": "permalink", "access_token": token}).json().get("permalink")
        except PublishError:
            link = None
        return Result(remote_id=media_id, url=link)


class ThreadsPublisher(Publisher):
    platform = "threads"
    required_env = ("THREADS_USER_ID", "THREADS_ACCESS_TOKEN")
    BASE = "https://graph.threads.net/v1.0"

    def token(self) -> str | None:
        # A refreshed token (stored by refresh_token()) wins over the original env value.
        return self.db.get_setting("threads_access_token") or env("THREADS_ACCESS_TOKEN")

    def publish(self, post: Post) -> Result:
        user, token = env("THREADS_USER_ID"), self.token()
        if not user or not token:
            raise NotConfigured("THREADS_USER_ID / THREADS_ACCESS_TOKEN not set")
        payload = {"text": post.text, "access_token": token}
        if post.image_url:
            payload.update(media_type="IMAGE", image_url=post.image_url)
        else:
            payload["media_type"] = "TEXT"
        container = self.http("POST", f"{self.BASE}/{user}/threads", data=payload).json()["id"]
        if post.image_url:
            for _ in range(20):
                status = self.http("GET", f"{self.BASE}/{container}",
                                   params={"fields": "status", "access_token": token}).json().get("status")
                if status == "FINISHED":
                    break
                if status in ("ERROR", "EXPIRED"):
                    raise PublishError(f"threads container {status}")
                time.sleep(3)
        else:
            time.sleep(2)
        media_id = self.http("POST", f"{self.BASE}/{user}/threads_publish",
                             data={"creation_id": container, "access_token": token}).json()["id"]
        try:
            link = self.http("GET", f"{self.BASE}/{media_id}",
                             params={"fields": "permalink", "access_token": token}).json().get("permalink")
        except PublishError:
            link = None
        return Result(remote_id=media_id, url=link)

    def refresh_token(self) -> bool:
        """Long-lived Threads tokens last 60 days and can be refreshed for free, no human needed."""
        token = self.token()
        if not token:
            return False
        data = self.http("GET", "https://graph.threads.net/refresh_access_token",
                         params={"grant_type": "th_refresh_token", "access_token": token}).json()
        if data.get("access_token"):
            self.db.set_setting("threads_access_token", data["access_token"])
            return True
        return False


def image_bytes(post: Post) -> bytes:
    if post.image_path and post.image_path.exists():
        return post.image_path.read_bytes()
    if post.image_url:
        return fetch_bytes(post.image_url)
    raise PublishError("no image available")
