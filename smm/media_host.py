"""Public image hosting (free). Instagram and Threads fetch images from a public URL, and
GitHub Actions runners are wiped between runs, so every generated image is uploaded once.

MEDIA_HOST=supabase  -> Supabase Storage public bucket (free tier, same account as the database)
MEDIA_HOST=imgbb     -> imgbb.com free API key
MEDIA_HOST unset     -> local file only (fine for dry runs / Facebook / LinkedIn)
"""
from __future__ import annotations

import base64
from pathlib import Path

import requests

from .config import Config, env


class MediaHostError(RuntimeError):
    pass


def upload_public(cfg: Config, path: Path) -> str | None:
    host = (env("MEDIA_HOST") or "").lower()
    if not host or cfg.dry_run and not env("MEDIA_UPLOAD_IN_DRY_RUN"):
        return None
    data = Path(path).read_bytes()
    if host == "imgbb":
        key = env("IMGBB_API_KEY")
        if not key:
            raise MediaHostError("IMGBB_API_KEY is not set")
        resp = requests.post("https://api.imgbb.com/1/upload", timeout=60,
                             data={"key": key, "image": base64.b64encode(data).decode()})
        if resp.status_code >= 400:
            raise MediaHostError(cfg.redact(f"imgbb {resp.status_code}: {resp.text[:300]}"))
        return resp.json()["data"]["url"]
    if host == "supabase":
        base, key = env("SUPABASE_URL"), env("SUPABASE_SERVICE_KEY")
        bucket = env("SUPABASE_BUCKET") or "media"
        if not base or not key:
            raise MediaHostError("SUPABASE_URL / SUPABASE_SERVICE_KEY are not set")
        name = Path(path).name
        resp = requests.post(
            f"{base.rstrip('/')}/storage/v1/object/{bucket}/{name}", data=data, timeout=60,
            headers={"apikey": key, "Content-Type": "image/png", "x-upsert": "true",
                     # legacy service_role keys are JWTs ("eyJ..."); new sb_secret_ keys go in apikey only
                     **({"Authorization": f"Bearer {key}"} if key.startswith("eyJ") else {})},
        )
        if resp.status_code >= 400:
            raise MediaHostError(cfg.redact(f"supabase {resp.status_code}: {resp.text[:300]}"))
        return f"{base.rstrip('/')}/storage/v1/object/public/{bucket}/{name}"
    raise MediaHostError(f"Unknown MEDIA_HOST: {host}")


def fetch_bytes(url: str) -> bytes:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content
