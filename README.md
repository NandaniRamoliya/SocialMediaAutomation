# SocialMediaAutomation

An AI social media employee for the company, running on **free tiers only ($0 budget)**.
It researches, plans the calendar, writes native posts for each platform, designs the image,
checks quality and compliance, asks for **one-tap approval on Telegram**, publishes on
schedule, and reports weekly.

Platforms: **Instagram · Facebook · LinkedIn · Threads · X** (YouTube is wired in for the upcoming video phase).

```
every hour (GitHub Actions, free)
  Telegram approvals ─► research (daily) ─► plan 14 days ─► draft + QA + image ─► Telegram preview
                                                                                 │ ✅ approve
                                                       publish at the slot time ◄┘
```

## What's built (phase 1–2)

| Part | Where | Status |
|---|---|---|
| Brand brain (voice, rules, facts, pillars, schedule) | `brand/brand.yaml`, `smm/brand.py` | ✅ |
| Market radar (Google News, competitor YouTube RSS, blog RSS) | `smm/agents/research.py` | ✅ |
| Strategist (14-day calendar, pillar mix, no repeats) | `smm/agents/strategist.py` | ✅ |
| Copywriter (native text for each platform) | `smm/agents/copywriter.py` | ✅ |
| QA (limits, banned words, placeholders, duplicates, AI brand/risk review, one auto-rewrite) | `smm/agents/qa.py` | ✅ |
| Image cards in brand colours | `smm/creative.py` | ✅ |
| Telegram approvals, reply-to-edit, kill switch | `smm/approval/telegram.py`, `smm/orchestrator.py` | ✅ |
| Publishers: Facebook, Instagram, Threads, LinkedIn, X, YouTube | `smm/publishers/` | ✅ (dry run by default) |
| Hourly schedule + tests on GitHub Actions | `.github/workflows/` | ✅ |
| Weekly summary, token refresh/reminders | `smm/orchestrator.py` | ✅ |
| Comments/DMs, analytics pull, carousels, short videos | – | next phases |

## Start here

1. **[docs/SETUP_FREE.md](docs/SETUP_FREE.md)**: get every free account and token (once, ~2–3 h).
2. Fill in **`brand/brand.yaml`**.
3. GitHub → Actions → *Autopilot* → Run workflow → `check`, then `cycle`.

It starts in **dry run** (nothing is really posted) until you set the `SMM_DRY_RUN` variable to `false`.

The full plan, including the complete list of responsibilities and what can and can't be automated, is in
**[docs/AUTOMATION_PLAN.md](docs/AUTOMATION_PLAN.md)**.

## Commands

```bash
python -m smm check        # what's connected
```

```bash
python -m smm cycle        # one full run (what the hourly job does)
```

`status`, `queue`, `list`, `show ID`, `approve ID`, `reject ID`, `redraft ID "note"`,
`pause`, `resume`, `plan`, `draft`, `publish`, `card "Headline" "Subtext"`, `test-llm`.
