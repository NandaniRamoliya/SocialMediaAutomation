"""Telegram bot: the only place a human touches the system.

Free, works from any phone. The bot sends each post's preview with buttons:
  ✅ Approve   🔁 Regenerate   ❌ Reject
Reply to any preview message with your changes and it is rewritten with your note.
Commands: /status  /queue  /pause (kill switch)  /resume  /plan  /help

We poll getUpdates on each scheduled run (no server/webhook needed, so $0). Telegram keeps
unread updates for 24 hours, which is far more than the hourly run interval.
"""
from __future__ import annotations

import html
from pathlib import Path

import requests

from ..config import Config, env


class Telegram:
    def __init__(self, cfg: Config, token: str, chat_id: str):
        self.cfg, self.token, self.chat_id = cfg, token, str(chat_id)
        self.base = f"https://api.telegram.org/bot{token}"

    @classmethod
    def from_env(cls, cfg: Config) -> "Telegram | None":
        token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
        return cls(cfg, token, chat) if token and chat else None

    def call(self, method: str, files=None, **params) -> dict:
        try:
            resp = requests.post(f"{self.base}/{method}", data=params if files else None,
                                 json=None if files else params, files=files, timeout=60)
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError(self.cfg.redact(f"telegram {method}: {exc}")) from None
        if not data.get("ok"):
            raise RuntimeError(self.cfg.redact(f"telegram {method}: {data.get('description')}"))
        return data["result"]

    def send_text(self, text: str, buttons: list[list[dict]] | None = None, html_mode: bool = True) -> int:
        params = {"chat_id": self.chat_id, "text": text[:4096], "disable_web_page_preview": True}
        if html_mode:
            params["parse_mode"] = "HTML"
        if buttons:
            params["reply_markup"] = {"inline_keyboard": buttons}
        return self.call("sendMessage", **params)["message_id"]

    def send_photo(self, photo: str | Path, caption: str) -> int:
        params = {"chat_id": self.chat_id, "caption": caption[:1024], "parse_mode": "HTML"}
        if isinstance(photo, Path) or (isinstance(photo, str) and not photo.startswith("http")):
            with open(photo, "rb") as fh:
                return self.call("sendPhoto", files={"photo": fh}, **params)["message_id"]
        return self.call("sendPhoto", photo=photo, **params)["message_id"]

    def get_updates(self, offset: int | None) -> list[dict]:
        params = {"timeout": 0, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            params["offset"] = offset
        return self.call("getUpdates", **params)

    def answer_callback(self, callback_id: str, text: str) -> None:
        try:
            self.call("answerCallbackQuery", callback_query_id=callback_id, text=text[:200])
        except RuntimeError:
            pass  # callbacks older than a few minutes can't be answered; harmless

    def clear_buttons(self, message_id: int) -> None:
        try:
            self.call("editMessageReplyMarkup", chat_id=self.chat_id, message_id=message_id,
                      reply_markup={"inline_keyboard": []})
        except RuntimeError:
            pass


def esc(text: str | None) -> str:
    return html.escape(text or "")


def approval_buttons(item_id: str) -> list[list[dict]]:
    return [[
        {"text": "✅ Approve", "callback_data": f"ap:{item_id}"},
        {"text": "🔁 Regenerate", "callback_data": f"rg:{item_id}"},
        {"text": "❌ Reject", "callback_data": f"rj:{item_id}"},
    ]]
