"""Orchestrator: the "manager" that runs one cycle of the whole job.

Each scheduled run (hourly on GitHub Actions) does, in order:
 1. read approvals / commands from Telegram
 2. stop here if the kill switch is on
 3. skip (never post) anything that wasn't approved before its slot
 4. research (once a day)
 5. plan the calendar for open days (once a day)
 6. draft + QA + render images for upcoming items, send them for approval
 7. publish approved posts whose time has come
 8. housekeeping: token refresh, token-expiry reminders, weekly summary
Every step is isolated: one failure is logged and reported, the rest of the cycle still runs.
"""
from __future__ import annotations

import json
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

from . import db as S
from .agents import copywriter, qa
from .agents.research import run_research
from .agents.strategist import plan, schedule_for
from .approval.telegram import Telegram, approval_buttons, esc
from .config import Config, env, iso
from .creative import render_card
from .db import DB
from .llm import get_llm
from .media_host import upload_public
from .publishers import NotConfigured, Post, get_publisher
from .publishers.meta import ThreadsPublisher

TERMINAL = {"published", "failed", "blocked", "skipped"}
PLATFORM_LABEL = {"instagram": "Instagram", "facebook": "Facebook", "linkedin": "LinkedIn",
                  "threads": "Threads", "x": "X", "youtube": "YouTube"}


