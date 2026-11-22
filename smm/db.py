"""Storage. SQLite locally, Postgres (e.g. Supabase free tier) in production.

Plain SQL that works on both: TEXT ids generated in Python, ISO-8601 UTC timestamps,
JSON stored as TEXT. `?` placeholders are converted to `%s` for Postgres.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS research (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        brief TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY,
        day TEXT NOT NULL,
        pillar TEXT,
        topic TEXT,
        hook TEXT,
        angle TEXT,
        status TEXT NOT NULL,
        feedback TEXT,
        qa_notes TEXT,
        card TEXT,
        media_path TEXT,
        media_url TEXT,
        tg_msg_ids TEXT,
        attempts INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS variants (
        id TEXT PRIMARY KEY,
        item_id TEXT NOT NULL,
        platform TEXT NOT NULL,
        text TEXT,
        title TEXT,
        scheduled_at TEXT,
        status TEXT NOT NULL,
        issues TEXT,
        attempts INTEGER DEFAULT 0,
        remote_id TEXT,
        remote_url TEXT,
        error TEXT,
        published_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        at TEXT NOT NULL,
        kind TEXT NOT NULL,
        item_id TEXT,
        detail TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_items_status ON items(status)",
    "CREATE INDEX IF NOT EXISTS idx_variants_item ON variants(item_id)",
]

# Item lifecycle
PLANNED = "planned"              # topic picked by the strategist
REDRAFT = "redraft"              # approver asked for changes
AWAITING = "awaiting_approval"   # drafted, QA'd, sent to the approver
APPROVED = "approved"
REJECTED = "rejected"
EXPIRED = "expired"              # not approved before its slot -> skipped, never posted
PUBLISHED = "published"
PARTIAL = "partially_published"
NEEDS_ATTENTION = "needs_attention"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class DB:
    def __init__(self, url: str):
        self.url = url
        if url.startswith("sqlite:///"):
            path = url[len("sqlite:///"):]
            if path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(path)
            self.conn.row_factory = sqlite3.Row
            self.kind = "sqlite"
        elif url.startswith(("postgres://", "postgresql://")):
            import psycopg  # installed only where needed: pip install "psycopg[binary]"
            from psycopg.rows import dict_row

            self.conn = psycopg.connect(url, autocommit=True, row_factory=dict_row)
            self.kind = "postgres"
        else:
            raise ValueError("DATABASE_URL must start with sqlite:/// or postgresql://")
        for stmt in SCHEMA:
            self.execute(stmt)

    # ---- low level -----------------------------------------------------
    def execute(self, sql: str, params: tuple | list = ()):
        if self.kind == "postgres":
            sql = sql.replace("?", "%s")
        cur = self.conn.cursor()
        cur.execute(sql, tuple(params))
        if self.kind == "sqlite":
            self.conn.commit()
        return cur

    def query(self, sql: str, params: tuple | list = ()) -> list[dict]:
        return [dict(r) for r in self.execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple | list = ()) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    # ---- settings (key/value state, e.g. paused flag, telegram offset) --
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.one("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    # ---- audit log -----------------------------------------------------
    def log(self, kind: str, item_id: str | None = None, detail: str | dict = "") -> None:
        if isinstance(detail, (dict, list)):
            detail = json.dumps(detail, ensure_ascii=False)
        self.execute(
            "INSERT INTO events (id, at, kind, item_id, detail) VALUES (?, ?, ?, ?, ?)",
            (new_id(), now_iso(), kind, item_id, detail[:4000]),
        )

    # ---- research ------------------------------------------------------
    def add_research(self, brief: dict) -> None:
        self.execute(
            "INSERT INTO research (id, created_at, brief) VALUES (?, ?, ?)",
            (new_id(), now_iso(), json.dumps(brief, ensure_ascii=False)),
        )

    def latest_research(self) -> dict | None:
        row = self.one("SELECT brief, created_at FROM research ORDER BY created_at DESC LIMIT 1")
        if not row:
            return None
        brief = json.loads(row["brief"])
        brief["_created_at"] = row["created_at"]
        return brief

    # ---- items ---------------------------------------------------------
    def add_item(self, day: str, pillar: str, topic: str, hook: str, angle: str) -> str:
        item_id = new_id()
        ts = now_iso()
        self.execute(
            "INSERT INTO items (id, day, pillar, topic, hook, angle, status, attempts, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)",
            (item_id, day, pillar, topic, hook, angle, PLANNED, ts, ts),
        )
        return item_id

    def update_item(self, item_id: str, **fields) -> None:
        if not fields:
            return
        fields["updated_at"] = now_iso()
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.execute(f"UPDATE items SET {cols} WHERE id = ?", (*fields.values(), item_id))

    def item(self, item_id: str) -> dict | None:
        return self.one("SELECT * FROM items WHERE id = ?", (item_id,))

    def items(self, *statuses: str) -> list[dict]:
        if not statuses:
            return self.query("SELECT * FROM items ORDER BY day")
        marks = ", ".join("?" for _ in statuses)
        return self.query(f"SELECT * FROM items WHERE status IN ({marks}) ORDER BY day", statuses)

    def item_days(self) -> set[str]:
        return {r["day"] for r in self.query("SELECT day FROM items")}

    def find_item_by_tg_message(self, message_id: int) -> dict | None:
        for row in self.query("SELECT * FROM items WHERE tg_msg_ids IS NOT NULL"):
            if message_id in json.loads(row["tg_msg_ids"] or "[]"):
                return row
        return None

    # ---- variants ------------------------------------------------------
    def replace_variants(self, item_id: str, variants: list[dict]) -> None:
        self.execute("DELETE FROM variants WHERE item_id = ?", (item_id,))
        for v in variants:
            self.execute(
                "INSERT INTO variants (id, item_id, platform, text, title, scheduled_at, status, issues, attempts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (new_id(), item_id, v["platform"], v.get("text"), v.get("title"), v.get("scheduled_at"),
                 v.get("status", "draft"), json.dumps(v.get("issues", []), ensure_ascii=False)),
            )

    def variants(self, item_id: str) -> list[dict]:
        return self.query("SELECT * FROM variants WHERE item_id = ? ORDER BY scheduled_at", (item_id,))

    def update_variant(self, variant_id: str, **fields) -> None:
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.execute(f"UPDATE variants SET {cols} WHERE id = ?", (*fields.values(), variant_id))

    def recent_published_texts(self, platform: str, limit: int = 50) -> list[str]:
        rows = self.query(
            "SELECT text FROM variants WHERE platform = ? AND status = 'published' "
            "ORDER BY published_at DESC LIMIT ?",
            (platform, limit),
        )
        return [r["text"] or "" for r in rows]

    def recent_topics(self, limit: int = 40) -> list[str]:
        rows = self.query("SELECT topic FROM items ORDER BY day DESC LIMIT ?", (limit,))
        return [r["topic"] for r in rows if r["topic"]]
