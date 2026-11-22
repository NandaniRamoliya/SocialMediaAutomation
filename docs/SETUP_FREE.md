# Setup guide: $0 budget

Everything below is free. You do it **once** (about 2–3 hours in total). After that the system
runs every hour on GitHub Actions, and you only approve posts on Telegram.

Where each value goes:
- **Secrets**: GitHub repo → Settings → Secrets and variables → Actions → **Secrets** → *New repository secret*
- **Variables** (not secret): same page → **Variables** tab

> This repository is **public**. Never paste a token into a file in the repo, an issue or a commit.
> Tokens only go into GitHub **Secrets** (or your local `.env`, which git ignores).

Platform screens and limits change often. If a button has moved, search the platform's
developer docs for the permission names given here.

---

## The $0 stack

| Job | Free service | Limit that matters |
|---|---|---|
| Runs every hour | GitHub Actions (public repo) | Free and unlimited for public repos. Hourly runs can start a few minutes late |
| AI brain | **Your Claude plan** via Claude Code (`CLAUDE_CODE_OAUTH_TOKEN`) | Shares your plan's normal usage limits. ~8–12 AI calls per day |
| Backup AI | Google Gemini API free tier | Free-tier rate limits; Google may use free-tier prompts to improve its products, so no private customer data |
| Database | Supabase free Postgres | 500 MB. Free projects pause after 7 days idle; the hourly run keeps it awake |
| Image hosting | Supabase Storage (public bucket) or imgbb | 1 GB on Supabase |
| Approvals | Telegram bot | Free |
| Research | Google News RSS, competitors' YouTube RSS, blog RSS | Free, no keys |
| Images | Built in (Pillow) | Free |
| Facebook, Instagram, Threads | Meta APIs, app in Development mode | Free; your own accounts need no App Review |
| LinkedIn | "Share on LinkedIn" (personal profile) | Free; token must be renewed by hand every 60 days (you get a reminder) |
| X | Free API tier | Posting only, small monthly cap, text only |
| YouTube | Data API free quota | ~6 uploads/day; uploads stay private until the free API audit is passed |

---

## Step 1: Telegram bot (approvals), 5 minutes

