"""YouTube Data API v3 (free: 10,000 quota units/day, an upload costs ~1,600 -> ~6 uploads/day).

Until the Google Cloud project passes YouTube's (free) API audit, uploads from it are locked to
private. Set the OAuth consent screen to "In production" or the refresh token expires in 7 days.
Wired in now; it is used once the video pipeline (next phase) produces videos.
"""
from __future__ import annotations

import json

from ..config import env
from .base import NotConfigured, Post, PublishError, Publisher, Result


class YouTubePublisher(Publisher):
    platform = "youtube"
    required_env = ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")

    def access_token(self) -> str:
        if self.missing():
            raise NotConfigured(f"missing {', '.join(self.missing())}")
        data = self.http("POST", "https://oauth2.googleapis.com/token", data={
            "client_id": env("YT_CLIENT_ID"), "client_secret": env("YT_CLIENT_SECRET"),
            "refresh_token": env("YT_REFRESH_TOKEN"), "grant_type": "refresh_token",
        }).json()
        return data["access_token"]

    def publish(self, post: Post) -> Result:
        if not post.video_path or not post.video_path.exists():
            raise PublishError("YouTube needs a video file (video pipeline not enabled yet)")
        token = self.access_token()
        size = post.video_path.stat().st_size
        meta = {
            "snippet": {"title": (post.title or post.text[:90])[:100], "description": post.text[:5000],
                        "categoryId": env("YT_CATEGORY_ID") or "22"},
            "status": {"privacyStatus": env("YT_PRIVACY") or "public", "selfDeclaredMadeForKids": False},
        }
        init = self.http(
            "POST", "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                     "X-Upload-Content-Type": "video/*", "X-Upload-Content-Length": str(size)},
            data=json.dumps(meta),
        )
        with open(post.video_path, "rb") as fh:
            video = self.http("PUT", init.headers["Location"], data=fh, timeout=1800,
                              headers={"Authorization": f"Bearer {token}", "Content-Type": "video/*"}).json()
        return Result(remote_id=video["id"], url=f"https://youtu.be/{video['id']}")
