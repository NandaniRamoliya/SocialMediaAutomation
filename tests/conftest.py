import copy
import os
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from smm.config import Config  # noqa: E402
from smm.db import DB  # noqa: E402

BRAND = yaml.safe_load((ROOT / "brand" / "brand.yaml").read_text())


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for key in list(os.environ):
        if key.startswith(("SMM_", "TELEGRAM_", "META_", "IG_", "THREADS_", "LINKEDIN_", "X_", "YT_",
                           "MEDIA_", "LLM_", "GEMINI_", "DATABASE_URL", "SUPABASE_", "IMGBB_")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SMM_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SMM_DRY_RUN", "true")


@pytest.fixture
def cfg():
    return Config(brand=copy.deepcopy(BRAND))


@pytest.fixture
def db(cfg):
    return DB("sqlite:///:memory:")


class FakeTelegram:
    chat_id = "42"

    def __init__(self):
        self.sent, self.updates, self.next_id = [], [], 100

    def _id(self):
        self.next_id += 1
        return self.next_id

    def send_text(self, text, buttons=None, html_mode=True):
        mid = self._id()
        self.sent.append({"id": mid, "text": text, "buttons": buttons})
        return mid

    def send_photo(self, photo, caption):
        mid = self._id()
        self.sent.append({"id": mid, "photo": str(photo), "text": caption})
        return mid

    def get_updates(self, offset):
        out = [u for u in self.updates if offset is None or u["update_id"] >= offset]
        return out

    def answer_callback(self, cid, text):
        pass

    def clear_buttons(self, mid):
        pass


@pytest.fixture
def tg():
    return FakeTelegram()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import requests

    def blocked(*a, **k):
        raise requests.ConnectionError("network disabled in tests")

    monkeypatch.setattr("smm.agents.research.requests.get", blocked)