1. In Telegram, open **@BotFather** → send `/newbot` → choose a name and a username ending in `bot`.
2. BotFather replies with a token → secret **`TELEGRAM_BOT_TOKEN`**.
3. Open your new bot and send it any message (e.g. `hi`).
4. In a browser open `https://api.telegram.org/bot<TOKEN>/getUpdates` (put your token in).
   Find `"chat":{"id":123456789` → secret **`TELEGRAM_CHAT_ID`**.
   ⚠️ This is **your** id, not the bot's. The number before the `:` in the token is the bot's own id,
   and that is the wrong one. If the page shows `"result":[]`, send the bot another message and reload.
   (For a team group: add the bot to the group, send a message there, and use the group's id, which starts with `-`.)

Only this chat can approve posts or use `/pause`. Messages from anyone else are ignored.

## Step 2: AI brain (Google Gemini, free), 5 minutes

1. Go to <https://aistudio.google.com> and sign in with a Google account.
2. *Get API key* → *Create API key* → secret **`GEMINI_API_KEY`**.

That's all. Gemini's free tier is the default AI. The free limits are shown in AI Studio. If you ever hit the
daily limit, set the variable **`GEMINI_MODEL`** to a "flash-lite" model listed there (higher free limits),
or turn off `qa.llm_review` in `brand/brand.yaml` (halves the AI calls).

**Optional, only with a paid Claude Pro or Max plan:** run `claude setup-token` in a terminal → secret
**`CLAUDE_CODE_OAUTH_TOKEN`**, variable **`LLM_PROVIDER`** = `claude_code`, and keep Gemini as backup
with variable **`LLM_FALLBACK`** = `gemini`. A free Claude account shows "Claude Max, Ultra, or Pro
is required"; in that case simply use Gemini.

## Step 3: Database + image hosting (Supabase), 10 minutes

1. Sign up at <https://supabase.com> → *New project* (Free plan). Save the database password.
2. Click **Connect** (top bar) → choose the **Session pooler** connection string (URI).
   GitHub Actions has no IPv6, so the "Direct connection" string does not work there.
   Replace `[YOUR-PASSWORD]` with your database password → secret **`DATABASE_URL`**.
   If the password has symbols like `@ # / : ?`, either reset it to letters and numbers only
   (Project Settings → Database → Reset password) or URL-encode them (`@` → `%40`, `#` → `%23`).
3. **Storage** → *New bucket* → name `media` → turn **Public bucket** on → Create.
4. *Project URL* (shown on the project home page, e.g. `https://xxxx.supabase.co`) → secret **`SUPABASE_URL`**.
5. **Project Settings → API Keys**: create or copy a **secret key** (`sb_secret_...`), or the
   `service_role` key from the *Legacy API keys* tab → secret **`SUPABASE_SERVICE_KEY`**.
   Never use the *publishable* / `anon` key here. Keep the secret key private: it has full access.
6. Variable **`MEDIA_HOST`** = `supabase`.

Alternative image host: free key from <https://api.imgbb.com> → secret **`IMGBB_API_KEY`**, variable `MEDIA_HOST` = `imgbb`.

## Step 4: Facebook Page + Instagram, 30–45 minutes

Requirements: a **Facebook Page**, and your Instagram set to a **Professional account** (Business or
Creator) and **linked to that Page** (Page settings → Linked accounts → Instagram).

1. Go to <https://developers.facebook.com> → *My Apps* → **Create app** (name it e.g. `SMM Facebook Instagram`).
   On **Add use cases**, choose the filter **Content management** and tick:
   - **Manage everything on your Page**
   - **Manage messaging & content on Instagram** (when asked, choose *API setup with Facebook login*)

   Do **not** tick *Access the Threads API* here. Threads gets its own app in Step 5.
   If it asks for a **Business** portfolio, pick yours or create one (free). Leave the app in
   **Development** mode: as the app admin you can use it on your own Page and Instagram
   without App Review.
2. Open **Tools → Graph API Explorer**, choose your app, *User Token*, and add these permissions:
   `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `instagram_basic`,
   `instagram_content_publish`, `business_management`. Click **Generate Access Token** and allow everything.
3. Make it long-lived (App ID and App Secret are under App settings → Basic). Open this in the browser:
   ```
   https://graph.facebook.com/v24.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN
   ```
4. Get the **Page token**, which does not expire:
   `https://graph.facebook.com/v24.0/me/accounts?access_token=LONG_USER_TOKEN`
   Find your Page: its `access_token` → secret **`META_PAGE_TOKEN`**, its `id` → secret **`META_PAGE_ID`**.
5. Get the Instagram account id:
   `https://graph.facebook.com/v24.0/PAGE_ID?fields=instagram_business_account&access_token=PAGE_TOKEN`
   → `instagram_business_account.id` → secret **`IG_USER_ID`**.
6. Paste the Page token into the **Access Token Debugger** (Tools menu). It should say *Expires: Never*.

## Step 5: Threads, 20 minutes

1. In the same Meta developer account, **Create app** again (e.g. `SMM Threads`) and tick only
   **Access the Threads API** (Meta keeps Threads in its own app). In the use case's settings,
   add the permissions `threads_basic` and `threads_content_publish`. The Threads **App ID and secret**
   are on the Threads use case's settings page; they differ from the app's main App ID.
2. **App roles → Roles → Add Threads Tester** → your Threads username. Accept the invite in the
   Threads app: Settings → Account → Website permissions → Invites.
3. In the Threads settings of the app, set a **Redirect URL**, e.g. this repo's URL
   `https://github.com/NandaniRamoliya/SocialMediaAutomation`.
4. Open in a browser (with your Threads app id and redirect URL):
   ```
   https://threads.net/oauth/authorize?client_id=THREADS_APP_ID&redirect_uri=REDIRECT_URL&scope=threads_basic,threads_content_publish&response_type=code
   ```
   Allow it. You land on the redirect page; copy the `code=` value from the address bar (drop a trailing `#_`).
5. Exchange it (terminal):
   ```bash
   curl -X POST https://graph.threads.net/oauth/access_token -F client_id=THREADS_APP_ID -F client_secret=THREADS_APP_SECRET -F grant_type=authorization_code -F redirect_uri=REDIRECT_URL -F code=CODE
   ```
   Then make it long-lived (60 days):
   `https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret=THREADS_APP_SECRET&access_token=SHORT_TOKEN`
   → secret **`THREADS_ACCESS_TOKEN`**. The system **refreshes it automatically every week**, so you never redo this.
6. `https://graph.threads.net/v1.0/me?fields=id,username&access_token=LONG_TOKEN` → `id` → secret **`THREADS_USER_ID`**.

## Step 6: LinkedIn, 15 minutes (+ 2 minutes every 60 days)

**Personal profile (free, instant):**
1. <https://www.linkedin.com/developers/apps> → **Create app** (it must be linked to a LinkedIn Page; use your company page).
2. **Products** tab → add **Sign In with LinkedIn using OpenID Connect** and **Share on LinkedIn**.
3. Open <https://www.linkedin.com/developers/tools/oauth/token-generator> → choose the app → tick
   `openid`, `profile`, `w_member_social` → *Request access token* → secret **`LINKEDIN_ACCESS_TOKEN`**.
4. Find your member id:
   ```bash
   curl -H "Authorization: Bearer TOKEN" https://api.linkedin.com/v2/userinfo
   ```
   → `sub` → secret **`LINKEDIN_AUTHOR_URN`** = `urn:li:person:<sub>`.
5. Variable **`LINKEDIN_TOKEN_EXPIRES`** = today + 60 days (e.g. `2027-01-21`). Telegram reminds you 7 days before.

**Company page:** on the app's Products tab, request **Community Management API** (free, but
LinkedIn reviews it; you need a registered company). Once approved, generate a token with
`w_organization_social` and set `LINKEDIN_AUTHOR_URN` = `urn:li:organization:<page id>`
(the number in your page's admin URL).

## Step 7: X (Twitter), 10 minutes

1. <https://developer.x.com> → sign up for the **Free** tier → open your Project → App.
2. **User authentication settings** → *Set up* → App permissions **Read and write**,
   type *Web App, Automated App or Bot*, Callback/Website URL = this repo's URL → Save.
   Do this *before* creating the tokens.
3. **Keys and tokens**: *API Key and Secret* → secrets **`X_API_KEY`**, **`X_API_SECRET`**;
   *Access Token and Secret* (Generate) → secrets **`X_ACCESS_TOKEN`**, **`X_ACCESS_SECRET`**.
   The access token must show **Read and Write**.

The free tier is posting-only, with a small monthly cap. Check the current number in the portal. The default schedule uses ~22 posts a month.

## Step 8: YouTube (later, when the video pipeline is on)

1. <https://console.cloud.google.com> → new project → enable **YouTube Data API v3**.
2. **OAuth consent screen**: External, add yourself as a test user, then **Publish app → In production**.
   (In "Testing" mode the token dies after 7 days.)
3. **Credentials → Create OAuth client ID** (Web application), redirect URI
   `https://developers.google.com/oauthplayground` → secrets **`YT_CLIENT_ID`**, **`YT_CLIENT_SECRET`**.
4. <https://developers.google.com/oauthplayground> → ⚙️ *Use your own OAuth credentials* → scope
   `https://www.googleapis.com/auth/youtube.upload` → Authorize → *Exchange authorization code for tokens*
   → refresh token → secret **`YT_REFRESH_TOKEN`**.
5. Uploads stay *private* until you pass YouTube's free API audit (form linked from the API docs).

## Step 9: Fill in the brand and switch it on

1. Edit `brand/brand.yaml`: company, audience, voice (paste 3–10 of your best past posts),
   rules, pillars, posting days and times, research keywords, competitor YouTube channel ids.
2. GitHub → **Actions** → *Autopilot* → **Run workflow** with command `check`: it lists what is connected.
3. Run it with `test-llm`, then with `cycle`. You should get the first previews on Telegram.
4. It now runs **every hour by itself**. It starts in **dry run**: everything happens except the
   real posting, and Telegram says "(dry run)". When you like a week of drafts, set the variable
   **`SMM_DRY_RUN`** = `false`. From then on, approved posts are published for real.

## Daily use (all in Telegram)

| You do | It does |
|---|---|
| Tap **✅ Approve** | Posts each platform at its time |
| Tap **🔁 Regenerate** | Writes a fresh version and sends it again |
| **Reply** to any preview with changes, e.g. "shorter, mention our Diwali offer" | Rewrites it with your note |
| Tap **❌ Reject** | Drops it |
| Do nothing | Never posts it; it expires at its slot |
| `/pause` · `/resume` | Kill switch: stops or starts all drafting and posting |
| `/status` · `/queue` · `/plan` | Pipeline counts · upcoming posts · refresh the calendar |

Changing `approval.mode` to `auto` in `brand/brand.yaml` lets clean, low-risk posts go out
without a tap. Anything with a QA warning or medium/high risk still waits for you.

## Run locally (optional)

```bash
pip install -r requirements-dev.txt
```

```bash
cp .env.example .env
```

```bash
python -m smm check
```

```bash
python -m smm cycle
```

```bash
python -m pytest -q
```

Locally the database is a SQLite file in `data/`, so no Supabase is needed.
