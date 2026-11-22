"""LinkedIn Posts API (free).

Personal profile: self-serve products "Sign In with LinkedIn using OpenID Connect" + "Share on LinkedIn"
(scope w_member_social), author urn:li:person:<id>.
Company page: needs the (free) Community Management API approval, author urn:li:organization:<id>.

Access tokens last 60 days and self-serve apps get no refresh token, so a human re-authorises
every ~60 days. The orchestrator reminds you on Telegram 7 days before LINKEDIN_TOKEN_EXPIRES.
"""
from __future__ import annotations

import re

from ..config import env
from .base import NotConfigured, Post, Publisher, Result
from .meta import image_bytes

# LinkedIn "little text" format: these characters must be backslash-escaped in commentary,
# otherwise the post is cut off or rejected.
_RESERVED = re.compile(r"([\\|{}@\[\]()<>#*_~])")


def escape_commentary(text: str) -> str:
    return _RESERVED.sub(r"\\\1", text)


class LinkedInPublisher(Publisher):
    platform = "linkedin"
    required_env = ("LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AUTHOR_URN")
    BASE = "https://api.linkedin.com/rest"

    def headers(self, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "LinkedIn-Version": env("LINKEDIN_VERSION") or "202510",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

    def upload_image(self, token: str, author: str, data: bytes) -> str:
        init = self.http("POST", f"{self.BASE}/images?action=initializeUpload", headers=self.headers(token),
                         json={"initializeUploadRequest": {"owner": author}}).json()["value"]
        self.http("PUT", init["uploadUrl"], data=data, headers={"Authorization": f"Bearer {token}"})
        return init["image"]

    def publish(self, post: Post) -> Result:
        token, author = env("LINKEDIN_ACCESS_TOKEN"), env("LINKEDIN_AUTHOR_URN")
        if not token or not author:
            raise NotConfigured("LINKEDIN_ACCESS_TOKEN / LINKEDIN_AUTHOR_URN not set")
        body = {
            "author": author,
            "commentary": escape_commentary(post.text),
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                             "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        if post.image_path or post.image_url:
            image_urn = self.upload_image(token, author, image_bytes(post))
            body["content"] = {"media": {"id": image_urn, **({"altText": post.alt_text} if post.alt_text else {})}}
        resp = self.http("POST", f"{self.BASE}/posts", headers=self.headers(token), json=body)
        urn = resp.headers.get("x-restli-id") or resp.headers.get("x-linkedin-id") or ""
        return Result(remote_id=urn, url=f"https://www.linkedin.com/feed/update/{urn}/" if urn else None)
