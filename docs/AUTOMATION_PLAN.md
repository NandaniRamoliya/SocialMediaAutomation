# AI Social Media Employee — Automation Plan

**Goal:** an AI "employee" that does the entire social media job for the company across
**Instagram, Facebook, LinkedIn, YouTube, Threads and X (Twitter)**: research, strategy,
content creation, quality checks, **human approval**, publishing, engagement, reporting and
learning.

**Design rule:** the human only has to **approve** (one tap). Everything before and after
that gate runs on its own. Over time, low-risk work is moved past the gate as well
(see §6, "Trust ramp"), so human time goes toward ~0.

Legend used in every table:

| Mark | Meaning |
|---|---|
| ✅ | Fully automated, no human |
| 🟡 | Automated, then waits for one-tap human approval |
| 🔶 | Partly automatable (the platform API limits it); the system prepares it, a human does one small step |
| ❌ | Cannot be automated (platform doesn't allow it, or it's legally/physically human-only) |

---

## 1. What we took from the three reference docs

| Source | What it gives | What we keep | Why it's not enough on its own |
|---|---|---|---|
| **Claude x Instagram Autopilot (Ootto connector)** | Claude chat + a paid MCP connector to Instagram; prompts for profile audit, competitor research, 30-day calendar, reel scripts, captions/hashtags, DM replies | All six prompt jobs become automated agent tasks (§3) | Instagram only; runs inside a chat window, so a human has to type every prompt; a paid third party holds the account access |
| **YouTube Agent Skill (Claude Code plugin)** | Voice profile from sample scripts, hook generation + scoring, scripts with on-screen text, viral research vs. channel baseline, Shorts clip-finding with timecodes, weekly planning | Voice profile, hook scoring, outlier research, Shorts clipping, planning | It says itself: "You review the results and publish your videos". It drafts only and doesn't upload, reply or report |
| **AI Native Social Media Agent Team (Notion, OneGTMLab)** | 9 agents with an Orchestrator, a `CLAUDE.md` rulebook, owner inputs (voice, budget, approval bar, positioning), 8 departments, 8 event playbooks, 27 "Brand OS" templates, approvals + queues + kill switch, weekly loop, ROI measurement | The whole operating model: Orchestrator, brand brain, departments, playbooks, approval queue, kill switch, weekly loop | It runs inside interactive Claude Code, so someone still has to start it. We run the same design **headless on a schedule**, so it works with nobody at the keyboard |

**Our version:** the Notion team structure, plus the YouTube pack's craft (hooks, voice,
Shorts), plus the Instagram prompts, **running as a scheduled service** that talks to
the platforms' official APIs directly.

---

## 2. The job description: every responsibility and whether we automate it

