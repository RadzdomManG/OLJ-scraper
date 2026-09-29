# Multi-source watcher setup

## Run locally

On Windows, from `D:\OLJ SCRAPER`:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
# Edit .env with your Telegram token and chat ID.
python watcher.py
```

The watcher schedules OLJ with a 20-second minimum interval and each additional
source at its own interval. A slow source can extend the actual time between
checks. It runs continuously while the terminal and computer remain on.
For unattended use, create a Windows Task Scheduler task:

1. Trigger: **At log on** for your Windows account.
2. Action program: your `python.exe` path (run `Get-Command python` to find it).
3. Arguments: `watcher.py`; **Start in:** `D:\OLJ SCRAPER`.
4. In **Settings**, select **If the task fails, restart every 1 minute** and
   **Run task as soon as possible after a scheduled start is missed**.
5. Keep Windows awake and connected to the internet.

The customer jobs page reads the private Supabase mirror, so it continues to show
stored jobs if the local watcher stops. New discoveries and owner backend controls
require the watcher to remain online. A temporary Cloudflare tunnel URL changes
when restarted; use a stable named tunnel or hosted backend for reliable remote
owner controls.

## Source coverage

| Source | Method | Default check interval | Current limit |
| --- | --- | --- | --- |
| OLJ | Public listing and detail pages | 20 seconds | Existing watcher behavior |
| Freelancer | Public all-jobs listing and project detail pages | 1 minute | About 50 recent cards; detail exposes budget but only relative posting time |
| Wellfound | Public page with Playwright and JobPosting data | 5 minutes | Public landing page covers a limited set of recent listings |
| Remotive | [Official public category RSS feeds](https://remotive.com/remote-jobs/rss-feed) | 30 minutes | Feed coverage depends on Remotive's public category feeds |
| PeoplePerHour | Playwright public page probe | 30 minutes | Bot challenge; currently blocked |
| Contra | Playwright public page probe | 30 minutes | Job feed redirects to login; currently blocked |
| We Work Remotely | [Official all-jobs RSS](https://weworkremotely.com/remote-job-rss-feed) | 1 minute | Feed publication timing is controlled by the site |
| Guru | Public newest projects page | 1 minute | HTTP 403 in the latest live probe; historical jobs remain stored |
| Jobicy | [Official RSS](https://jobicy.com/jobs-rss-feed) | 1 hour | Feed rules prohibit polling more than once per hour |
| Himalayas | [Public no-key jobs feed](https://himalayas.app/docs/data-dictionary) | 5 minutes | Feed exposes up to 100 recent listings per response; source cadence controls freshness |
| VirtualStaff.ph | Public browser-rendered jobs and detail responses | 1 minute | Public page exposes a limited set of job cards |

Blocked sources are reported in **Backend Status** and do not fabricate jobs or
attempt captcha solving or account login. Enable/disable a source and set its interval there.
The allowed minimums protect the source's access limits. Manual scans respect
those source intervals.


## Jobs and alerts

All discovered jobs share a source, title, company/client, description,
salary/budget when explicitly provided, work type, skills, location/remote,
posted time when provided, original link, and scrape time. Missing fields remain
blank; the watcher does not infer salary from Freelancer's average bids. Jobs
appear newest first, with source and stage filters, date and keyword filters,
and notification status. Owners can mark jobs **Saved**, **Applied**, or
**Ignored**. The 5,000 newest discoveries remain in the archive.

The watcher mirrors the archive to private Supabase `jobs` records after each
source with new discoveries. Customers see every stored job, newest first;
their selected niches only determine the match badge. Their only list control
is title and keyword search. Source names and advanced filters are owner-only.
The browser receives new rows through a server-side Realtime subscription and
also refreshes every 30 seconds.

The owner **Keywords** page edits include and exclude terms for new alerts.
Collection keeps every job visible on each accessible public listing page,
including jobs outside your niche. Keywords control alerts, not collection.
One-minute polling is a target for eligible sources, not a guarantee of seeing
a post within one minute of its creation. Source publication delays and the
watcher's sequential scan can add delay. The dashboard refreshes every 30 seconds.
Only newly discovered matching jobs can notify. The first fetch from a newly
enabled external source establishes a baseline without sending a backlog of
alerts. Later new matching jobs send Telegram messages with source, title,
summary, salary, posting time, link, and matched terms. SQLite stores job keys,
settings, and stages across restarts, preventing repeat notifications.

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`. If you use a separate
all-jobs chat, set `TELEGRAM_CHAT_ID_ALL_JOBS`; otherwise set it to the same chat.
Never commit `.env` or the SQLite database. The database is at
`data/jobs.sqlite3`; existing `data/job_events.json` is imported on first run
and kept as a backup.
