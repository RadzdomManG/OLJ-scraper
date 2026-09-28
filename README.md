# OnlineJobs Watcher Bot

## Aurelius web portal (Vercel)

The `frontend/` directory is a Next.js dashboard. Vercel runs the frontend and its protected API routes; the Flask watcher runs separately. Public code users can access only `/jobs`. Supabase Auth verifies the owner, and Supabase Postgres stores hashed access codes. Owner and code checks run on the server. The frontend never sends the Supabase service role key or backend token to the browser.

### 1. Set up Supabase

Create a Supabase project, run [`supabase/schema.sql`](supabase/schema.sql) in its SQL editor, and create the owner account under Authentication → Users. Disable public signups for an owner-only portal. Set `OWNER_EMAIL` to the exact owner account email. The owner password stays in Supabase Auth; there is no `OWNER_PASSWORD_HASH` when using this method.

Access codes are displayed only when created. Copy them then; the database stores only a keyed hash. Revoking or deleting a code immediately invalidates its viewer sessions. `max_uses` counts successful new code logins, not page refreshes. Existing sessions remain valid after the use limit is reached until the code is revoked or expires.

### 2. Run the Flask backend

Copy [`.env.example`](.env.example) values into your terminal environment or process manager. Set `BACKEND_API_TOKEN` to a long random secret and use the same value on Vercel. This protects all `/api/*` endpoints when exposing the backend. Set `FRONTEND_ORIGIN` to your exact Vercel URL. Localhost port 3000 is also allowed for development. `UI_HOST` defaults to `0.0.0.0`, `UI_PORT` to `8080`, and `GET /healthz` is available for health checks.

```powershell
git clone https://github.com/RadzdomManG/OLJ-scraper.git
cd OLJ-scraper
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:BACKEND_API_TOKEN = "your-long-random-secret"
$env:FRONTEND_ORIGIN = "https://your-project.vercel.app"
python watcher.py
```

On macOS/Linux, activate with `source .venv/bin/activate` and use `export` for environment variables. In a second terminal, install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) and run:

```text
cloudflared tunnel --url http://localhost:8080
```

Use the generated `https://xxxxx.trycloudflare.com` URL as `NEXT_PUBLIC_BACKEND_API_URL`. Quick Tunnel URLs change when restarted, so update the Vercel environment variable and redeploy after a URL change. A named tunnel or VPS address is preferable for stable hosting.

### 3. Configure and deploy the frontend

Use [`frontend/.env.example`](frontend/.env.example) as the variable checklist. In Vercel, set the project root directory to `frontend`. Set `NEXT_PUBLIC_BACKEND_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `OWNER_EMAIL`, `SESSION_SECRET`, and `BACKEND_API_TOKEN`. Keep the service role key, session secret, and backend token server side; never add `NEXT_PUBLIC_` to them. `NEXT_PUBLIC_BACKEND_API_URL` is public by design, but its API requires the server token.

For local development:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Set real values in `.env.local` before signing in. The app is at `http://localhost:3000`. Run `npm run lint` and `npm run build` before deployment. `.env` files are gitignored.

**Security:** Do not expose the Flask API through a tunnel without `BACKEND_API_TOKEN`. Its original dashboard and control endpoints are powerful. The portal sends the token only from Next.js server routes. The owner's Supabase access cookie expires with the Auth token, after which the owner signs in again.

Simple bot for watching OnlineJobs.ph job posts and sending alerts to Telegram.

## What This Bot Does

- checks for new job posts
- saves seen jobs and job history
- opens a local dashboard
- sends Telegram alerts for matching jobs

## Requirements

Install these first:

- Python 3.11 or newer
- `pip`

## Project Files

Important saved files:

- `data/seen_jobs.json` - jobs already seen
- `data/job_events.json` - saved job history
- `data/telegram_settings.json` - Telegram token, chat ID, and trigger words

## First-Time Setup

Open PowerShell in the project folder:

```powershell
cd "D:\RADZ AUTOMATION\onlinejobs-watcher"
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

## How To Start The Bot

Run:

```powershell
python watcher.py
```

After starting:

- the dashboard will open in a desktop window if supported
- if desktop mode is not available, open this in your browser:

```text
http://127.0.0.1:8080
```

## Telegram Setup

After the bot starts:

1. open the dashboard
2. go to `Telegram Mobile Alerts`
3. enter your:
   - Bot Token
   - Chat ID
   - Trigger Words
4. click `Save`
5. click `Send Test`

The bot saves those settings here:

```text
data/telegram_settings.json
```

## What To Enter

### Bot Token

Get this from BotFather in Telegram.

Example:

```text
1234567890:ABCdefGHIjkLMNopQRstuVWxyz
```

### Chat ID

This is the Telegram chat, group, or channel ID where alerts will be sent.

Example:

```text
123456789
```

or for some groups/channels:

```text
-1001234567890
```

### How To Get Your Chat ID

Simple way:

1. create your bot using `@BotFather`
2. start a chat with your bot and send any message like `hello`
3. open this in your browser, replacing `YOUR_BOT_TOKEN`:

```text
https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
```

4. look for `"chat":{"id": ... }`
5. copy that number and use it as your Chat ID

If you are using a Telegram group:

1. add the bot to the group
2. send a message in the group
3. open `getUpdates` again
4. copy the group chat ID

Note:

- personal chat IDs are usually positive numbers
- group or channel IDs often start with `-100`

### Trigger Words

These are the words the bot uses to decide what jobs matter to you.

Example:

```text
video editor, social media, content creator, ai automation
```

## Start Again Later

Next time, you only need:

```powershell
cd "D:\RADZ AUTOMATION\onlinejobs-watcher"
.\.venv\Scripts\Activate.ps1
python watcher.py
```

## How To Stop The Bot

In the same terminal:

```powershell
Ctrl + C
```

## Optional: Set Telegram In Terminal

If you want, you can also set your Telegram details before starting the bot:

```powershell
$env:TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
$env:TELEGRAM_CHAT_ID="YOUR_CHAT_ID"
$env:TRIGGER_WORDS="video editor,social media,content creator"
python watcher.py
```

Note:

- if you save settings in the dashboard, they are stored in `data/telegram_settings.json`
- environment variables can override saved values for that run

## Optional Settings

Useful terminal settings:

```powershell
$env:POSTED_WITHIN_MINUTES="60"
$env:UI_PORT="8080"
$env:DESKTOP_APP="true"
$env:TELEGRAM_ENABLED="true"
python watcher.py
```

## Health Check

When the bot is running, test this:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/healthz
```

Expected result:

```text
{"ok": true}
```

## Install Packages Used By This Bot

These are installed from `requirements.txt`:

- `requests`
- `beautifulsoup4`
- `lxml`
- `flask`
- `tzdata`
- `pywebview`

## Notes

- the scan cycle in this version is fixed at `20` seconds
- keep your Telegram bot token private
- if Telegram is enabled, make sure your Bot Token and Chat ID are correct
