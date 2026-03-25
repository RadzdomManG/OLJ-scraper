# OnlineJobs Watcher Bot

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
