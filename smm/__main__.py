"""Command line.  python -m smm <command>

  cycle             run one full cycle (what GitHub Actions runs every hour)
  check             show which platforms / services are connected
  research | plan   run one step on its own
  draft             draft + QA + send for approval for upcoming days
  publish           publish approved posts that are due
  status | queue    show the pipeline
  list              list items with ids
  show ID           show one item with all platform texts
  approve ID | reject ID | redraft ID "note"   decide without Telegram
  pause | resume    kill switch
  card "Headline" "Subtext"   render a test image to data/media/test-card.png
  test-llm          one tiny call to the configured LLM
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .approval.telegram import Telegram
from .config import Config, env
from .db import DB, REDRAFT
from .orchestrator import Autopilot
from .publishers import REGISTRY


def build(args) -> Autopilot:
    cfg = Config(args.brand)
    db = DB(cfg.database_url)
    return Autopilot(cfg, db, telegram=Telegram.from_env(cfg))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="smm", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--brand", help="path to brand.yaml")
    parser.add_argument("command")
    parser.add_argument("args", nargs="*")
    args = parser.parse_args(argv)
    if os.environ.get("GITHUB_ACTIONS") == "true" and not env("DATABASE_URL") \
            and args.command not in ("check", "test-llm", "card"):
        # Not set up yet: skip quietly (exit 0) so GitHub doesn't send a failure email every hour.
        print("::warning::Not set up yet: DATABASE_URL is missing, so nothing was done. Runners are wiped "
              "after every run; without a database each run would start from zero. See docs/SETUP_FREE.md, step 3.")
        return 0
    ap = build(args)
    cfg, db, now = ap.cfg, ap.db, ap.cfg.now()
    cmd = args.command

    if cmd == "cycle":
        report = ap.cycle()
    elif cmd == "research":
        db.set_setting("last_research_at", "")
        ap.maybe_research(now)
        report = ap.report
    elif cmd == "plan":
        db.set_setting("last_plan_at", "")
        ap.maybe_plan(now)
        report = ap.report or ["nothing to plan (calendar already full)"]
    elif cmd == "draft":
        ap.draft_due(now)
        report = ap.report
    elif cmd == "publish":
        ap.publish_due(now)
        report = ap.report
    elif cmd == "status":
        report = [ap.status_text()]
    elif cmd == "queue":
        report = [ap.queue_text()]
    elif cmd == "list":
        report = [f"{i['id']}  {i['day']}  {i['status']:<20} {i['topic']}" for i in db.items()] or ["(empty)"]
    elif cmd == "show":
        item = db.item(args.args[0])
        report = [json.dumps({"item": item, "variants": db.variants(args.args[0])}, indent=2, ensure_ascii=False)]
    elif cmd in ("approve", "reject"):
        report = [ap.apply_decision(args.args[0], "ap" if cmd == "approve" else "rj", by="cli")]
    elif cmd == "redraft":
        db.update_item(args.args[0], status=REDRAFT, feedback=" ".join(args.args[1:]) or None)
        report = ["will be rewritten on the next draft run"]
    elif cmd == "pause":
        ap.handle_command("/pause")
        report = ap.report
    elif cmd == "resume":
        ap.handle_command("/resume")
        report = ap.report
    elif cmd == "card":
        from .creative import render_card
        path = render_card(cfg, args.args[0] if args.args else "Your headline here",
                           args.args[1] if len(args.args) > 1 else "A short supporting line.",
                           cfg.data_dir / "media" / "test-card.png")
        report = [f"wrote {path}"]
    elif cmd == "check":
        report = [f"mode: {'DRY RUN (nothing is really posted)' if cfg.dry_run else 'LIVE'}",
                  f"database: {db.kind}",
                  f"LLM: {env('LLM_PROVIDER') or 'claude_code'}" + (f" (fallback {env('LLM_FALLBACK')})" if env('LLM_FALLBACK') else ""),
                  f"telegram approvals: {'connected' if ap.tg else 'NOT configured'}",
                  f"media host: {env('MEDIA_HOST') or 'none (Instagram needs one when live)'}"]
        for name in cfg.platforms:
            missing = REGISTRY[name](cfg, db).missing()
            report.append(f"{name:<10} {'ready' if not missing else 'missing ' + ', '.join(missing)}")
    elif cmd == "test-llm":
        out = ap.llm.complete_json("You are a test.", "Say hello in one word.",
                                   {"type": "object", "properties": {"word": {"type": "string"}}, "required": ["word"]})
        report = [f"{ap.llm.name}: {out}"]
    else:
        parser.print_help()
        return 2
    for line in report:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