### A. Brand foundation (one-time setup, then kept up to date automatically)
| # | Responsibility | Status | How |
|---|---|---|---|
| A1 | Brand voice profile (tone, words we use/never use, language mix e.g. English/Hinglish) | ✅ | Built from 5–10 past posts/scripts (same method as the YouTube pack's `voice.md`); re-tuned monthly from what got approved and what got edited |
| A2 | Positioning, audience personas, offers, USPs | 🟡 | Agent drafts them from the website, past posts and competitors; owner approves once |
| A3 | Content pillars (e.g. education / proof / behind-the-scenes / offer) and the mix ratio | 🟡 | Strategist proposes; owner approves once a quarter |
| A4 | Visual identity kit (logo, colours, fonts, templates) | ✅ | Stored in the Brand OS folder; every design is rendered from these templates |
| A5 | Rulebook (`CLAUDE.md`-style): banned claims, legal lines, competitor-mention policy, approval bar | 🟡 | Owner fills one form once; every agent reads it before every task |
| A6 | Budget limits (AI spend, ad spend, tool spend) | 🟡 | Owner sets them; the system enforces them as hard caps |

### B. Research and listening
| # | Responsibility | Status | How |
|---|---|---|---|
| B1 | Audit our own profiles (what works, what doesn't, 5 fixes) | ✅ | Pulls our insights from each platform API every week |
| B2 | Competitor tracking (their top posts, hooks, formats, posting times, promos) | ✅ | Watchlist of competitor accounts; public data, web search, YouTube Data API, Threads keyword search |
| B3 | Trend and news radar for our niche | ✅ | Web search + Google Trends + YouTube trending + Threads/X search, scored for relevance to our pillars |
| B4 | Keyword / search demand (YouTube SEO, LinkedIn topics, hashtags) | ✅ | Search-suggest data + our own performance data |
| B5 | Outlier ("viral") detection: posts doing 3×+ their account's average | ✅ | The YouTube pack's method, applied to all platforms |
| B6 | Audience questions mining (from our comments/DMs/reviews) | ✅ | Clusters recurring questions into content ideas |
| B7 | Brand mention / sentiment monitoring | 🔶 | Possible on platforms with search/mention APIs (Threads, YouTube, X on a paid tier, our own comments everywhere); LinkedIn has no public search API |

### C. Strategy and planning
| # | Responsibility | Status | How |
|---|---|---|---|
| C1 | Monthly content strategy (goals, themes, campaigns, KPIs) | 🟡 | Strategist drafts it from research + last month's results; one approval a month |
| C2 | 30-day content calendar: topic, hook, format, platform, date and time per slot | 🟡 | Generated monthly, refreshed weekly; approved as a batch |
| C3 | Platform mix and frequency (e.g. IG 5/wk, LinkedIn 3/wk, YouTube 1 long + 3 Shorts/wk) | ✅ | Starts from defaults, then tuned automatically from results |
| C4 | Best posting time per platform | ✅ | From each platform's audience-online insights + our own history |
| C5 | Campaigns, festivals, launches, awareness days | ✅ | Calendar of dates for our country and industry, merged into the plan 3 weeks ahead |
| C6 | Content repurposing plan (1 long video → Shorts, carousel, LinkedIn post, thread, X thread) | ✅ | Every "hero" piece gets a repurposing tree automatically |

### D. Content creation
| # | Responsibility | Status | How |
|---|---|---|---|
| D1 | Hooks: 5 options, each scored, best one picked | ✅ | YouTube pack method, used for every format |
| D2 | Captions / post copy written natively per platform (length, tone, line breaks, CTA) | ✅ | One idea → 6 platform-native versions, not one copy pasted 6 times |
| D3 | Hashtags, keywords, alt text, first comment | ✅ | |
| D4 | Reel / Short / TikTok-style scripts (2-sec hook, 30-sec body, CTA, on-screen text) | ✅ | |
| D5 | Long-form YouTube scripts, titles, descriptions, chapters, tags | ✅ | |
| D6 | LinkedIn posts, articles, document (PDF) carousels | ✅ | |
| D7 | X threads and Threads posts | ✅ | |
| D8 | Static graphics and carousels (on-brand) | ✅ | Rendered from brand templates (HTML/Canva-style templating) with AI images where needed |
| D9 | Thumbnails (YouTube) | ✅ | 3 variants generated; best one chosen by a scoring check |
| D10 | Short videos without filming: B-roll, motion graphics, text animation, AI voice-over | ✅ | Template video rendering + AI image/video + text-to-speech |
| D11 | Videos with a real person on camera (founder, team, product in hand) | ❌ / 🔶 | A human must film it. The system sends a shot list and script, then **edits it automatically** (cut silences, captions, music bed, resize to 9:16 / 1:1 / 16:9). An AI avatar of a consenting person is the only no-filming alternative |
| D12 | Clip long videos/podcasts into Shorts with timecodes | ✅ | Transcript → best moments → auto-cut → captions |
| D13 | Subtitles / captions files | ✅ | |
| D14 | Translations / Hinglish versions | ✅ | |

### E. Quality control (before a human sees anything)
| # | Responsibility | Status | How |
|---|---|---|---|
| E1 | Brand voice check | ✅ | Separate reviewer agent scores each draft against the voice profile; below the bar → rewrite automatically |
| E2 | Fact / claim check (prices, stats, offers, dates) | ✅ | Checked against the company facts sheet; anything unverifiable is flagged for the approver |
| E3 | Legal & policy check (banned claims, health/finance claims, copyright, platform ad policy) | ✅ | Rulebook + platform policy checklist; high risk → escalated |
| E4 | Spelling, links, @mentions, hashtags, character limits, aspect ratios, file specs | ✅ | Deterministic checks, no AI needed |
| E5 | Duplicate / too-similar-to-last-week check | ✅ | |
| E6 | Accessibility (alt text, captions, contrast) | ✅ | |

### F. Human verification (the one human step)
| # | Responsibility | Status | How |
|---|---|---|---|
| F1 | Approve / edit / reject each post | 🟡 | One message per post on **Telegram, Slack or WhatsApp** with a preview for every platform and buttons: **Approve · Edit · Regenerate (with a note) · Reject** |
| F2 | Batch approval | 🟡 | "Approve the whole week" in one tap from the dashboard |
| F3 | Learn from edits | ✅ | Every edit and rejection reason is fed back into the voice profile and rulebook |
| F4 | Deadline handling | ✅ | Not approved before the slot → the post is **skipped and rescheduled, never posted unapproved** (unless that category is on auto, §6) |

### G. Publishing (after approval)
| # | Responsibility | Status | How |
|---|---|---|---|
| G1 | Schedule and publish to all 6 platforms at the best time | ✅ | Official APIs (§4) |
| G2 | Platform formats: feed image, carousel, Reel, Story, Short, long video, text post, thread, document post | ✅ / 🔶 | See the platform matrix in §4 for exact limits |
| G3 | First comment, pin comment, playlist, cross-links | ✅ / 🔶 | Platform-dependent |
| G4 | Verify the post actually went live; retry on failure; alert if it fails twice | ✅ | |
| G5 | Kill switch: pause everything instantly | ✅ | One command/button stops all queued posts and auto-replies |
| G6 | Trending audio from Instagram's/YouTube's music library | ❌ | The APIs don't allow adding library music. We use licensed/royalty-free music baked into the video file instead |
| G7 | Story stickers (polls, link stickers, questions), Instagram Collab invites, Broadcast channels, YouTube Community posts | ❌ | No API for these; the system prepares them and sends a 30-second "do this in the app" task to a human if we want them |

### H. Community management and engagement
| # | Responsibility | Status | How |
|---|---|---|---|
| H1 | Read every comment on all platforms | ✅ | IG, FB, Threads, YouTube, LinkedIn company page, X (paid tier) |
| H2 | Reply to routine comments (thanks, FAQs, "price?", "link?") | ✅ (after trust ramp) / 🟡 at start | Replies from the approved FAQ bank go out on their own; anything new waits for approval |
| H3 | Hide/delete spam, scams, abuse | ✅ | Rules + classifier; logged for review |
| H4 | Reply to DMs: Instagram, Facebook Messenger | ✅ / 🟡 | Platform rule: replies must be within **24 hours** of the customer's last message |
| H5 | DMs on LinkedIn | ❌ | No messaging API for normal accounts. The system drafts a reply and notifies a human |
| H6 | DMs on X | 🔶 | Only on a paid API tier |
| H7 | Lead capture from comments/DMs ("interested", "price", "demo") → CRM / Google Sheet + alert the sales person | ✅ | |
| H8 | Negative comment / complaint / crisis | 🟡 always | Never auto-replied. Escalated immediately with a suggested reply |
| H9 | Proactive engagement: commenting on other people's posts, liking, following | ❌ (by choice) | Mostly not allowed by APIs, and automating it gets accounts banned. The system produces a daily "10 posts worth commenting on + suggested comment" list for a human (5 min) |
| H10 | Reviews (Google Business, Facebook recommendations) | 🔶 | Google Business Profile API lets us read and reply; same approval rules as comments |

### I. Analytics, reporting and learning
| # | Responsibility | Status | How |
|---|---|---|---|
| I1 | Collect metrics per post and per account from all 6 platforms | ✅ | Daily pull into our database |
| I2 | Weekly report: what worked, what didn't, followers, reach, engagement, leads | ✅ | Sent automatically every Monday (PDF/Slack/email) |
| I3 | Monthly ROI report (leads, sign-ups, sales with UTM tracking) | ✅ | UTM links on every post; joins with website analytics/CRM |
| I4 | Learning loop: winning hooks, formats, times and topics feed the next plan | ✅ | This is what makes it improve on its own |
| I5 | A/B tests (hooks, thumbnails, times) | ✅ | |

### J. Event playbooks (it reacts without being told)
Taken from the Notion system and extended:

| Trigger | Automatic response | Human? |
|---|---|---|
| A post goes viral (3× normal reach in 2 h) | Pin it, reply to top comments, make 2 follow-up posts, repurpose to other platforms | Approve the follow-ups |
| Search/trend spike in our niche | Draft a quick-response post within 1 h | Approve |
| Competitor launches a promo | Summary + counter-content suggestion | Approve |
| Negative review or complaint spike | Freeze promotional posts, draft responses, alert owner | Always human |
| Calendar has < 7 days of approved posts | Generate 2 weeks of extra drafts | Approve batch |
| Post performance drops for 2 weeks | Diagnose (hook? time? format?) and change the plan | Info only |
| Ad creative fatigue (if ads are on) | New creative variants | Approve |
| DM/lead at 11 pm | Instant FAQ answer + lead logged + morning alert | No |

### K. Things only a human can do (and we keep them small)
- Create the business accounts, pass **Meta Business Verification**, register the developer apps, pass **app review** for Meta, LinkedIn and YouTube (one-time, guided step by step).
- Hold 2FA and recovery for the accounts.
- Film real people when we want real faces (D11).
- Sign contracts and payments with influencers or agencies.
- Increase ad spend above the cap.
- Respond to legal notices and real crises (the system drafts, a human decides).

---

## 3. The agent team

Same shape as the Notion "AI Native Social Media Agent Team", run headless.

| # | Agent | Job | Runs |
|---|---|---|---|
| 1 | **Orchestrator** (the "manager") | Runs the daily/weekly loop, assigns work, enforces budgets and the kill switch, triggers playbooks | Every 15 min + on events |
| 2 | **Brand Brain** | Keeps the voice profile, rulebook, facts sheet and templates; learns from approvals and edits | On change + monthly |
| 3 | **Market Radar** | Competitors, trends, news, keywords, outliers, audience questions | Daily |
| 4 | **Strategist** | Monthly strategy, 30-day calendar, platform mix, campaigns, repurposing tree | Monthly + weekly refresh |
| 5 | **Copywriter** | Hooks, captions, scripts, threads, LinkedIn posts, YouTube metadata, all platform-native | Per calendar slot |
| 6 | **Creative Studio** | Graphics, carousels, thumbnails, short videos, Shorts clipping, subtitles, voice-over | Per calendar slot |
| 7 | **QA & Compliance** | Brand, facts, legal, specs, duplicates, accessibility; rewrites or escalates | Before approval |
| 8 | **Publisher** | Scheduling, posting, verifying it's live, retries | On approval |
| 9 | **Community Manager** | Comments, DMs, spam, leads, escalations | Every 5–15 min |
| 10 | **Analyst** | Metrics, weekly/monthly reports, A/B tests, feeds learnings back | Daily + weekly |

---

## 4. Platform capability matrix (official APIs)

These are the **official APIs** limits as we know them. **Re-check every limit at build
time**, because the platforms change them often.

| Capability | Instagram | Facebook Page | LinkedIn | YouTube | Threads | X (Twitter) |
|---|---|---|---|---|---|---|
| Account type needed | Business or Creator | Page (not personal profile) | Company Page (+ optional personal profile) | Channel | Profile | Account |
| API | Instagram Graph API / Instagram API with Instagram Login | Graph API (Pages) | Posts API + Community Management API | YouTube Data API v3 + Analytics API | Threads API | X API v2 |
| Approval needed to use it | Meta app review + Business Verification | Meta app review + Business Verification | **Community Management API approval** for company pages (weeks; needs a registered company) | Google API **compliance audit**, otherwise uploads stay **private** | Meta app review | Paid tier for anything beyond basic posting |
| Image / text posts | ✅ image (text needs an image) | ✅ | ✅ | ❌ (Community posts have no API) | ✅ | ✅ |
| Carousel | ✅ up to 10 | ✅ multi-photo | ✅ document/PDF carousel, multi-image | — | ✅ up to 20 | ✅ up to 4 images |
| Short video | ✅ Reels | ✅ Reels/video | ✅ video | ✅ Shorts (vertical upload) | ✅ | ✅ |
| Long video | ✅ (as Reel) | ✅ | ✅ | ✅ | ✅ | ✅ (length depends on tier) |
| Stories | ✅ (no stickers) | ✅ | — | — | — | — |
| Native scheduling | We schedule | ✅ `scheduled_publish_time` | We schedule | ✅ `publishAt` | We schedule | We schedule |
| Daily posting limit | ~100 API posts / 24 h | High | Rate limited | **~6 uploads/day** on the default 10,000-unit quota (upload ≈ 1,600 units); quota increase on request | 250 posts / 24 h | Depends on paid tier |
| Read & reply to comments | ✅ | ✅ | ✅ company page posts | ✅ | ✅ | 🔶 paid tier |
| Hide/delete comments | ✅ | ✅ | ✅ delete | ✅ moderate | ✅ hide | 🔶 hide replies |
| DMs | ✅ 24 h window | ✅ Messenger, 24 h window | ❌ | ❌ (no DMs) | ❌ | 🔶 paid tier |
| Analytics | ✅ | ✅ | ✅ org stats | ✅ | ✅ | 🔶 paid tier |
| Library music / trending audio | ❌ | ❌ | — | ❌ | — | — |
| Biggest catch | Business Verification + app review | Groups can't be posted to via API any more | Company-page access approval is slow and strict | Must pass the audit or every upload is private | Newer API, fewer features | **Cost**: free tier is write-only with a small monthly cap; reading comments/mentions needs a paid plan |

**Budget = $0 decision:** unified posting APIs (Ayrshare, Buffer and similar) cost money, so we use each
platform's **official free API directly**. For our own accounts, Meta (Facebook, Instagram, Threads) works without
App Review, LinkedIn personal-profile posting is self-serve, and X has a free posting tier.
Setup steps: [`SETUP_FREE.md`](SETUP_FREE.md).

---

## 5. How one week runs (zero human except the approval taps)

```
Mon 07:00  Analyst     → weekly report to owner (last week's results + learnings)
Mon 08:00  Radar       → competitor + trend + keyword scan
Mon 09:00  Strategist  → refreshes next 14 days of the calendar
Mon 10:00  Copywriter + Creative Studio → drafts for every slot (6 platform versions each)
Mon 11:00  QA          → checks, auto-rewrites, flags risks
Mon 11:30  Owner       → gets "12 posts ready", approves the week in ~10–15 minutes
Daily      Publisher   → posts at best time per platform, confirms live
Every 10m  Community   → comments/DMs/spam/leads; escalates the rest
Daily      Radar       → watches for spikes → playbooks (§2-J)
1st of mo  Strategist  → monthly strategy + 30-day calendar for approval
```

---

## 6. Approval design (how we take the human out step by step)

1. **Tiers** set in the rulebook:
   - **Tier 0, auto:** spam hiding, FAQ replies from the approved bank, metric reports, reposting an already-approved post to another platform.
   - **Tier 1, one tap:** normal posts, new comment replies, DMs outside the FAQ bank.
   - **Tier 2, full review:** offers/prices, legal/health/finance claims, anything about competitors, crisis, paid ads, anything QA flagged.
2. **Trust ramp:** when a category is approved **without edits ≥ 95% of the time for 4 weeks**, the system proposes moving it to Tier 0. The owner says yes once, and that category no longer needs a human. This is how we reach "no human needed" safely.
3. **Never** auto-post Tier 2.
4. **Kill switch** on Telegram/Slack/dashboard: pauses all publishing and auto-replies immediately.
5. **Audit log:** every post, reply and approval is recorded (who/what/when, the exact text and media).

---

## 7. Technology ($0 budget)

| Layer | Free choice | Notes |
|---|---|---|
| AI brain | **Our existing Claude plan**, run headless through Claude Code (`claude -p`, token from `claude setup-token`) | No API bill; shares the plan's usage limits. Backup: Gemini API free tier |
| Runtime | **GitHub Actions** cron, every hour | Free and unlimited for public repos; a keep-alive step stops GitHub switching the schedule off |
| System of record | **Supabase free Postgres** (SQLite locally) | Repo is public, so no state, tokens or leads are ever committed |
| Image hosting | Supabase Storage public bucket (or imgbb) | Instagram/Threads fetch images from a public URL |
| Approvals | **Telegram bot** (polled each run, no server) | One-tap approve, reply to edit, `/pause` kill switch |
| Publishing | Official free APIs of each platform | See §4 |
| Graphics | Pillow, rendered from brand colours | No design tool needed |
| Video (next phase) | FFmpeg + free stock (Pexels API) + free TTS | Faceless short videos |
| Research | Google News RSS, YouTube channel RSS, blog RSS | No keys, no quota |

## 8. Build roadmap

| Phase | Time | Output | Human work |
|---|---|---|---|
| **0. Setup** | Week 1 | Business accounts on all 6 platforms, Meta Business Verification started, developer apps registered (Meta, LinkedIn, Google, X), brand intake form filled | Owner: ~2–3 h, guided checklist |
| **1. Brain + drafting** ✅ built | Weeks 1–2 | Brand Brain, Radar, Strategist, Copywriter, QA; Telegram approval bot; drafts for all 6 platforms | Approve drafts, post by hand for now |
| **2. Auto-publishing** ✅ built | Weeks 2–4 | Publishers on the official free APIs → posting happens on approval; image cards | Approval taps only |
| **3. Video** | Weeks 3–5 | Short videos without filming, Shorts clipping from long videos, YouTube uploads | Approval taps; film when we want faces |
| **4. Community** | Weeks 4–6 | Comments, DMs, spam, lead capture, escalations | Tier 2 replies only |
| **5. Analytics + learning** | Weeks 5–7 | Metrics pipeline, weekly/monthly reports, learning loop, A/B tests, playbooks | Read the Monday report |
| **6. Company pages + trust ramp** | Weeks 6–10 | LinkedIn company page once approved; YouTube audit; turn on Tier 0 categories | Say yes to trust-ramp proposals |

---

## 9. Decisions

Already decided by the $0 budget: Telegram for approvals, official APIs instead of a paid posting service,
X posting only (free tier), LinkedIn personal profile first (company page once Community Management API
access is approved), faceless content (no filming needed).

Still needed from the company:
1. Company name, niche, website, audience and language (English, Hindi or Hinglish?). This goes into `brand/brand.yaml`.
2. 3–10 of our best past posts, so the AI learns the voice.
3. Posting days and times per platform (defaults are in `brand/brand.yaml`).
4. Competitors to watch (their YouTube channels and blogs).
5. Where leads should go (Google Sheet is free) when the community phase starts.
