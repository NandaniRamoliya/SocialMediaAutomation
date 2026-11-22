"""Configuration: brand file (brand/brand.yaml) + environment variables (secrets).

Secrets are only ever read from the environment (GitHub Actions secrets in production,
a local `.env` file in development). They are never written to the database or logs.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
PLATFORMS = ("instagram", "facebook", "linkedin", "threads", "x", "youtube")
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# Every env var that holds a secret. Used to redact them from error messages.
SECRET_ENV_VARS = (
    "TELEGRAM_BOT_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "GEMINI_API_KEY", "DATABASE_URL",
    "IMGBB_API_KEY", "SUPABASE_SERVICE_KEY", "META_PAGE_TOKEN", "IG_ACCESS_TOKEN",
    "THREADS_ACCESS_TOKEN", "LINKEDIN_ACCESS_TOKEN", "X_API_KEY", "X_API_SECRET",
    "X_ACCESS_TOKEN", "X_ACCESS_SECRET", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN",
)


def load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE lines). Existing env vars win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def env_bool(name: str, default: bool = False) -> bool:
    value = env(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class Config:
    def __init__(self, brand_path: str | Path | None = None, brand: dict | None = None):
        load_dotenv(ROOT / ".env")
        self.brand_path = Path(brand_path or env("SMM_BRAND_FILE") or ROOT / "brand" / "brand.yaml")
        if brand is not None:
            self.brand = brand
        else:
            with open(self.brand_path, encoding="utf-8") as fh:
                self.brand = yaml.safe_load(fh) or {}
        self.data_dir = Path(env("SMM_DATA_DIR") or ROOT / "data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.database_url = env("DATABASE_URL") or f"sqlite:///{self.data_dir / 'smm.db'}"
        # Safety first: nothing is really posted until SMM_DRY_RUN=false is set explicitly.
        self.dry_run = env_bool("SMM_DRY_RUN", True)
        self.tz = ZoneInfo(self.brand.get("timezone") or "UTC")

    # ---- brand helpers -------------------------------------------------
    def section(self, name: str) -> dict:
        return self.brand.get(name) or {}

    @property
    def platforms(self) -> dict[str, dict]:
        """Enabled platforms and their settings."""
        out = {}
        for name, conf in (self.brand.get("platforms") or {}).items():
            if name in PLATFORMS and conf and conf.get("enabled"):
                out[name] = conf
        return out

    def setting(self, section: str, key: str, default=None):
        return self.section(section).get(key, default)

    # ---- time helpers --------------------------------------------------
    def now(self) -> datetime:
        fake = env("SMM_FAKE_NOW")  # for tests / manual simulation
        if fake:
            return datetime.fromisoformat(fake).astimezone(timezone.utc)
        return datetime.now(timezone.utc)

    def local(self, dt: datetime) -> datetime:
        return dt.astimezone(self.tz)

    # ---- secrets -------------------------------------------------------
    def redact(self, text: str) -> str:
        for name in SECRET_ENV_VARS:
            value = os.environ.get(name)
            if value and len(value) >= 6:
                text = text.replace(value, f"<{name}>")
        return text


def iso(dt: datetime) -> str:
    """UTC ISO string with fixed format so string comparison == time comparison."""
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()