class Autopilot:
    def __init__(self, cfg: Config, db: DB, llm=None, telegram: Telegram | None = None,
                 publisher_factory=get_publisher):
        self.cfg, self.db = cfg, db
        self._llm = llm
        self.tg = telegram
        self.publisher_factory = publisher_factory
        self.report: list[str] = []

    # ---- utilities -----------------------------------------------------
    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm(self.cfg)
        return self._llm

    def notify(self, text: str, html_mode: bool = True) -> None:
        self.report.append(text)
        if self.tg:
            try:
                self.tg.send_text(text, html_mode=html_mode)
            except RuntimeError as exc:
                self.db.log("notify_error", detail=str(exc))

    @property
    def paused(self) -> bool:
        return self.db.get_setting("paused", "0") == "1" or env("SMM_PAUSED") in ("1", "true")

    def _step(self, name: str, fn, *args):
        try:
            return fn(*args)
        except Exception as exc:  # isolate failures per step
            detail = self.cfg.redact(f"{type(exc).__name__}: {exc}")
            self.db.log("error", detail={"step": name, "error": detail,
                                         "trace": self.cfg.redact(traceback.format_exc()[-1500:])})
            self.notify(f"⚠️ <b>{esc(name)}</b> failed: {esc(detail[:500])}")
            return None

    def _due(self, key: str, now: datetime, hours: float) -> bool:
        last = self.db.get_setting(key)
        return not last or datetime.fromisoformat(last) <= now - timedelta(hours=hours)

    # ---- the cycle -----------------------------------------------------
    def cycle(self) -> list[str]:
        now = self.cfg.now()
        self._step("approvals", self.poll_approvals)
        if self.paused:
            self.report.append("paused (kill switch on): nothing drafted or posted")
            return self.report
        self._step("expire", self.expire, now)
        self._step("research", self.maybe_research, now)
        self._step("plan", self.maybe_plan, now)
        self._step("draft", self.draft_due, now)
        self._step("publish", self.publish_due, now)
        self._step("housekeeping", self.housekeeping, now)
        return self.report

    # ---- 1. approvals --------------------------------------------------
    def poll_approvals(self) -> None:
        if not self.tg:
            return
        offset = self.db.get_setting("tg_offset")
        updates = self.tg.get_updates(int(offset) if offset else None)
        for upd in updates:
            self.db.set_setting("tg_offset", str(upd["update_id"] + 1))
            self.handle_update(upd)

    def handle_update(self, upd: dict) -> None:
        cb = upd.get("callback_query")
        if cb:
            if str((cb.get("message") or {}).get("chat", {}).get("id")) != self.tg.chat_id:
                return  # only the configured approver chat may control the bot
            action, _, item_id = (cb.get("data") or "").partition(":")
            reply = self.apply_decision(item_id, action, by=(cb.get("from") or {}).get("username"))
            self.tg.answer_callback(cb["id"], reply)
            if cb.get("message"):
                self.tg.clear_buttons(cb["message"]["message_id"])
            return
        msg = upd.get("message")
        if not msg or str(msg.get("chat", {}).get("id")) != self.tg.chat_id:
            return
        text = (msg.get("text") or "").strip()
        if text.startswith("/"):
            self.handle_command(text.split()[0].split("@")[0].lower())
            return
        replied = msg.get("reply_to_message")
        if replied and text:
            item = self.db.find_item_by_tg_message(replied["message_id"])
            if item and item["status"] in (S.AWAITING, S.NEEDS_ATTENTION, S.APPROVED):
                self.db.update_item(item["id"], status=S.REDRAFT, feedback=text)
                self.db.log("feedback", item["id"], text)
                self.notify(f"✍️ Got it. Rewriting <b>{esc(item['topic'])}</b> with your note.")

    def apply_decision(self, item_id: str, action: str, by: str | None = None) -> str:
        item = self.db.item(item_id)
        if not item:
            return "Unknown post"
        if item["status"] not in (S.AWAITING, S.NEEDS_ATTENTION):
            return f"Already {item['status']}"
        if action == "ap":
            self.db.update_item(item_id, status=S.APPROVED)
            self.db.log("approved", item_id, by or "")
            first = min((v["scheduled_at"] for v in self.db.variants(item_id) if v["status"] == "ready"), default=None)
            when = self.cfg.local(datetime.fromisoformat(first)).strftime("%a %d %b %H:%M") if first else "soon"
            self.notify(f"✅ Approved: <b>{esc(item['topic'])}</b>. Posting from {when}.")
            return "Approved"
        if action == "rj":
            self.db.update_item(item_id, status=S.REJECTED)
            self.db.log("rejected", item_id, by or "")
            self.notify(f"❌ Rejected: <b>{esc(item['topic'])}</b>. It won't be posted.")
            return "Rejected"
        if action == "rg":
            self.db.update_item(item_id, status=S.REDRAFT,
                                feedback="The approver wants a noticeably different, stronger version.")
            self.db.log("regenerate", item_id, by or "")
            return "Regenerating"
        return "Unknown action"

    def handle_command(self, cmd: str) -> None:
        if cmd == "/pause":
            self.db.set_setting("paused", "1")
            self.db.log("paused")
            self.notify("⏸ Kill switch ON. Nothing will be drafted or posted until /resume.")
        elif cmd == "/resume":
            self.db.set_setting("paused", "0")
            self.db.log("resumed")
            self.notify("▶️ Resumed. Back to work.")
        elif cmd == "/status":
            self.notify(self.status_text())
        elif cmd == "/queue":
            self.notify(self.queue_text())
        elif cmd == "/plan":
            self.db.set_setting("last_plan_at", "")
            self.notify("🗓 I'll refresh the calendar on the next run.")
        else:
            self.notify("Commands: /status /queue /pause /resume /plan\n"
                        "Reply to a preview with changes to get a rewrite.", html_mode=False)

    # ---- 3. expire -----------------------------------------------------
    def expire(self, now: datetime) -> None:
        now_s = iso(now)
        for item in self.db.items(S.PLANNED, S.REDRAFT, S.AWAITING, S.NEEDS_ATTENTION):
            times = [v["scheduled_at"] for v in self.db.variants(item["id"])] or \
                list(schedule_for(self.cfg, item["day"]).values())
            if times and min(times) <= now_s:
                self.db.update_item(item["id"], status=S.EXPIRED)
                self.db.log("expired", item["id"])
                if item["status"] != S.PLANNED:
                    self.notify(f"⌛ Not approved in time, skipped (never posted unapproved): "
                                f"<b>{esc(item['topic'])}</b>")

    # ---- 4/5. research + plan -------------------------------------------
    def maybe_research(self, now: datetime) -> None:
        if not self._due("last_research_at", now, 20):
            return
        brief = run_research(self.cfg, self.db, self.llm)
        self.db.set_setting("last_research_at", iso(now))
        self.report.append(f"research: {brief.get('source_count', 0)} headlines scanned")

    def maybe_plan(self, now: datetime) -> None:
        if not self._due("last_plan_at", now, 20):
            return
        created = plan(self.cfg, self.db, self.llm, now)
        self.db.set_setting("last_plan_at", iso(now))
        if created:
            self.report.append(f"planned {len(created)} new calendar days")

    # ---- 6. draft ------------------------------------------------------
    def draft_due(self, now: datetime) -> None:
        horizon = (self.cfg.local(now).date() + timedelta(days=int(self.cfg.setting("planning", "draft_days_ahead", 5)))).isoformat()
        limit = int(self.cfg.setting("planning", "max_drafts_per_run", 3))
        due = [i for i in self.db.items(S.REDRAFT, S.PLANNED) if i["day"] <= horizon]
        due.sort(key=lambda i: (i["status"] != S.REDRAFT, i["day"]))  # approver feedback first
        for item in due[:limit]:
            self._step(f"draft {item['day']}", self.draft_item, item)

    def draft_item(self, item: dict) -> None:
        schedule = schedule_for(self.cfg, item["day"])
        platforms = [p for p in schedule if p != "youtube"]  # YouTube waits for the video pipeline
        if not platforms:
            self.db.update_item(item["id"], status=S.EXPIRED)
            return
        feedback = item.get("feedback")
        use_review = bool(self.cfg.setting("qa", "llm_review", True))
        min_score = int(self.cfg.setting("qa", "min_score", 7))
        recent = {p: self.db.recent_published_texts(p) for p in platforms}
        out, errors, warnings, review = {}, {}, {}, None
        for attempt in range(2):  # one automatic rewrite if QA finds problems
            out = copywriter.draft(self.cfg, self.llm, item, platforms, feedback)
            variants = out.get("variants") or {}
            errors, warnings = {}, {}
            for p in platforms:
                v = variants.get(p) or {}
                errors[p], warnings[p] = qa.check(self.cfg, p, v.get("text", ""), v.get("title"), recent[p])
            review = qa.llm_review(self.cfg, self.llm, item, variants) if use_review else None
            problems = [f"{p}: {e}" for p in platforms for e in errors[p]]
            if review and int(review.get("score", 10)) < min_score:
                problems += review.get("issues") or []
            if not problems or attempt == 1:
                break
            feedback = ((item.get("feedback") or "") + "\nQA found these problems, fix all of them:\n- "
                        + "\n- ".join(problems)).strip()

        card = out.get("card") or {"headline": item.get("hook") or item.get("topic"), "subtext": ""}
        image = render_card(self.cfg, card.get("headline", ""), card.get("subtext", ""),
                            self.cfg.data_dir / "media" / f"{item['id']}-{item['attempts'] or 0}.png")
        media_url = upload_public(self.cfg, image)
        if "instagram" in platforms and not media_url and not self.cfg.dry_run:
            errors["instagram"].append("no public image URL: set MEDIA_HOST so Instagram can fetch the image")

        rows = []
        for p in platforms:
            v = (out.get("variants") or {}).get(p) or {}
            rows.append({"platform": p, "text": v.get("text", ""), "title": v.get("title"),
                         "scheduled_at": schedule[p], "status": "blocked" if errors[p] else "ready",
                         "issues": errors[p] + warnings[p]})
        self.db.replace_variants(item["id"], rows)
        notes = {"review": review, "errors": {p: e for p, e in errors.items() if e},
                 "warnings": {p: w for p, w in warnings.items() if w}}
        any_ready = any(r["status"] == "ready" for r in rows)
        self.db.update_item(item["id"], card=json.dumps(card, ensure_ascii=False), media_path=str(image),
                            media_url=media_url, qa_notes=json.dumps(notes, ensure_ascii=False),
                            attempts=(item["attempts"] or 0) + 1, feedback=None,
                            status=S.AWAITING if any_ready else S.NEEDS_ATTENTION)
        self.db.log("drafted", item["id"], {"platforms": platforms, "score": (review or {}).get("score")})
        self.request_approval(self.db.item(item["id"]))

    def request_approval(self, item: dict) -> None:
        mode = self.cfg.setting("approval", "mode", "telegram")
        notes = json.loads(item.get("qa_notes") or "{}")
        review = notes.get("review") or {}
        clean = not notes.get("errors") and not notes.get("warnings") and review.get("risk", "low") == "low"
        if mode == "auto" and clean and item["status"] == S.AWAITING:
            self.db.update_item(item["id"], status=S.APPROVED)
            self.db.log("auto_approved", item["id"])
            self.report.append(f"auto-approved {item['topic']}")
            return
        if not self.tg:
            self.report.append(f"awaiting approval (no Telegram configured): {item['id']} {item['topic']}")
            return
        self.send_preview(item)

    def send_preview(self, item: dict) -> None:
        notes = json.loads(item.get("qa_notes") or "{}")
        review = notes.get("review") or {}
        day = date.fromisoformat(item["day"]).strftime("%a %d %b")
        header = (f"📝 <b>{esc(day)} · {esc(item['pillar'])}</b>\n<b>{esc(item['topic'])}</b>"
                  + (f"\nQA score {review.get('score')}/10 · risk {esc(review.get('risk'))}" if review else ""))
        ids = []
        image = Path(item["media_path"]) if item.get("media_path") else None
        if image and image.exists():
            ids.append(self.tg.send_photo(image, header))
        else:
            ids.append(self.tg.send_text(header))
        for v in self.db.variants(item["id"]):
            when = self.cfg.local(datetime.fromisoformat(v["scheduled_at"])).strftime("%H:%M")
            issues = json.loads(v["issues"] or "[]")
            flag = "⛔ BLOCKED, won't post: " if v["status"] == "blocked" else "⚠️ "
            body = (f"<b>{PLATFORM_LABEL[v['platform']]}</b> · {when}\n"
                    + (f"<b>Title:</b> {esc(v['title'])}\n" if v.get("title") else "")
                    + f"{esc(v['text'])}"
                    + (f"\n\n<i>{flag}{esc('; '.join(issues))}</i>" if issues else ""))
            ids.append(self.tg.send_text(body))
        if review.get("issues"):
            ids.append(self.tg.send_text("🔎 Reviewer notes:\n" + "\n".join(f"• {esc(i)}" for i in review["issues"])))
        ids.append(self.tg.send_text("Approve all platforms above? Or reply to any message with changes.",
                                     buttons=approval_buttons(item["id"])))
        self.db.update_item(item["id"], tg_msg_ids=json.dumps(ids))

    # ---- 7. publish ----------------------------------------------------
    def publish_due(self, now: datetime) -> None:
        now_s = iso(now)
        for item in self.db.items(S.APPROVED):
            card = json.loads(item.get("card") or "{}")
            alt = f"{card.get('headline', '')}. {card.get('subtext', '')}".strip(". ")
            image = Path(item["media_path"]) if item.get("media_path") else None
            for v in self.db.variants(item["id"]):
                if v["status"] != "ready" or v["scheduled_at"] > now_s:
                    continue
                post = Post(text=v["text"], title=v.get("title"),
                            image_path=image if image and image.exists() else None,
                            image_url=item.get("media_url"), alt_text=alt or None)
                if v["platform"] == "x":
                    post.image_path = post.image_url = None  # free tier: text only
                publisher = self.publisher_factory(self.cfg, self.db, v["platform"])
                try:
                    res = publisher.publish(post)
                except NotConfigured as exc:
                    self.db.update_variant(v["id"], status="skipped", error=str(exc))
                    self.notify(f"⏭ {PLATFORM_LABEL[v['platform']]} not connected yet, skipped: {esc(str(exc))}")
                    continue
                except Exception as exc:
                    attempts = (v["attempts"] or 0) + 1
                    err = self.cfg.redact(str(exc))[:1000]
                    self.db.update_variant(v["id"], attempts=attempts, error=err,
                                           status="failed" if attempts >= 3 else "ready")
                    self.db.log("publish_error", item["id"], {"platform": v["platform"], "error": err})
                    if attempts >= 3:
                        self.notify(f"🚨 Failed 3 times on {PLATFORM_LABEL[v['platform']]}: "
                                    f"<b>{esc(item['topic'])}</b>\n{esc(err[:400])}")
                    continue
                self.db.update_variant(v["id"], status="published", remote_id=res.remote_id,
                                       remote_url=res.url, published_at=iso(self.cfg.now()), error=None)
                self.db.log("published", item["id"], {"platform": v["platform"], "url": res.url})
                tag = " (dry run)" if self.cfg.dry_run else ""
                self.notify(f"🚀 Posted on {PLATFORM_LABEL[v['platform']]}{tag}: {esc(item['topic'])}"
                            + (f"\n{esc(res.url)}" if res.url else ""))
            states = [v["status"] for v in self.db.variants(item["id"])]
            if states and all(s in TERMINAL for s in states):
                if all(s == "published" for s in states):
                    status = S.PUBLISHED
                elif "published" in states:
                    status = S.PARTIAL
                else:
                    status = S.NEEDS_ATTENTION
                self.db.update_item(item["id"], status=status)

    # ---- 8. housekeeping -----------------------------------------------
    def housekeeping(self, now: datetime) -> None:
        if not self.cfg.dry_run and env("THREADS_ACCESS_TOKEN") and self._due("threads_refreshed_at", now, 24 * 7):
            if ThreadsPublisher(self.cfg, self.db).refresh_token():
                self.db.set_setting("threads_refreshed_at", iso(now))
        expires = env("LINKEDIN_TOKEN_EXPIRES")
        if expires and self._due("linkedin_reminder_at", now, 24):
            days_left = (date.fromisoformat(expires) - self.cfg.local(now).date()).days
            if days_left <= 7:
                self.notify(f"🔑 LinkedIn access token expires in {days_left} day(s). "
                            "Re-authorise (docs/SETUP_FREE.md → LinkedIn) and update the secret.")
                self.db.set_setting("linkedin_reminder_at", iso(now))
        local = self.cfg.local(now)
        week = f"{local.isocalendar().year}-W{local.isocalendar().week}"
        if local.weekday() == 0 and local.hour >= 8 and self.db.get_setting("summary_week") != week:
            self.notify(self.weekly_summary(now))
            self.db.set_setting("summary_week", week)

    # ---- reports -------------------------------------------------------
    def status_text(self) -> str:
        counts: dict[str, int] = {}
        for item in self.db.items():
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        lines = [f"{'⏸ PAUSED' if self.paused else '▶️ Running'} · {'dry run' if self.cfg.dry_run else 'LIVE'}"]
        lines += [f"{k}: {v}" for k, v in sorted(counts.items())] or ["(no content yet)"]
        return "📊 Status\n" + "\n".join(lines)

    def queue_text(self) -> str:
        rows = []
        for item in self.db.items(S.APPROVED):
            for v in self.db.variants(item["id"]):
                if v["status"] == "ready":
                    t = self.cfg.local(datetime.fromisoformat(v["scheduled_at"])).strftime("%a %d %b %H:%M")
                    rows.append((v["scheduled_at"], f"{t} · {PLATFORM_LABEL[v['platform']]} · {esc(item['topic'])}"))
        rows.sort()
        return "🗓 Upcoming approved posts\n" + ("\n".join(r for _, r in rows[:25]) or "(none)")

    def weekly_summary(self, now: datetime) -> str:
        since = iso(now - timedelta(days=7))
        published = self.db.query("SELECT platform, COUNT(*) AS n FROM variants WHERE status = 'published' "
                                  "AND published_at >= ? GROUP BY platform", (since,))
        decided = self.db.query("SELECT kind, COUNT(*) AS n FROM events WHERE at >= ? AND kind IN "
                                "('approved', 'rejected', 'feedback', 'regenerate', 'expired', 'auto_approved') "
                                "GROUP BY kind", (since,))
        pub = ", ".join(f"{PLATFORM_LABEL[r['platform']]} {r['n']}" for r in published) or "nothing"
        dec = ", ".join(f"{r['kind']} {r['n']}" for r in decided) or "no decisions"
        return f"📈 <b>Weekly summary</b>\nPosted: {pub}\nApprovals: {dec}\n\n{esc(self.queue_text())}"
