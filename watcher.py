import csv
import hashlib
import io
import json
import os
import re
import smtplib
import threading
import time
import webbrowser
from datetime import datetime, timezone
from email.mime.text import MIMEText
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from flask import Flask, Response, jsonify, request


# ======================
# ENV HELPERS
# ======================


def env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        print(f"Invalid int for {name}: {value}. Using default {default}.")
        return default


def csv_words(value):
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        parts = [str(v).strip().lower() for v in value]
    else:
        parts = [p.strip().lower() for p in str(value).split(",")]

    # Preserve order while removing duplicates/empties.
    deduped = []
    seen = set()
    for part in parts:
        if not part or part in seen:
            continue
        seen.add(part)
        deduped.append(part)
    return deduped


def safe_timezone(name, default="UTC"):
    try:
        return ZoneInfo(name)
    except Exception:
        print(f"Invalid timezone '{name}', falling back to {default}.")
        if default:
            try:
                return ZoneInfo(default)
            except Exception:
                pass
        return timezone.utc


# ======================
# CONFIG
# ======================

ONLINEJOBSPH_SEARCH_URL = os.environ.get(
    "ONLINEJOBSPH_SEARCH_URL", "https://www.onlinejobs.ph/jobseekers/jobsearch"
).strip()
INCLUDE_FREELANCER = env_flag("INCLUDE_FREELANCER", False)
LISTINGS_REQUIRE_KEYWORD_MATCH = env_flag("LISTINGS_REQUIRE_KEYWORD_MATCH", False)
STORE_ALL_FETCHED_JOBS = env_flag("STORE_ALL_FETCHED_JOBS", True)

JOB_SITES = [
    {
        "name": "OnlineJobsPH",
        "url": ONLINEJOBSPH_SEARCH_URL,
        "type": "onlinejobsph",
        "require_keyword_match": LISTINGS_REQUIRE_KEYWORD_MATCH,
    },
]

if INCLUDE_FREELANCER:
    JOB_SITES.append(
        {
            "name": "Freelancer",
            "url": os.environ.get("FREELANCER_SEARCH_URL", "https://www.freelancer.ph/jobs").strip(),
            "type": "freelancer",
            "require_keyword_match": LISTINGS_REQUIRE_KEYWORD_MATCH,
        }
    )

# Fixed scan cycle per product requirement.
CHECK_INTERVAL_SECONDS = 20
HEARTBEAT_INTERVAL = env_int("HEARTBEAT_INTERVAL", 3600)
POSTED_WITHIN_MINUTES = env_int("POSTED_WITHIN_MINUTES", 60)
STARTUP_BACKFILL_HOURS = max(1, env_int("STARTUP_BACKFILL_HOURS", 24))
MAX_RETRIES = env_int("MAX_RETRIES", 2)
TIMEOUT = env_int("TIMEOUT", 20)
SITE_FETCH_BUDGET_SECONDS = max(5, env_int("SITE_FETCH_BUDGET_SECONDS", 25))
MAX_STORED_EVENTS = env_int("MAX_STORED_EVENTS", 2000)
MAX_DETAIL_FETCH_PER_CYCLE = env_int("MAX_DETAIL_FETCH_PER_CYCLE", 5)
MAX_LOG_LINES = max(80, env_int("MAX_LOG_LINES", 600))

DATA_DIR = os.environ.get("DATA_DIR", "data")
SEEN_FILE = os.path.join(DATA_DIR, "seen_jobs.json")
EVENTS_FILE = os.path.join(DATA_DIR, "job_events.json")
TELEGRAM_SETTINGS_FILE = os.path.join(DATA_DIR, "telegram_settings.json")
FEEDBACK_FILE = os.path.join(DATA_DIR, "feedback.json")
ANALYTICS_FILE = os.path.join(DATA_DIR, "analytics.json")
PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolio_links.json")
OUTCOMES_FILE = os.path.join(DATA_DIR, "outcomes.json")
GOALS_FILE = os.path.join(DATA_DIR, "goals.json")
TEMPLATES_FILE = os.path.join(DATA_DIR, "templates.json")
INTERVIEWS_FILE = os.path.join(DATA_DIR, "interviews.json")
RULES_FILE = os.path.join(DATA_DIR, "rules.json")
TEAM_FILE = os.path.join(DATA_DIR, "team.json")

ONLINEJOBSPH_TIMEZONE = os.environ.get("ONLINEJOBSPH_TIMEZONE", "Asia/Manila")
DASHBOARD_TIMEZONE = os.environ.get("DASHBOARD_TIMEZONE", ONLINEJOBSPH_TIMEZONE)
ONLINEJOBSPH_TZ = safe_timezone(ONLINEJOBSPH_TIMEZONE, "UTC")
DASHBOARD_TZ = safe_timezone(DASHBOARD_TIMEZONE, "UTC")

KEYWORDS = csv_words(
    os.environ.get(
        "KEYWORDS",
        "ai,artificial intelligence,social media,video editor,video editing,content creator,ugc,user generated content,reels,shorts,tiktok,youtube,comfyui,stable diffusion,sdxl,prompt engineer",
    )
)
TRIGGER_WORDS_ENV_RAW = os.environ.get("TRIGGER_WORDS")
TRIGGER_WORDS = csv_words(TRIGGER_WORDS_ENV_RAW) if TRIGGER_WORDS_ENV_RAW is not None else list(KEYWORDS)
ONLINEJOBSPH_FETCH_DETAILS_FOR_KEYWORD_MATCH = env_flag("ONLINEJOBSPH_FETCH_DETAILS_FOR_KEYWORD_MATCH", False)

DRY_RUN = env_flag("DRY_RUN", False)
SEED_SEEN_ON_STARTUP = env_flag("SEED_SEEN_ON_STARTUP", False)
SEED_ONLY_IF_EMPTY = env_flag("SEED_ONLY_IF_EMPTY", True)

TELEGRAM_ENABLED = env_flag("TELEGRAM_ENABLED", True)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_CHAT_ID_VA = os.environ.get("TELEGRAM_CHAT_ID_VA", "-1003563189604").strip()
TELEGRAM_CHAT_ID_SMM = os.environ.get("TELEGRAM_CHAT_ID_SMM", "-1003646312429").strip()
TELEGRAM_CHAT_ID_VIDEO_EDITOR = os.environ.get("TELEGRAM_CHAT_ID_VIDEO_EDITOR", "-1003441216817").strip()
TELEGRAM_CHAT_ID_AI_AUTOMATION = os.environ.get("TELEGRAM_CHAT_ID_AI_AUTOMATION", "-1003777467110").strip()
TELEGRAM_CHAT_ID_ALL_JOBS = os.environ.get("TELEGRAM_CHAT_ID_ALL_JOBS", "-1003781890387").strip()
SEND_TO_ALL_JOBS_GROUP = env_flag("SEND_TO_ALL_JOBS_GROUP", True)
NOTIFY_ONLY_KEYWORD_MATCH = env_flag("NOTIFY_ONLY_KEYWORD_MATCH", False)
ENABLE_STATUS_NOTIFICATIONS = env_flag("ENABLE_STATUS_NOTIFICATIONS", False)
ENABLE_MULTI_CHANNEL_ALERTS = env_flag("ENABLE_MULTI_CHANNEL_ALERTS", True)
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
EMAIL_ALERTS_ENABLED = env_flag("EMAIL_ALERTS_ENABLED", False)
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = env_int("SMTP_PORT", 587)
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER).strip()
SMTP_TO = os.environ.get("SMTP_TO", "").strip()
TELEGRAM_MIN_INTERVAL_SECONDS = max(1, env_int("TELEGRAM_MIN_INTERVAL_SECONDS", 2))
TELEGRAM_MAX_SEND_RETRIES = max(1, env_int("TELEGRAM_MAX_SEND_RETRIES", 3))
TELEGRAM_MAX_MESSAGE_CHARS = max(1000, env_int("TELEGRAM_MAX_MESSAGE_CHARS", 3900))
UNSENT_BACKFILL_PER_CYCLE = max(0, env_int("UNSENT_BACKFILL_PER_CYCLE", 0))

NICHE_KEYWORDS = {
    "VA": [
        "virtual assistant", "executive assistant", "admin assistant", "administrative assistant",
        "general va", "data entry", "inbox management", "calendar management", "crm management",
        "operations assistant", "ecommerce assistant", "shopify assistant", "customer support va",
        "email support", "appointment setter", "research assistant", "real estate va",
        "bookkeeping assistant", "project coordinator", "personal assistant", "lead generation",
        "cold calling", "customer service", "live chat support",
    ],
    "SMM": [
        "social media manager", "social media specialist", "content creator", "content strategist",
        "social media marketing", "facebook ads", "instagram marketing", "tiktok manager",
        "community manager", "social media growth", "brand manager", "meta ads", "paid social",
        "ugc creator", "social media coordinator", "social media assistant", "media buyer",
        "digital marketer", "content calendar", "influencer manager",
    ],
    "VIDEO_EDITOR": [
        "video editor", "content editor", "short form editor", "reels editor", "tiktok editor",
        "youtube editor", "adobe premiere", "premiere pro", "final cut pro", "after effects",
        "motion graphics", "podcast editor", "davinci resolve", "video producer",
        "post production", "color grading", "sound design", "subtitle editor",
    ],
    "AI_AUTOMATION": [
        "ai automation", "zapier", "make.com", "integromat", "workflow automation", "ai specialist",
        "chatgpt automation", "prompt engineer", "api integration", "python automation",
        "no-code automation", "crm automation", "airtable automation", "ghl", "go high level",
        "highlevel", "n8n", "automation specialist", "process automation", "marketing automation",
        "sales automation", "webhook", "rest api", "google apps script", "power automate", "rpa",
    ],
}

NICHE_CHAT_IDS = {
    "VA": TELEGRAM_CHAT_ID_VA,
    "SMM": TELEGRAM_CHAT_ID_SMM,
    "VIDEO_EDITOR": TELEGRAM_CHAT_ID_VIDEO_EDITOR,
    "AI_AUTOMATION": TELEGRAM_CHAT_ID_AI_AUTOMATION,
    "ALL_JOBS": TELEGRAM_CHAT_ID_ALL_JOBS or TELEGRAM_CHAT_ID,
}
BROADCAST_TO_ALL_GROUPS = env_flag("BROADCAST_TO_ALL_GROUPS", False)

ENABLE_DUPLICATE_SUPPRESSION = env_flag("ENABLE_DUPLICATE_SUPPRESSION", False)
DUPLICATE_WINDOW_HOURS = max(1, env_int("DUPLICATE_WINDOW_HOURS", 72))
ENABLE_LEARNING_LOOP = env_flag("ENABLE_LEARNING_LOOP", True)
ENABLE_DIGEST_NOTIFICATIONS = env_flag("ENABLE_DIGEST_NOTIFICATIONS", False)
DIGEST_SEND_HOUR_LOCAL = min(23, max(0, env_int("DIGEST_SEND_HOUR_LOCAL", 21)))
PROPOSAL_TONE = os.environ.get("PROPOSAL_TONE", "confident").strip().lower()
AUTO_FOLLOWUP_ENABLED = env_flag("AUTO_FOLLOWUP_ENABLED", False)
FOLLOWUP_AFTER_HOURS = max(1, env_int("FOLLOWUP_AFTER_HOURS", 24))
FOLLOWUP_MAX_PER_EVENT = max(1, env_int("FOLLOWUP_MAX_PER_EVENT", 2))
FOLLOWUP_MAX_PER_CYCLE = max(0, env_int("FOLLOWUP_MAX_PER_CYCLE", 3))
ENABLE_INTERVIEW_PREP = env_flag("ENABLE_INTERVIEW_PREP", True)
ENABLE_PORTFOLIO_MATCHING = env_flag("ENABLE_PORTFOLIO_MATCHING", True)
ENABLE_COMPETITOR_DENSITY = env_flag("ENABLE_COMPETITOR_DENSITY", True)
ENABLE_BUDGET_NORMALIZATION = env_flag("ENABLE_BUDGET_NORMALIZATION", True)
PROFILE_SKILLS = csv_words(os.environ.get("PROFILE_SKILLS", "video editing,social media management,ai tools,content creation,copywriting"))
WORKSPACE_NAME = os.environ.get("WORKSPACE_NAME", "default").strip() or "default"

ENABLE_UI = env_flag("ENABLE_UI", True)
UI_HOST = os.environ.get("UI_HOST", "0.0.0.0")
UI_PORT = env_int("UI_PORT", 8080)
UI_REFRESH_SECONDS = max(2, env_int("UI_REFRESH_SECONDS", 5))
DESKTOP_APP = env_flag("DESKTOP_APP", True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
}

ONLINEJOBS_BASE_URL = "https://www.onlinejobs.ph"
FREELANCER_BASE_URL = "https://www.freelancer.ph"

session = requests.Session()
session.headers.update(HEADERS)

app = Flask(__name__)

state_lock = threading.Lock()
state = {
    "seen": set(),
    "events": [],
    "event_keys": set(),
    "telegram": {
        "enabled": TELEGRAM_ENABLED,
        "bot_token": "",
        "chat_id": "",
        "trigger_words": list(TRIGGER_WORDS),
        "updated_at": "",
    },
    "started_at": "",
    "last_check_at": "",
    "last_cycle_summary": {},
    "last_error": "",
    "last_heartbeat_ts": 0.0,
    "watcher_running": False,
    "next_check_due_ts": 0.0,
    "check_interval_seconds": CHECK_INTERVAL_SECONDS,
    "auto_scan_paused": False,
    "manual_scan_requested": False,
    "scan_in_progress": False,
    "last_scan_started_at": "",
    "last_scan_finished_at": "",
    "last_scan_result": "idle",
    "logs": [],
    "feedback": {},
    "analytics": {
        "applied": {},
        "wins": {},
    },
    "recent_fingerprints": {},
    "last_digest_date": "",
    "followups_sent": {},
    "outcomes": {},
    "metrics": {
        "scan_cycles_total": 0,
        "scan_cycles_failed": 0,
        "notifications_attempted": 0,
        "notifications_sent": 0,
        "events_created": 0,
    },
    "telegram_last_sent_ts": 0.0,
    "auto_followup_enabled": AUTO_FOLLOWUP_ENABLED,
}

watcher_thread_lock = threading.Lock()
watcher_thread = None
watcher_stop_event = threading.Event()
scan_wakeup_event = threading.Event()
scan_cycle_lock = threading.Lock()


# ======================
# UTILS
# ======================


def now_utc_iso():
    return datetime.now(timezone.utc).isoformat()


def ui_url():
    host = (UI_HOST or "").strip()
    if host in {"", "0.0.0.0", "::"}:
        host = "127.0.0.1"
    return f"http://{host}:{UI_PORT}"


def format_local_time(iso_text, tzinfo):
    if not iso_text:
        return ""
    try:
        dt = datetime.fromisoformat(iso_text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tzinfo).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_text


def parse_iso_to_utc(iso_text):
    iso_text = (iso_text or "").strip()
    if not iso_text:
        return None
    try:
        parsed = datetime.fromisoformat(iso_text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def truncate_text(text, max_len=220):
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def mask_telegram_token(token):
    token = (token or "").strip()
    if len(token) <= 10:
        return "*" * len(token)
    return f"{token[:6]}...{token[-4:]}"


def add_runtime_log(message, level="info"):
    ts_local = datetime.now(DASHBOARD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "ts_local": ts_local,
        "level": (level or "info").strip().lower(),
        "message": str(message),
    }
    with state_lock:
        logs = state.setdefault("logs", [])
        logs.insert(0, entry)
        if len(logs) > MAX_LOG_LINES:
            del logs[MAX_LOG_LINES:]
    print(f"[{ts_local}] {entry['message']}")


def normalize_scan_interval_seconds(value, fallback=None):
    # Runtime scan interval is intentionally fixed.
    return CHECK_INTERVAL_SECONDS


def get_runtime_scan_interval_seconds():
    with state_lock:
        raw_value = state.get("check_interval_seconds", CHECK_INTERVAL_SECONDS)
    return normalize_scan_interval_seconds(raw_value, fallback=CHECK_INTERVAL_SECONDS)


def set_runtime_scan_interval_seconds(seconds, reset_next_scan=True):
    normalized = normalize_scan_interval_seconds(seconds, fallback=CHECK_INTERVAL_SECONDS)
    with state_lock:
        state["check_interval_seconds"] = normalized
        if reset_next_scan and state.get("watcher_running"):
            state["next_check_due_ts"] = time.time() + normalized
    return normalized


def event_age_minutes(event):
    now_dt = datetime.now(timezone.utc)

    # Prefer dynamic age from posted timestamp so colors keep updating over time.
    posted_iso = (event.get("posted_at_iso") or "").strip()
    posted_dt = parse_iso_to_utc(posted_iso)
    if posted_dt:
        age_seconds = (now_dt - posted_dt).total_seconds()
        return max(0, int(age_seconds // 60))

    # Fallback to detected timestamp when posted time is unavailable.
    detected_iso = (event.get("detected_at") or "").strip()
    detected_dt = parse_iso_to_utc(detected_iso)
    if detected_dt:
        age_seconds = (now_dt - detected_dt).total_seconds()
        return max(0, int(age_seconds // 60))

    # Last fallback for legacy records.
    age_seconds = event.get("age_seconds_at_detection")
    if isinstance(age_seconds, (int, float)):
        return max(0, int(age_seconds // 60))
    return None


def age_bucket_from_minutes(minutes):
    if minutes is None:
        return "unknown"
    if minutes < 60:
        return "green"
    if minutes < 180:
        return "yellow"
    return "red"


def event_date_key(event):
    for key in ("detected_at_local", "posted_at", "detected_at", "posted_at_iso"):
        text = str(event.get(key, "")).strip()
        match = re.match(r"^(\d{4}-\d{2}-\d{2})", text)
        if match:
            return match.group(1)
    return "Unknown"


def event_posted_datetime_utc(event):
    posted_iso = (event.get("posted_at_iso") or "").strip()
    if posted_iso:
        posted_dt = parse_iso_to_utc(posted_iso)
        if posted_dt:
            return posted_dt

    posted_raw = (event.get("posted_at") or "").strip()
    parsed_local = parse_onlinejobs_posted_at_any(posted_raw)
    if parsed_local:
        return parsed_local.astimezone(timezone.utc)
    return None


def event_within_current_window(event):
    if str(event.get("site_type", "")).strip() != "onlinejobsph":
        return True
    within, _, _ = is_onlinejobs_within_window(event)
    return bool(within)


def prune_events_outside_window(events):
    pruned = [e for e in (events or []) if event_within_current_window(e)]
    pruned.sort(
        key=lambda e: (
            int((enrich_event_for_ui(e, include_heavy=False).get("posted_ts") or 0)),
            str(e.get("detected_at", "")),
        ),
        reverse=True,
    )
    if len(pruned) > MAX_STORED_EVENTS:
        pruned = pruned[:MAX_STORED_EVENTS]
    keys = {e.get("event_key", "") for e in pruned if e.get("event_key")}
    return pruned, keys


def age_bucket_counts(events):
    counts = {"green": 0, "yellow": 0, "red": 0}
    for event in events:
        bucket = age_bucket_from_minutes(event_age_minutes(event))
        if bucket in counts:
            counts[bucket] += 1
    return counts


def enrich_event_for_ui(event, include_heavy=False, all_events=None):
    enriched = dict(event)
    minutes = event_age_minutes(enriched)
    bucket = age_bucket_from_minutes(minutes)
    severity_label_map = {
        "green": "New",
        "yellow": "Semi-old",
        "red": "Old",
        "unknown": "Unknown",
    }
    enriched["age_minutes"] = minutes
    enriched["age_bucket"] = bucket
    enriched["severity_label"] = severity_label_map.get(bucket, "Unknown")
    enriched["event_date"] = event_date_key(enriched)
    enriched["posted_display"] = format_onlinejobs_posted_display(enriched)
    posted_dt_utc = event_posted_datetime_utc(enriched)
    enriched["posted_ts"] = int(posted_dt_utc.timestamp()) if posted_dt_utc else 0
    enriched["last_seen_at_local"] = enriched.get("last_seen_at_local", "")
    intelligence = score_event(enriched)
    enriched["job_score"] = intelligence["score"]
    enriched["priority"] = intelligence["priority"]
    enriched["intent"] = intelligence["intent"]
    enriched["employer_quality_score"] = intelligence["employer_quality_score"]
    enriched["reply_opportunity"] = intelligence.get("reply_opportunity", "low")
    enriched["reply_signals"] = intelligence.get("reply_signals", [])
    enriched["repost_suspected"] = bool(enriched.get("repost_suspected", False))
    if ENABLE_BUDGET_NORMALIZATION:
        enriched.update(budget_context(enriched))
    if include_heavy:
        reference_events = all_events if isinstance(all_events, list) else []
        enriched["job_brief"] = build_job_brief(enriched, reference_events)
        enriched["portfolio_links"] = select_portfolio_links(enriched)
    else:
        enriched["job_brief"] = {"competitor_density": {"density": "unknown", "score": 0}}
        enriched["portfolio_links"] = []
    return enriched


def normalize_telegram_settings(raw):
    if not isinstance(raw, dict):
        raw = {}
    return {
        "enabled": bool(raw.get("enabled", TELEGRAM_ENABLED)),
        "bot_token": str(raw.get("bot_token", "")).strip(),
        "chat_id": str(raw.get("chat_id", "")).strip(),
        "trigger_words": csv_words(raw.get("trigger_words", [])),
        "updated_at": str(raw.get("updated_at", "")).strip(),
    }


def save_telegram_settings(settings):
    normalized = normalize_telegram_settings(settings)
    normalized["updated_at"] = now_utc_iso()
    save_json_file(TELEGRAM_SETTINGS_FILE, normalized)
    return normalized


def load_telegram_settings():
    saved = normalize_telegram_settings(load_json_file(TELEGRAM_SETTINGS_FILE, {}))
    trigger_words = list(saved.get("trigger_words", [])) or list(TRIGGER_WORDS)
    if TRIGGER_WORDS_ENV_RAW is not None:
        trigger_words = csv_words(TRIGGER_WORDS_ENV_RAW)

    merged = {
        "enabled": TELEGRAM_ENABLED if "TELEGRAM_ENABLED" in os.environ else saved["enabled"],
        "bot_token": TELEGRAM_BOT_TOKEN or saved["bot_token"],
        "chat_id": TELEGRAM_CHAT_ID or saved["chat_id"],
        "trigger_words": trigger_words,
        "updated_at": saved["updated_at"],
    }
    persisted = save_telegram_settings(merged)
    return persisted


def get_runtime_telegram_settings():
    with state_lock:
        snapshot = dict(state.get("telegram", {}))
    return normalize_telegram_settings(snapshot)


def update_runtime_telegram_settings(bot_token=None, chat_id=None, enabled=None, trigger_words=None, persist=True):
    with state_lock:
        current = normalize_telegram_settings(state.get("telegram", {}))
    if bot_token is not None:
        current["bot_token"] = str(bot_token).strip()
    if chat_id is not None:
        current["chat_id"] = str(chat_id).strip()
    if enabled is not None:
        current["enabled"] = bool(enabled)
    if trigger_words is not None:
        current["trigger_words"] = csv_words(trigger_words)

    if persist:
        current = save_telegram_settings(current)
    else:
        current["updated_at"] = now_utc_iso()

    with state_lock:
        state["telegram"] = current

    return current


def get_active_trigger_words():
    runtime = get_runtime_telegram_settings()
    words = csv_words(runtime.get("trigger_words", []))
    if words:
        return words
    return list(TRIGGER_WORDS)


def detect_event_niches(event):
    text = " ".join(
        [
            event.get("title", ""),
            event.get("description", ""),
            event.get("type_of_work", ""),
            event.get("wage_salary", ""),
            event.get("hours_per_week", ""),
        ]
    )
    matched = []
    for niche, words in NICHE_KEYWORDS.items():
        strict = (niche == "AI_AUTOMATION")
        if keyword_match(text, words=words, match_if_empty=False, strict=strict):
            matched.append(niche)
    return matched


def send_telegram_niche_routed(message, title="Job Alert", event=None):
    sent_any = False
    delivered_chat_ids = set()

    # Optional mirror channel for all jobs.
    all_jobs_chat = (NICHE_CHAT_IDS.get("ALL_JOBS") or "").strip()
    if SEND_TO_ALL_JOBS_GROUP and all_jobs_chat:
        if send_telegram(message, title=title, chat_id=all_jobs_chat):
            sent_any = True
            delivered_chat_ids.add(all_jobs_chat)

    # Optional broadcast mode: send every job to every configured group.
    if BROADCAST_TO_ALL_GROUPS:
        for _, chat_id in NICHE_CHAT_IDS.items():
            chat_id = (chat_id or "").strip()
            if not chat_id or chat_id in delivered_chat_ids:
                continue
            if send_telegram(message, title=title, chat_id=chat_id):
                sent_any = True
                delivered_chat_ids.add(chat_id)
        return sent_any

    # Send to niche groups that match.
    event_like = event if isinstance(event, dict) else {"title": title, "description": message}
    matched_niches = detect_event_niches(event_like)
    for niche in matched_niches:
        chat_id = (NICHE_CHAT_IDS.get(niche) or "").strip()
        if not chat_id or chat_id in delivered_chat_ids:
            continue
        if send_telegram(message, title=title, chat_id=chat_id):
            sent_any = True
            delivered_chat_ids.add(chat_id)

    return sent_any


def send_telegram(message, title="Job Alert", bot_token=None, chat_id=None):
    if DRY_RUN:
        print(f"[DRY RUN] Telegram skipped | {title} | {message[:220]}")
        return True

    runtime = get_runtime_telegram_settings()
    if bot_token is None:
        bot_token = runtime["bot_token"]
    if chat_id is None:
        chat_id = runtime["chat_id"]

    if not runtime["enabled"]:
        print("Telegram is disabled. Notification skipped.")
        return False

    if not bot_token or not chat_id:
        print("Telegram token/chat_id missing. Notification skipped.")
        return False

    def split_message_chunks(text, limit):
        text = str(text or "")
        if len(text) <= limit:
            return [text]
        chunks = []
        remaining = text
        while len(remaining) > limit:
            cut = remaining.rfind("\n", 0, limit)
            if cut <= 0:
                cut = remaining.rfind(" ", 0, limit)
            if cut <= 0:
                cut = limit
            chunk = remaining[:cut].rstrip()
            if chunk:
                chunks.append(chunk)
            remaining = remaining[cut:].lstrip()
        if remaining:
            chunks.append(remaining)
        return chunks

    full_text = f"{title}\n{message}".strip()
    chunks = split_message_chunks(full_text, TELEGRAM_MAX_MESSAGE_CHARS)

    for idx, chunk in enumerate(chunks, start=1):
        payload = {
            "chat_id": str(chat_id),
            "text": chunk if len(chunks) == 1 else f"{chunk}\n\n({idx}/{len(chunks)})",
            "disable_web_page_preview": False,
        }

        for attempt in range(1, TELEGRAM_MAX_SEND_RETRIES + 1):
            try:
                with state_lock:
                    last_ts = float(state.get("telegram_last_sent_ts", 0.0) or 0.0)
                now_ts = time.time()
                wait_needed = TELEGRAM_MIN_INTERVAL_SECONDS - (now_ts - last_ts)
                if wait_needed > 0:
                    time.sleep(wait_needed)

                response = requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json=payload,
                    timeout=10,
                )

                if response.status_code == 429:
                    retry_after = 2
                    try:
                        body = response.json()
                        retry_after = int(body.get("parameters", {}).get("retry_after", retry_after))
                    except Exception:
                        pass
                    if attempt < TELEGRAM_MAX_SEND_RETRIES:
                        time.sleep(max(1, retry_after))
                        continue
                    print(f"Telegram rate limit hit after retries. retry_after={retry_after}s")
                    return False

                response.raise_for_status()
                body = response.json()
                if not body.get("ok"):
                    print(f"Telegram API returned non-ok: {body}")
                    return False
                with state_lock:
                    state["telegram_last_sent_ts"] = time.time()
                break
            except Exception as e:
                if attempt >= TELEGRAM_MAX_SEND_RETRIES:
                    print("Telegram send error:", e)
                    return False
                time.sleep(min(5, attempt + 1))

    return True


def send_webhook(webhook_url, message, title="Job Alert"):
    if not webhook_url:
        return False
    payload = {"text": f"{title}\n{message}".strip()}
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print("Webhook send error:", e)
        return False


def send_email_alert(message, title="Job Alert"):
    if not EMAIL_ALERTS_ENABLED:
        return False
    if not (SMTP_HOST and SMTP_FROM and SMTP_TO):
        return False
    msg = MIMEText(message, "plain", "utf-8")
    msg["Subject"] = title
    msg["From"] = SMTP_FROM
    msg["To"] = SMTP_TO
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [SMTP_TO], msg.as_string())
        return True
    except Exception as e:
        print("Email send error:", e)
        return False


def load_json_file(path, default):
    if not os.path.exists(path):
        return default
    try:
        # utf-8-sig also accepts utf-8 with BOM (common when edited from PowerShell/Windows tools).
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception as e:
        print(f"Could not load {path}: {e}")
        return default


def save_json_file(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)


def build_seen_key(site_type, job_id):
    return f"{site_type}:{job_id}"


def build_seen_key_for_job(site_type, job_id, job):
    base_key = build_seen_key(site_type, job_id)
    if site_type != "onlinejobsph" or not isinstance(job, dict):
        return base_key

    posted_text = str(job.get("posted_at", "")).strip()
    posted_dt = parse_onlinejobs_posted_at_any(posted_text)
    if not posted_dt:
        return base_key
    return f"{base_key}:{posted_dt.strftime('%Y-%m-%d %H:%M:%S')}"


def normalize_legacy_seen_item(value):
    text = str(value)
    if ":" in text:
        return text

    legacy_id_match = re.search(r"(\d+)$", text)
    if not legacy_id_match:
        return None

    return build_seen_key("onlinejobsph", legacy_id_match.group(1))


def load_seen_jobs():
    raw = load_json_file(SEEN_FILE, [])

    if isinstance(raw, list):
        seen = set()
        for value in raw:
            normalized = normalize_legacy_seen_item(value)
            if normalized:
                seen.add(normalized)
        return seen

    if isinstance(raw, dict):
        seen = set()
        for site_type, ids in raw.items():
            if not isinstance(ids, list):
                continue
            for job_id in ids:
                seen.add(build_seen_key(site_type, str(job_id)))
        return seen

    return set()


def save_seen_jobs(seen):
    save_json_file(SEEN_FILE, sorted(seen))


def normalize_event(item):
    if not isinstance(item, dict):
        return None

    site_type = str(item.get("site_type", "")).strip()
    job_id = str(item.get("job_id", "")).strip()
    event_key = str(item.get("event_key", "")).strip()
    if not event_key and site_type and job_id:
        event_key = build_seen_key(site_type, job_id)
    if not event_key:
        return None

    base = {
        "event_key": event_key,
        "site": str(item.get("site", "")).strip(),
        "site_type": site_type,
        "job_id": job_id,
        "title": str(item.get("title", "")).strip(),
        "url": str(item.get("url", "")).strip(),
        "description": str(item.get("description", "")).strip(),
        "posted_at": str(item.get("posted_at", "")).strip(),
        "posted_at_iso": str(item.get("posted_at_iso", "")).strip(),
        "detected_at": str(item.get("detected_at", "")).strip(),
        "detected_at_local": str(item.get("detected_at_local", "")).strip(),
        "last_seen_at": str(item.get("last_seen_at", item.get("detected_at", ""))).strip(),
        "last_seen_at_local": str(item.get("last_seen_at_local", item.get("detected_at_local", ""))).strip(),
        "age_seconds_at_detection": item.get("age_seconds_at_detection", None),
        "type_of_work": str(item.get("type_of_work", "")).strip(),
        "wage_salary": str(item.get("wage_salary", "")).strip(),
        "hours_per_week": str(item.get("hours_per_week", "")).strip(),
        "date_updated": str(item.get("date_updated", "")).strip(),
        "keyword_matched": bool(item.get("keyword_matched", False)),
        "notification_sent": bool(item.get("notification_sent", False)),
        "repost_suspected": bool(item.get("repost_suspected", False)),
        "fingerprint": str(item.get("fingerprint", "")).strip(),
        "job_score": item.get("job_score", None),
        "priority": str(item.get("priority", "")).strip(),
        "intent": item.get("intent", {}) if isinstance(item.get("intent", {}), dict) else {},
        "employer_quality_score": item.get("employer_quality_score", None),
        "reply_opportunity": str(item.get("reply_opportunity", "")).strip(),
        "reply_signals": item.get("reply_signals", []) if isinstance(item.get("reply_signals", []), list) else [],
    }
    if "keyword_matched" not in item:
        base["keyword_matched"] = event_matches_niche_keywords(base)
    return base


def load_job_events():
    raw = load_json_file(EVENTS_FILE, [])
    if not isinstance(raw, list):
        return [], set()

    events = []
    keys = set()
    for item in raw:
        event = normalize_event(item)
        if not event:
            continue
        if event["event_key"] in keys:
            continue
        keys.add(event["event_key"])
        events.append(event)

    events.sort(key=lambda e: e.get("detected_at", ""), reverse=True)
    if len(events) > MAX_STORED_EVENTS:
        events = events[:MAX_STORED_EVENTS]
        keys = {e["event_key"] for e in events}

    return events, keys


def save_job_events(events):
    save_json_file(EVENTS_FILE, events)


def normalize_match_text(value):
    normalized = re.sub(r"[^a-z0-9]+", " ", (value or "").lower())
    return re.sub(r"\s+", " ", normalized).strip()


def keyword_match(text, words=None, match_if_empty=True, strict=False):
    active_words = KEYWORDS if words is None else csv_words(words)
    if not active_words:
        return match_if_empty

    raw_text = (text or "").lower()
    normalized_text = f" {normalize_match_text(raw_text)} "

    for word in active_words:
        token = (word or "").strip().lower()
        if not token:
            continue

        # Fast path for longer direct substrings.
        if (not strict) and len(token) >= 3 and token in raw_text:
            return True

        # Robust path: punctuation/hyphen/case-insensitive normalization.
        normalized_token = normalize_match_text(token)
        if not normalized_token:
            continue
        if " " in normalized_token:
            if normalized_token in normalized_text:
                return True
        else:
            if f" {normalized_token} " in normalized_text:
                return True

    return False


def event_matches_niche_keywords(event):
    trigger_words = get_active_trigger_words()
    if not trigger_words:
        return False
    parts = [
        event.get("title", ""),
        event.get("description", ""),
        event.get("type_of_work", ""),
        event.get("wage_salary", ""),
        event.get("hours_per_week", ""),
        event.get("date_updated", ""),
    ]
    return keyword_match(" ".join(parts), words=trigger_words, match_if_empty=False)


def parse_money_value(text):
    values = re.findall(r"(\d+(?:\.\d+)?)", str(text or ""))
    if not values:
        return None
    nums = []
    for value in values:
        try:
            nums.append(float(value))
        except Exception:
            continue
    if not nums:
        return None
    return max(nums)


def detect_hiring_intent(text):
    text = (text or "").lower()
    intent_words = {
        "urgent": ["urgent", "asap", "immediately", "today", "right away", "start now"],
        "long_term": ["long term", "full time", "ongoing", "permanent", "monthly"],
        "high_budget": ["competitive pay", "high budget", "$", "usd", "bonus", "raise"],
        "trial": ["test task", "trial", "sample work", "unpaid", "probation"],
    }
    result = {}
    for key, words in intent_words.items():
        result[key] = any(w in text for w in words)
    return result


def detect_reply_opportunity(text):
    text = (text or "").lower()
    signals = ["active", "responding quickly", "online now", "interviewing now", "hiring now", "immediate start"]
    matched = [s for s in signals if s in text]
    if len(matched) >= 2:
        return "high", matched
    if len(matched) == 1:
        return "medium", matched
    return "low", []


def event_fingerprint(event):
    text = normalize_match_text(
        " ".join(
            [
                event.get("site_type", ""),
                event.get("title", ""),
                event.get("description", ""),
                event.get("type_of_work", ""),
            ]
        )
    )
    if not text:
        text = event.get("event_key", "")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_work_hours(text):
    values = re.findall(r"(\d+)", str(text or ""))
    if not values:
        return None
    try:
        return int(values[0])
    except Exception:
        return None


def get_learning_bias_for_event(event):
    if not ENABLE_LEARNING_LOOP:
        return 0
    with state_lock:
        feedback = dict(state.get("feedback", {}))
    good_words = csv_words(feedback.get("good_words", []))
    bad_words = csv_words(feedback.get("bad_words", []))
    haystack = normalize_match_text(
        f"{event.get('title', '')} {event.get('description', '')} {event.get('type_of_work', '')}"
    )
    score = 0
    for word in good_words:
        token = normalize_match_text(word)
        if token and token in haystack:
            score += 2
    for word in bad_words:
        token = normalize_match_text(word)
        if token and token in haystack:
            score -= 2
    return max(-15, min(15, score))


def score_event(event):
    score = 50
    intent = detect_hiring_intent(f"{event.get('title', '')} {event.get('description', '')}")
    reply_level, reply_signals = detect_reply_opportunity(f"{event.get('title', '')} {event.get('description', '')}")

    if event.get("keyword_matched"):
        score += 12
    age_minutes = event_age_minutes(event)
    if age_minutes is not None:
        if age_minutes <= 10:
            score += 18
        elif age_minutes <= 30:
            score += 10
        elif age_minutes > 120:
            score -= 12

    wage = parse_money_value(event.get("wage_salary", ""))
    if wage is not None:
        if wage >= 15:
            score += 8
        elif wage <= 3:
            score -= 12

    hours = parse_work_hours(event.get("hours_per_week", ""))
    if hours is not None and hours >= 30:
        score += 4

    if intent.get("urgent"):
        score += 10
    if intent.get("long_term"):
        score += 6
    if intent.get("trial"):
        score -= 8
    if reply_level == "high":
        score += 10
    elif reply_level == "medium":
        score += 5

    # Employer quality heuristic from job post signals.
    employer_quality = 60
    desc_lower = (event.get("description", "") or "").lower()
    red_flags = ["unpaid", "commission only", "free test", "no payment", "interview fee"]
    green_flags = ["clear scope", "weekly pay", "long term", "fixed salary", "bonus"]
    if any(flag in desc_lower for flag in red_flags):
        employer_quality -= 25
    if any(flag in desc_lower for flag in green_flags):
        employer_quality += 15

    score += (employer_quality - 60) // 3
    score += get_learning_bias_for_event(event)

    score = max(0, min(100, int(score)))
    priority = "low"
    if score >= 75:
        priority = "high"
    elif score >= 55:
        priority = "medium"

    return {
        "score": score,
        "intent": intent,
        "employer_quality_score": max(0, min(100, employer_quality)),
        "priority": priority,
        "reply_opportunity": reply_level,
        "reply_signals": reply_signals,
    }


def load_feedback():
    raw = load_json_file(FEEDBACK_FILE, {})
    if not isinstance(raw, dict):
        return {"good_words": [], "bad_words": [], "event_feedback": {}}
    return {
        "good_words": csv_words(raw.get("good_words", [])),
        "bad_words": csv_words(raw.get("bad_words", [])),
        "event_feedback": raw.get("event_feedback", {}) if isinstance(raw.get("event_feedback", {}), dict) else {},
    }


def save_feedback(feedback):
    normalized = {
        "good_words": csv_words(feedback.get("good_words", [])),
        "bad_words": csv_words(feedback.get("bad_words", [])),
        "event_feedback": feedback.get("event_feedback", {}),
        "updated_at": now_utc_iso(),
    }
    save_json_file(FEEDBACK_FILE, normalized)
    return normalized


def load_analytics():
    raw = load_json_file(ANALYTICS_FILE, {"applied": {}, "wins": {}})
    if not isinstance(raw, dict):
        return {"applied": {}, "wins": {}}
    applied = raw.get("applied", {})
    wins = raw.get("wins", {})
    if not isinstance(applied, dict):
        applied = {}
    if not isinstance(wins, dict):
        wins = {}
    return {"applied": applied, "wins": wins}


def save_analytics(analytics):
    normalized = {
        "applied": analytics.get("applied", {}),
        "wins": analytics.get("wins", {}),
        "updated_at": now_utc_iso(),
    }
    save_json_file(ANALYTICS_FILE, normalized)
    return normalized


def load_portfolio_links():
    raw = load_json_file(PORTFOLIO_FILE, {})
    if not isinstance(raw, dict):
        return {}
    cleaned = {}
    for key, value in raw.items():
        topic = normalize_match_text(key)
        if not topic:
            continue
        if isinstance(value, list):
            cleaned[topic] = [str(v).strip() for v in value if str(v).strip()]
        else:
            text = str(value).strip()
            if text:
                cleaned[topic] = [text]
    return cleaned


def save_outcomes(outcomes):
    normalized = outcomes if isinstance(outcomes, dict) else {}
    save_json_file(OUTCOMES_FILE, normalized)
    return normalized


def load_outcomes():
    raw = load_json_file(OUTCOMES_FILE, {})
    return raw if isinstance(raw, dict) else {}


def load_goals():
    raw = load_json_file(GOALS_FILE, {})
    if not isinstance(raw, dict):
        return {"daily_apply_target": 5, "daily_followup_target": 3}
    return {
        "daily_apply_target": int(raw.get("daily_apply_target", 5)),
        "daily_followup_target": int(raw.get("daily_followup_target", 3)),
    }


def save_goals(goals):
    normalized = {
        "daily_apply_target": max(0, int(goals.get("daily_apply_target", 5))),
        "daily_followup_target": max(0, int(goals.get("daily_followup_target", 3))),
        "updated_at": now_utc_iso(),
    }
    save_json_file(GOALS_FILE, normalized)
    return normalized


def load_templates():
    raw = load_json_file(TEMPLATES_FILE, {})
    if not isinstance(raw, dict):
        return {"concise": "", "consultative": "", "premium": ""}
    return {
        "concise": str(raw.get("concise", "")).strip(),
        "consultative": str(raw.get("consultative", "")).strip(),
        "premium": str(raw.get("premium", "")).strip(),
    }


def save_templates(data):
    normalized = {
        "concise": str(data.get("concise", "")).strip(),
        "consultative": str(data.get("consultative", "")).strip(),
        "premium": str(data.get("premium", "")).strip(),
        "updated_at": now_utc_iso(),
    }
    save_json_file(TEMPLATES_FILE, normalized)
    return normalized


def load_interviews():
    raw = load_json_file(INTERVIEWS_FILE, [])
    return raw if isinstance(raw, list) else []


def save_interviews(items):
    payload = items if isinstance(items, list) else []
    save_json_file(INTERVIEWS_FILE, payload)
    return payload


def load_rules():
    raw = load_json_file(RULES_FILE, [])
    return raw if isinstance(raw, list) else []


def save_rules(items):
    payload = items if isinstance(items, list) else []
    save_json_file(RULES_FILE, payload)
    return payload


def load_team_data():
    raw = load_json_file(TEAM_FILE, {"comments": []})
    if not isinstance(raw, dict):
        return {"comments": []}
    comments = raw.get("comments", [])
    if not isinstance(comments, list):
        comments = []
    return {"comments": comments}


def save_team_data(data):
    payload = {"comments": data.get("comments", []) if isinstance(data, dict) else []}
    save_json_file(TEAM_FILE, payload)
    return payload


def budget_context(event):
    wage_text = event.get("wage_salary", "")
    value = parse_money_value(wage_text)
    if value is None:
        return {"normalized_monthly_usd": None, "budget_type": "unknown"}
    text = str(wage_text).lower()
    hours = parse_work_hours(event.get("hours_per_week", "")) or 20
    if "hour" in text or "/hr" in text:
        monthly = value * hours * 4
        budget_type = "hourly"
    elif "week" in text:
        monthly = value * 4
        budget_type = "weekly"
    else:
        monthly = value
        budget_type = "monthly_or_fixed"
    return {"normalized_monthly_usd": round(monthly, 2), "budget_type": budget_type}


def estimate_competitor_density(event, events):
    if not ENABLE_COMPETITOR_DENSITY:
        return {"density": "unknown", "score": 0}
    title_tokens = set(normalize_match_text(event.get("title", "")).split())
    title_tokens = {t for t in title_tokens if len(t) >= 4}
    if not title_tokens:
        return {"density": "low", "score": 10}
    similar = 0
    for other in events:
        if other.get("event_key") == event.get("event_key"):
            continue
        other_tokens = set(normalize_match_text(other.get("title", "")).split())
        if len(title_tokens.intersection(other_tokens)) >= 2:
            similar += 1
    density = "low"
    if similar >= 6:
        density = "high"
    elif similar >= 3:
        density = "medium"
    return {"density": density, "score": min(100, similar * 12)}


def build_job_brief(event, all_events):
    intent = detect_hiring_intent(f"{event.get('title', '')} {event.get('description', '')}")
    risks = []
    if intent.get("trial"):
        risks.append("Possible unpaid/trial-heavy hiring flow")
    if event.get("repost_suspected"):
        risks.append("Potential repost / recycled listing")
    if event_age_minutes(event) and event_age_minutes(event) > 90:
        risks.append("Late application window")
    if not risks:
        risks.append("No major red flags detected from listing text")
    density = estimate_competitor_density(event, all_events)
    return {
        "client_needs_summary": truncate_text(
            f"{event.get('title', '')}. Focus appears to be {event.get('type_of_work') or 'role execution'} with quick turnaround.",
            220,
        ),
        "risks": risks,
        "win_strategy": [
            "Lead with a relevant sample in first 2 lines",
            "Offer a 24-48h first milestone",
            "Clarify communication cadence and revisions",
        ],
        "competitor_density": density,
    }


def select_portfolio_links(event, limit=3):
    if not ENABLE_PORTFOLIO_MATCHING:
        return []
    links_map = load_portfolio_links()
    haystack = normalize_match_text(
        f"{event.get('title', '')} {event.get('description', '')} {event.get('type_of_work', '')}"
    )
    scored = []
    for topic, links in links_map.items():
        if topic in haystack:
            for link in links:
                scored.append((len(topic), link))
    scored.sort(key=lambda x: x[0], reverse=True)
    deduped = []
    seen = set()
    for _, link in scored:
        if link in seen:
            continue
        seen.add(link)
        deduped.append(link)
        if len(deduped) >= limit:
            break
    return deduped


def proposal_tone_prefix():
    tones = {
        "friendly": "Hi there, I would love to help with this.",
        "consultative": "Hi, I reviewed your requirements and here is a practical execution plan.",
        "direct": "Hi, I can start immediately and deliver quickly.",
        "confident": "Hi, this is exactly the type of project I handle regularly.",
    }
    return tones.get(PROPOSAL_TONE, tones["confident"])


def build_followup_message(event):
    return (
        f"Quick follow-up on your {event.get('title', 'job post')} project.\n"
        "I can share a concise execution plan and first milestone timeline today.\n"
        "If you want, I can start with a small deliverable immediately."
    )


def build_interview_prep(event):
    title = event.get("title", "the role")
    return {
        "likely_questions": [
            f"Can you show similar work related to {title}?",
            "How fast can you deliver the first milestone?",
            "How do you handle revisions and feedback?",
            "What tools and workflow will you use?",
        ],
        "answer_bullets": [
            "Highlight closest relevant sample with measurable result",
            "Offer concrete timeline with checkpoints",
            "Set revision policy and communication cadence",
            "Show process clarity to reduce client risk",
        ],
    }


def suggest_bid_range(event):
    ctx = budget_context(event)
    monthly = ctx.get("normalized_monthly_usd")
    score = int(event.get("job_score", 50) or 50)
    if monthly is None:
        base_low, base_high = 300, 800
    else:
        base_low = max(100, int(monthly * 0.65))
        base_high = max(base_low + 50, int(monthly * 1.05))
    if score >= 80:
        base_low = int(base_low * 1.1)
        base_high = int(base_high * 1.15)
    return {"min_usd": base_low, "max_usd": base_high, "confidence": "medium" if monthly is not None else "low"}


def detect_skill_gaps(event):
    text = normalize_match_text(f"{event.get('title', '')} {event.get('description', '')}")
    demand = []
    for token in ["video editing", "tiktok", "youtube", "copywriting", "seo", "automation", "python", "comfyui"]:
        if normalize_match_text(token) in text:
            demand.append(token)
    gaps = [s for s in demand if normalize_match_text(s) not in " ".join(PROFILE_SKILLS)]
    return {"required_signals": demand, "profile_skills": PROFILE_SKILLS, "gaps": gaps}


def proposal_variants(event):
    base = proposal_tone_prefix()
    title = event.get("title", "your project")
    return {
        "concise": f"{base} I can handle {title} and deliver a first milestone in 24-48h. Ready to start now.",
        "consultative": f"Hi, for {title}, I recommend a 3-step plan: discovery, quick prototype, then polish with revisions.",
        "premium": f"Hi, I run this as a high-accountability engagement for {title} with clear milestones, reporting, and quality control.",
    }


def build_voice_note_script(event):
    return (
        f"Hi! Quick intro for your {event.get('title', 'project')}. "
        "I can start immediately, send a first result within 24 to 48 hours, "
        "and keep communication fast with clear milestones. "
        "If helpful, I can share the exact execution plan right now."
    )


def build_smart_queue(events):
    ranked = sorted(events, key=lambda e: e.get("job_score", 0), reverse=True)
    tasks = []
    for event in ranked[:20]:
        action = "apply_now" if event.get("priority") == "high" else "review"
        if event_age_minutes(event) and event_age_minutes(event) > 24 * 60:
            action = "archive"
        tasks.append({"event_key": event.get("event_key"), "title": event.get("title"), "action": action, "score": event.get("job_score", 0)})
    return tasks


def build_weekly_coach(events, analytics, outcomes):
    high = len([e for e in events if e.get("priority") == "high"])
    applied = sum(int(v) for v in analytics.get("applied", {}).values())
    wins = sum(int(v) for v in analytics.get("wins", {}).values())
    loss_reasons = {}
    for _, info in outcomes.items():
        if not isinstance(info, dict):
            continue
        if info.get("status") != "lost":
            continue
        reason = (info.get("reason") or "unspecified").strip().lower()
        loss_reasons[reason] = int(loss_reasons.get(reason, 0)) + 1
    top_loss = sorted(loss_reasons.items(), key=lambda x: x[1], reverse=True)[:3]
    tips = [
        f"High-priority opportunities this week: {high}. Focus on applying within first 10 minutes.",
        f"Applications vs wins: {applied}/{wins}. Improve proposal specificity if win rate is low.",
        "Use portfolio links in first message to lift trust quickly.",
    ]
    return {"tips": tips, "top_loss_reasons": top_loss}


def competitor_heatmap(events):
    heat = {}
    for event in events:
        detected = parse_iso_to_utc(event.get("detected_at", ""))
        if not detected:
            continue
        hour = detected.astimezone(DASHBOARD_TZ).strftime("%H:00")
        density = event.get("job_brief", {}).get("competitor_density", {}).get("density", "low")
        key = f"{hour}|{density}"
        heat[key] = int(heat.get(key, 0)) + 1
    rows = [{"bucket": k, "count": v} for k, v in sorted(heat.items(), key=lambda x: x[0])]
    return rows


def duplicate_clusters(events):
    clusters = {}
    for event in events:
        fp = event.get("fingerprint") or event_fingerprint(event)
        clusters.setdefault(fp, []).append({"event_key": event.get("event_key"), "title": event.get("title"), "detected_at": event.get("detected_at")})
    return [v for v in clusters.values() if len(v) >= 2]


def pipeline_board(events, outcomes):
    board = {"new": [], "applied": [], "replied": [], "interview": [], "won": [], "lost": []}
    for event in events:
        key = event.get("event_key", "")
        outcome = outcomes.get(key, {}) if isinstance(outcomes, dict) else {}
        status = str(outcome.get("status", "")).strip().lower()
        card = {
            "event_key": key,
            "title": event.get("title", ""),
            "score": event.get("job_score", 0),
            "url": event.get("url", ""),
        }
        if status == "applied":
            board["applied"].append(card)
        elif status == "win":
            board["won"].append(card)
        elif status == "lost":
            board["lost"].append(card)
        else:
            board["new"].append(card)
    return board


def compute_daily_progress(goals, analytics, followups_sent):
    today = datetime.now(DASHBOARD_TZ).strftime("%Y-%m-%d")
    applied_today = int(analytics.get("applied", {}).get(today, 0))
    followups_today = sum(int(v) for _, v in (followups_sent or {}).items())
    apply_target = int(goals.get("daily_apply_target", 5))
    followup_target = int(goals.get("daily_followup_target", 3))
    return {
        "today": today,
        "applied_today": applied_today,
        "followups_today": followups_today,
        "apply_target": apply_target,
        "followup_target": followup_target,
        "apply_progress_pct": 100 if apply_target <= 0 else round((applied_today / apply_target) * 100, 2),
        "followup_progress_pct": 100 if followup_target <= 0 else round((followups_today / followup_target) * 100, 2),
    }


def best_apply_hours(events, outcomes):
    stats = {}
    for event in events:
        dt = parse_iso_to_utc(event.get("detected_at", ""))
        if not dt:
            continue
        hour = dt.astimezone(DASHBOARD_TZ).hour
        row = stats.setdefault(hour, {"events": 0, "wins": 0})
        row["events"] += 1
        key = event.get("event_key", "")
        if outcomes.get(key, {}).get("status") == "win":
            row["wins"] += 1
    ranked = []
    for hour, row in stats.items():
        rate = (row["wins"] / row["events"]) if row["events"] else 0.0
        ranked.append({"hour": hour, "events": row["events"], "wins": row["wins"], "win_rate": round(rate * 100, 2)})
    ranked.sort(key=lambda x: (x["win_rate"], x["events"]), reverse=True)
    return ranked[:6]


def employer_trust_index(event):
    score = int(event.get("employer_quality_score", 60) or 60)
    if event.get("repost_suspected"):
        score -= 15
    text = (event.get("description", "") or "").lower()
    if "verified" in text or "long term" in text:
        score += 10
    if "unpaid" in text or "commission only" in text:
        score -= 20
    score = max(0, min(100, score))
    risk = "low" if score >= 70 else ("medium" if score >= 45 else "high")
    return {"trust_score": score, "risk_level": risk}


def opportunity_index(event):
    budget = budget_context(event).get("normalized_monthly_usd") or 400
    score = int(event.get("job_score", 50) or 50)
    effort = 100 - min(95, score)
    idx = round((budget * (score / 100.0)) / max(1, effort), 3)
    return {"index": idx, "budget_monthly_usd": budget, "effort_inverse_score": effort}


def evaluate_rules(event, rules):
    hits = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        name = str(rule.get("name", "rule")).strip() or "rule"
        keyword = normalize_match_text(rule.get("keyword", ""))
        min_score = int(rule.get("min_score", 0) or 0)
        action = str(rule.get("action", "flag")).strip() or "flag"
        haystack = normalize_match_text(f"{event.get('title','')} {event.get('description','')}")
        if keyword and keyword not in haystack:
            continue
        if int(event.get("job_score", 0) or 0) < min_score:
            continue
        hits.append({"name": name, "action": action})
    return hits


def build_digest_summary_text(mode="daily"):
    window_hours = 24 if mode == "daily" else 24 * 7
    cutoff = datetime.now(timezone.utc).timestamp() - (window_hours * 3600)
    with state_lock:
        events_snapshot = list(state.get("events", []))
    events = [enrich_event_for_ui(e, include_heavy=False) for e in events_snapshot]
    selected = []
    for event in events:
        detected = parse_iso_to_utc(event.get("detected_at", ""))
        if detected and detected.timestamp() >= cutoff:
            selected.append(event)
    top = sorted(selected, key=lambda e: e.get("job_score", 0), reverse=True)[:5]
    lines = [
        f"{mode.title()} digest ({window_hours}h)",
        f"Total jobs: {len(selected)}",
        f"High priority: {len([e for e in selected if e.get('priority') == 'high'])}",
        "",
        "Top opportunities:",
    ]
    for event in top:
        lines.append(
            f"- [{event.get('job_score', 0)}/100] {truncate_text(event.get('title', ''), 90)} | {event.get('url', '')}"
        )
    return "\n".join(lines)


def request_text(url, site_name):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"{site_name} fetch failed ({attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2)
    return None


def extract_onlinejobs_job_id(href):
    full_url = urljoin(ONLINEJOBS_BASE_URL, href)
    path = urlparse(full_url).path.rstrip("/")

    match = re.search(r"/jobseekers/job/(?:.*-)?(\d+)$", path)
    if match:
        return match.group(1)

    match = re.search(r"(\d+)$", path)
    if match:
        return match.group(1)

    return None


def extract_freelancer_job_id(href):
    full_url = urljoin(FREELANCER_BASE_URL, href)
    path = urlparse(full_url).path.rstrip("/")
    if not path:
        return None
    return path.split("/")[-1]


def parse_onlinejobs_posted_at(posted_text):
    if not posted_text:
        return None
    try:
        parsed = datetime.strptime(posted_text, "%Y-%m-%d %H:%M:%S")
        return parsed.replace(tzinfo=ONLINEJOBSPH_TZ)
    except Exception:
        return None


def parse_onlinejobs_posted_at_any(posted_text):
    posted_text = (posted_text or "").strip()
    if not posted_text:
        return None

    parsed = parse_onlinejobs_posted_at(posted_text)
    if parsed:
        return parsed

    try:
        iso_like = posted_text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(iso_like)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ONLINEJOBSPH_TZ)
        return parsed.astimezone(ONLINEJOBSPH_TZ)
    except Exception:
        return None


def format_onlinejobs_posted_display(event):
    updated_raw = (event.get("date_updated") or "").strip()
    if updated_raw:
        return f"{updated_raw} (OLJ DATE UPDATED)"

    posted_raw = (event.get("posted_at") or "").strip()
    if not posted_raw:
        return "N/A"
    # Show OLJ raw value exactly as scraped to prevent date-shift confusion.
    return f"{posted_raw} (OLJ)"


def is_onlinejobs_within_window(job):
    if POSTED_WITHIN_MINUTES <= 0:
        return True, None, ""

    posted_text = job.get("posted_at", "")
    posted_dt = parse_onlinejobs_posted_at(posted_text)
    if not posted_dt:
        return False, None, ""

    now_dt = datetime.now(ONLINEJOBSPH_TZ)
    age_seconds = (now_dt - posted_dt).total_seconds()

    # Allow small server clock skew tolerance.
    if age_seconds < 0 and abs(age_seconds) <= 120:
        age_seconds = 0

    within = age_seconds <= (POSTED_WITHIN_MINUTES * 60)
    return within, age_seconds, posted_dt.isoformat()


def is_onlinejobs_within_hours(job, hours):
    posted_text = job.get("posted_at", "")
    posted_dt = parse_onlinejobs_posted_at(posted_text)
    if not posted_dt:
        return False, None, ""
    now_dt = datetime.now(ONLINEJOBSPH_TZ)
    age_seconds = (now_dt - posted_dt).total_seconds()
    if age_seconds < 0 and abs(age_seconds) <= 120:
        age_seconds = 0
    within = age_seconds <= (max(1, int(hours)) * 3600)
    return within, age_seconds, posted_dt.isoformat()


# ======================
# FETCH JOBS
# ======================


def canonical_label(text):
    return re.sub(r"[^a-z]", "", (text or "").lower())


def parse_detail_kv_fields(soup):
    details = {
        "type_of_work": "",
        "wage_salary": "",
        "hours_per_week": "",
        "date_updated": "",
    }

    label_map = {
        "typeofwork": "type_of_work",
        "worktype": "type_of_work",
        "wagesalary": "wage_salary",
        "salary": "wage_salary",
        "hoursperweek": "hours_per_week",
        "hoursweek": "hours_per_week",
        "dateupdated": "date_updated",
        "updated": "date_updated",
    }

    lines = []
    for line in soup.get_text("\n", strip=True).splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip()
        if cleaned:
            lines.append(cleaned)

    for idx, line in enumerate(lines[:-1]):
        mapped = label_map.get(canonical_label(line))
        if not mapped or details[mapped]:
            continue
        value = lines[idx + 1].strip()
        if value:
            details[mapped] = value

    return details


def fetch_job_detail_onlinejobsph(url):
    html = request_text(url, "OnlineJobsPH detail")
    if not html:
        return {
            "description": "",
            "skills": "",
            "type_of_work": "",
            "wage_salary": "",
            "hours_per_week": "",
            "date_updated": "",
        }

    soup = BeautifulSoup(html, "lxml")
    desc = (
        soup.find("div", id="jobdescription")
        or soup.find(id="job-description")
        or soup.select_one(".job-description")
    )
    skills = soup.find("div", id="skills") or soup.select_one(".skills")
    metadata = parse_detail_kv_fields(soup)
    metadata["description"] = desc.get_text(" ", strip=True) if desc else ""
    metadata["skills"] = skills.get_text(" ", strip=True) if skills else ""
    return metadata


def parse_onlinejobs_cards(soup):
    jobs = {}

    for card in soup.select("div.jobpost-cat-box.latest-job-post"):
        parent_link = card.find_parent("a", href=True)
        if not parent_link:
            continue

        href = parent_link.get("href", "").strip()
        if "/jobseekers/job/" not in href:
            continue

        job_id = extract_onlinejobs_job_id(href)
        if not job_id or job_id in jobs:
            continue

        title_tag = card.select_one("h4")
        raw_title = title_tag.get_text(" ", strip=True) if title_tag else parent_link.get_text(" ", strip=True)
        title = re.sub(r"\s+", " ", raw_title).strip()

        desc_tag = card.select_one("div.desc")
        description = desc_tag.get_text(" ", strip=True) if desc_tag else ""

        posted_tag = card.select_one("p[data-temp]")
        posted_at = posted_tag.get("data-temp", "").strip() if posted_tag else ""

        jobs[job_id] = {
            "title": f"[OnlineJobsPH] {title}",
            "url": f"{ONLINEJOBS_BASE_URL}/jobseekers/job/{job_id}",
            "description": description,
            "posted_at": posted_at,
            "type_of_work": "",
            "wage_salary": "",
            "hours_per_week": "",
            "date_updated": "",
        }

    return jobs


def fetch_jobs(site):
    jobs = {}
    html = request_text(site["url"], site["name"])
    if not html:
        return jobs

    soup = BeautifulSoup(html, "lxml")
    require_keyword_match = site.get("require_keyword_match", True)
    filter_words = get_active_trigger_words() or KEYWORDS

    if site["type"] == "onlinejobsph":
        parsed_jobs = parse_onlinejobs_cards(soup)
        detail_keyword_fetch_count = 0
        detail_keyword_fetch_limit = 3

        if not parsed_jobs:
            for a in soup.select("a[href*='/jobseekers/job/']"):
                href = a.get("href", "").strip()
                job_id = extract_onlinejobs_job_id(href)
                if not job_id or job_id in parsed_jobs:
                    continue

                title = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
                parsed_jobs[job_id] = {
                    "title": f"[OnlineJobsPH] {title}",
                    "url": f"{ONLINEJOBS_BASE_URL}/jobseekers/job/{job_id}",
                    "description": "",
                    "posted_at": "",
                    "type_of_work": "",
                    "wage_salary": "",
                    "hours_per_week": "",
                    "date_updated": "",
                }

        for job_id, job in parsed_jobs.items():
            if not require_keyword_match:
                jobs[job_id] = job
                continue

            combined_text = f"{job['title']} {job.get('description', '')}"
            if (
                not keyword_match(combined_text, words=filter_words, match_if_empty=True)
                and ONLINEJOBSPH_FETCH_DETAILS_FOR_KEYWORD_MATCH
                and detail_keyword_fetch_count < detail_keyword_fetch_limit
            ):
                detail = fetch_job_detail_onlinejobsph(job["url"])
                combined_text = f"{combined_text} {detail.get('description', '')} {detail.get('skills', '')}"
                detail_keyword_fetch_count += 1

            if keyword_match(combined_text, words=filter_words, match_if_empty=True):
                jobs[job_id] = job

    elif site["type"] == "freelancer":
        for job_card in soup.select("div.JobSearchCard-item"):
            a = job_card.select_one("a[data-item='job-title-link']")
            if not a:
                continue

            href = a.get("href", "").strip()
            job_id = extract_freelancer_job_id(href)
            if not job_id:
                continue

            title = a.get_text(strip=True)
            url_full = urljoin(FREELANCER_BASE_URL, href)

            desc_tag = job_card.select_one("p.JobSearchCard-description")
            description = desc_tag.get_text(" ", strip=True) if desc_tag else ""

            combined_text = f"{title} {description}"
            if not require_keyword_match or keyword_match(combined_text, words=filter_words, match_if_empty=True):
                jobs[job_id] = {
                    "title": f"[Freelancer] {title}",
                    "url": url_full,
                    "description": description,
                    "posted_at": "",
                }

    return jobs


def seed_seen_from_current_listings(seen):
    added = 0
    for site in JOB_SITES:
        print(f"Seeding seen jobs from {site['name']}...", end=" ")
        jobs = fetch_jobs(site)
        print(f"found {len(jobs)} jobs")

        for job_id in jobs:
            key = build_seen_key_for_job(site["type"], job_id, jobs.get(job_id, {}))
            if key in seen:
                continue
            seen.add(key)
            added += 1

    return added


def startup_backfill_recent_jobs(hours=24):
    added_events = 0
    seen_changed = False
    events_changed = False
    detail_fetch_count = 0
    hours = max(1, int(hours))

    for site in JOB_SITES:
        try:
            jobs = fetch_jobs(site)
        except Exception as exc:
            add_runtime_log(f"Startup backfill fetch error ({site['name']}): {type(exc).__name__}: {exc}", "error")
            continue

        for job_id, job in jobs.items():
            if site["type"] != "onlinejobsph":
                continue

            within, age_seconds, posted_at_iso = is_onlinejobs_within_hours(job, hours)
            if not within:
                continue

            seen_key = build_seen_key_for_job(site["type"], job_id, job)
            with state_lock:
                if seen_key not in state["seen"]:
                    state["seen"].add(seen_key)
                    seen_changed = True

            if detail_fetch_count < MAX_DETAIL_FETCH_PER_CYCLE:
                detail = fetch_job_detail_onlinejobsph(job["url"])
                if detail.get("description"):
                    job["description"] = detail["description"]
                job["type_of_work"] = detail.get("type_of_work", "")
                job["wage_salary"] = detail.get("wage_salary", "")
                job["hours_per_week"] = detail.get("hours_per_week", "")
                job["date_updated"] = detail.get("date_updated", "")
                detail_fetch_count += 1

            event = build_event(site, job_id, job, age_seconds=age_seconds, posted_at_iso=posted_at_iso, seen_key=seen_key)
            fp = event_fingerprint(event)
            event["fingerprint"] = fp

            with state_lock:
                if event["event_key"] in state["event_keys"]:
                    continue
                state["event_keys"].add(event["event_key"])
                state["events"].insert(0, event)
                if len(state["events"]) > MAX_STORED_EVENTS:
                    state["events"] = state["events"][:MAX_STORED_EVENTS]
                    state["event_keys"] = {e["event_key"] for e in state["events"]}
                recent_fps = state.setdefault("recent_fingerprints", {})
                recent_fps[fp] = event.get("detected_at", now_utc_iso())
                added_events += 1
                events_changed = True

    if seen_changed:
        with state_lock:
            seen_snapshot = set(state["seen"])
        save_seen_jobs(seen_snapshot)
    if events_changed:
        with state_lock:
            events_snapshot = list(state["events"])
        save_job_events(events_snapshot)

    return added_events


# ======================
# WATCHER LOOP
# ======================


def build_event(site, job_id, job, age_seconds=None, posted_at_iso="", seen_key=""):
    detected_at = now_utc_iso()
    event_key = str(seen_key or build_seen_key_for_job(site["type"], job_id, job))
    event = {
        "event_key": event_key,
        "site": site["name"],
        "site_type": site["type"],
        "job_id": str(job_id),
        "title": job.get("title", "").strip(),
        "url": job.get("url", "").strip(),
        "description": job.get("description", "").strip(),
        "posted_at": job.get("posted_at", "").strip(),
        "posted_at_iso": posted_at_iso,
        "detected_at": detected_at,
        "detected_at_local": format_local_time(detected_at, DASHBOARD_TZ),
        "last_seen_at": detected_at,
        "last_seen_at_local": format_local_time(detected_at, DASHBOARD_TZ),
        "age_seconds_at_detection": round(age_seconds, 2) if age_seconds is not None else None,
        "type_of_work": job.get("type_of_work", "").strip(),
        "wage_salary": job.get("wage_salary", "").strip(),
        "hours_per_week": job.get("hours_per_week", "").strip(),
        "date_updated": job.get("date_updated", "").strip(),
        "keyword_matched": False,
        "notification_sent": False,
        "repost_suspected": False,
    }
    event["keyword_matched"] = event_matches_niche_keywords(event)
    intelligence = score_event(event)
    event["job_score"] = intelligence["score"]
    event["priority"] = intelligence["priority"]
    event["intent"] = intelligence["intent"]
    event["employer_quality_score"] = intelligence["employer_quality_score"]
    event["reply_opportunity"] = intelligence.get("reply_opportunity", "low")
    event["reply_signals"] = intelligence.get("reply_signals", [])
    return event


def notify_new_event(event, site):
    # Force-refresh OLJ details before sending so description comes from the
    # actual job page, not listing snippets or automation-generated text.
    site_name = str(site.get("name", "")).strip().lower()
    url = (event.get("url") or "").strip()
    if "onlinejobsph" in site_name and "onlinejobs.ph/jobseekers/job/" in url:
        detail = fetch_job_detail_onlinejobsph(url)
        if detail.get("description"):
            event["description"] = detail.get("description", "").strip()
        if detail.get("type_of_work"):
            event["type_of_work"] = detail.get("type_of_work", "").strip()
        if detail.get("wage_salary"):
            event["wage_salary"] = detail.get("wage_salary", "").strip()
        if detail.get("hours_per_week"):
            event["hours_per_week"] = detail.get("hours_per_week", "").strip()
        if detail.get("date_updated"):
            event["date_updated"] = detail.get("date_updated", "").strip()

    snippet = (event.get("description") or "").strip()
    if not snippet:
        snippet = "N/A"

    raw_title = (event.get("title") or "").strip() or "N/A"
    title_no_prefix = re.sub(r"^\[(onlinejobsph|freelancer)\]\s*", "", raw_title, flags=re.IGNORECASE).strip()
    posted_time = format_onlinejobs_posted_display(event)
    type_of_work = (event.get("type_of_work") or "").strip() or "N/A"
    wage_salary = (event.get("wage_salary") or "").strip() or "N/A"
    hours_per_week = (event.get("hours_per_week") or "").strip() or "N/A"
    date_updated = (event.get("date_updated") or "").strip() or "N/A"
    detected_at_local = (event.get("detected_at_local") or "").strip() or "N/A"
    url = (event.get("url") or "").strip() or "N/A"

    lines = [
        f"Title: [{site['name']}] {title_no_prefix}",
        "",
        f"Employer Quality: {event.get('employer_quality_score', 'N/A')}/100",
        f"Wage/Salary: {wage_salary}",
        f"Hours/Week: {hours_per_week}",
        "",
        f"Description: {snippet}",
        "",
        f"Date posted: {posted_time}",
        f"Date detected: {detected_at_local} ({DASHBOARD_TIMEZONE})",
        f"Link: {url}",
    ]
    text = "\n".join(lines)
    title = ""
    sent_any = False

    if send_telegram_niche_routed(text, title=title, event=event):
        sent_any = True

    if ENABLE_MULTI_CHANNEL_ALERTS:
        if send_webhook(SLACK_WEBHOOK_URL, text, title=title):
            sent_any = True
        if send_webhook(DISCORD_WEBHOOK_URL, text, title=title):
            sent_any = True
        if send_email_alert(text, title=title):
            sent_any = True

    return sent_any


def run_check_cycle():
    cycle_started = now_utc_iso()
    add_runtime_log("Cycle stage: start run_check_cycle", "info")
    cycle_summary = {
        "checked_at": cycle_started,
        "sites": [],
        "new_events": 0,
        "skipped_outside_window": 0,
        "niche_matched_events": 0,
        "notifications_sent": 0,
        "notifications_skipped": 0,
        "detail_fetches": 0,
        "duplicates_suppressed": 0,
    }

    pending_notifications = []
    seen_changed = False
    events_changed = False
    detail_fetch_count = 0

    for site in JOB_SITES:
        site_started_ts = time.time()
        add_runtime_log(f"Cycle stage: fetching jobs for {site['name']}", "info")
        site_summary = {
            "site": site["name"],
            "fetched": 0,
            "new_events": 0,
            "skipped_outside_window": 0,
            "niche_matched_events": 0,
            "notifications_sent": 0,
            "notifications_skipped": 0,
            "errors": 0,
            "aborted_budget": False,
        }

        try:
            jobs = fetch_jobs(site)
        except Exception as exc:
            site_summary["errors"] += 1
            add_runtime_log(f"Site fetch error ({site['name']}): {type(exc).__name__}: {exc}", "error")
            cycle_summary["sites"].append(site_summary)
            continue
        site_summary["fetched"] = len(jobs)
        if len(jobs) == 0:
            add_runtime_log(f"No jobs returned for {site['name']} (after listing filter).", "warn")
        add_runtime_log(f"Cycle stage: fetched {len(jobs)} jobs for {site['name']}", "info")

        for job_id, job in jobs.items():
            if time.time() - site_started_ts > SITE_FETCH_BUDGET_SECONDS:
                site_summary["aborted_budget"] = True
                add_runtime_log(
                    f"Site scan budget reached for {site['name']} ({SITE_FETCH_BUDGET_SECONDS}s). Remaining jobs deferred.",
                    "warn",
                )
                break
            seen_key = build_seen_key_for_job(site["type"], job_id, job)

            already_seen = False
            with state_lock:
                if seen_key in state["seen"]:
                    already_seen = True
                else:
                    state["seen"].add(seen_key)
                    seen_changed = True

            should_store = True
            age_seconds = None
            posted_at_iso = ""

            if site["type"] == "onlinejobsph":
                should_store, age_seconds, posted_at_iso = is_onlinejobs_within_window(job)
                if not should_store:
                    site_summary["skipped_outside_window"] += 1
                    cycle_summary["skipped_outside_window"] += 1
                    continue

                if detail_fetch_count < MAX_DETAIL_FETCH_PER_CYCLE:
                    detail = fetch_job_detail_onlinejobsph(job["url"])
                    if detail.get("description"):
                        job["description"] = detail["description"]
                    job["type_of_work"] = detail.get("type_of_work", "")
                    job["wage_salary"] = detail.get("wage_salary", "")
                    job["hours_per_week"] = detail.get("hours_per_week", "")
                    job["date_updated"] = detail.get("date_updated", "")
                    detail_fetch_count += 1
                    cycle_summary["detail_fetches"] = detail_fetch_count

            event = build_event(site, job_id, job, age_seconds=age_seconds, posted_at_iso=posted_at_iso, seen_key=seen_key)
            fp = event_fingerprint(event)
            event["fingerprint"] = fp

            suppress_duplicate = False
            if ENABLE_DUPLICATE_SUPPRESSION:
                with state_lock:
                    recent_fps = dict(state.get("recent_fingerprints", {}))
                prev_iso = recent_fps.get(fp, "")
                prev_dt = parse_iso_to_utc(prev_iso)
                if prev_dt:
                    age_h = (datetime.now(timezone.utc) - prev_dt).total_seconds() / 3600.0
                    if age_h <= DUPLICATE_WINDOW_HOURS:
                        suppress_duplicate = True
                        event["repost_suspected"] = True

            if suppress_duplicate:
                site_summary["notifications_skipped"] += 1
                cycle_summary["duplicates_suppressed"] += 1
                continue
            if event["keyword_matched"]:
                site_summary["niche_matched_events"] += 1
                cycle_summary["niche_matched_events"] += 1

            with state_lock:
                now_seen_iso = now_utc_iso()
                now_seen_local = format_local_time(now_seen_iso, DASHBOARD_TZ)
                if event["event_key"] in state["event_keys"]:
                    if STORE_ALL_FETCHED_JOBS:
                        for idx, existing in enumerate(state["events"]):
                            if existing.get("event_key") != event["event_key"]:
                                continue
                            existing["title"] = event.get("title", existing.get("title", ""))
                            existing["url"] = event.get("url", existing.get("url", ""))
                            existing["description"] = event.get("description", existing.get("description", ""))
                            existing["posted_at"] = event.get("posted_at", existing.get("posted_at", ""))
                            existing["posted_at_iso"] = event.get("posted_at_iso", existing.get("posted_at_iso", ""))
                            existing["type_of_work"] = event.get("type_of_work", existing.get("type_of_work", ""))
                            existing["wage_salary"] = event.get("wage_salary", existing.get("wage_salary", ""))
                            existing["hours_per_week"] = event.get("hours_per_week", existing.get("hours_per_week", ""))
                            existing["date_updated"] = event.get("date_updated", existing.get("date_updated", ""))
                            existing["keyword_matched"] = event.get("keyword_matched", existing.get("keyword_matched", False))
                            existing["job_score"] = event.get("job_score", existing.get("job_score", 0))
                            existing["priority"] = event.get("priority", existing.get("priority", ""))
                            existing["intent"] = event.get("intent", existing.get("intent", {}))
                            existing["employer_quality_score"] = event.get("employer_quality_score", existing.get("employer_quality_score", 0))
                            existing["reply_opportunity"] = event.get("reply_opportunity", existing.get("reply_opportunity", "low"))
                            existing["reply_signals"] = event.get("reply_signals", existing.get("reply_signals", []))
                            existing["fingerprint"] = fp
                            existing["last_seen_at"] = now_seen_iso
                            existing["last_seen_at_local"] = now_seen_local
                            # Move recently seen job toward top so the table reflects current listings.
                            state["events"].pop(idx)
                            state["events"].insert(0, existing)
                            break
                        events_changed = True
                    continue

                state["event_keys"].add(event["event_key"])
                event["last_seen_at"] = now_seen_iso
                event["last_seen_at_local"] = now_seen_local
                state["events"].insert(0, event)
                if len(state["events"]) > MAX_STORED_EVENTS:
                    state["events"] = state["events"][:MAX_STORED_EVENTS]
                    state["event_keys"] = {e["event_key"] for e in state["events"]}

                events_changed = True
                metrics = state.setdefault("metrics", {})
                metrics["events_created"] = int(metrics.get("events_created", 0)) + 1
                recent_fps = state.setdefault("recent_fingerprints", {})
                recent_fps[fp] = event.get("detected_at", now_utc_iso())

            pending_notifications.append((event, site))
            site_summary["new_events"] += 1
            cycle_summary["new_events"] += 1

        cycle_summary["sites"].append(site_summary)

    if seen_changed:
        add_runtime_log("Cycle stage: saving seen jobs", "info")
        with state_lock:
            seen_snapshot = set(state["seen"])
        save_seen_jobs(seen_snapshot)

    add_runtime_log(f"Cycle stage: notifying {len(pending_notifications)} event(s)", "info")
    for event, site in pending_notifications:
        with state_lock:
            metrics = state.setdefault("metrics", {})
            metrics["notifications_attempted"] = int(metrics.get("notifications_attempted", 0)) + 1
        notification_sent = notify_new_event(event, site)
        with state_lock:
            for stored_event in state["events"]:
                if stored_event["event_key"] == event["event_key"]:
                    stored_event["notification_sent"] = bool(notification_sent)
                    break
            if notification_sent:
                metrics = state.setdefault("metrics", {})
                metrics["notifications_sent"] = int(metrics.get("notifications_sent", 0)) + 1

        for site_summary in cycle_summary["sites"]:
            if site_summary["site"] != site["name"]:
                continue
            if notification_sent:
                site_summary["notifications_sent"] += 1
                cycle_summary["notifications_sent"] += 1
            else:
                site_summary["notifications_skipped"] += 1
                cycle_summary["notifications_skipped"] += 1
            break

        if notification_sent:
            print(f"New job saved and notified: {event['title']}")
        else:
            print(f"New job saved but notification skipped: {event['title']}")

    # Backfill unsent historical events so jobs visible in the app are eventually
    # delivered to Telegram even if they were missed in prior runs/configs.
    backfill_candidates = []
    if UNSENT_BACKFILL_PER_CYCLE > 0:
        with state_lock:
            for stored_event in state.get("events", []):
                if stored_event.get("notification_sent"):
                    continue
                if not stored_event.get("url"):
                    continue
                backfill_candidates.append(dict(stored_event))
                if len(backfill_candidates) >= UNSENT_BACKFILL_PER_CYCLE:
                    break

    if backfill_candidates:
        add_runtime_log(
            f"Cycle stage: backfill notify {len(backfill_candidates)} unsent event(s)",
            "info",
        )
        for event in backfill_candidates:
            if event.get("site_type") == "onlinejobsph":
                within, _, _ = is_onlinejobs_within_window(event)
                if not within:
                    continue
            site_name = event.get("site", "OnlineJobsPH") or "OnlineJobsPH"
            notification_sent = notify_new_event(event, {"name": site_name, "type": event.get("site_type", "")})
            with state_lock:
                for stored_event in state["events"]:
                    if stored_event.get("event_key") == event.get("event_key"):
                        if notification_sent:
                            stored_event["notification_sent"] = True
                        break
            if notification_sent:
                cycle_summary["notifications_sent"] += 1
            else:
                cycle_summary["notifications_skipped"] += 1

    if events_changed:
        add_runtime_log("Cycle stage: saving event history", "info")
        with state_lock:
            events_snapshot = list(state["events"])
        save_job_events(events_snapshot)

    now_ts = time.time()
    should_heartbeat = False

    with state_lock:
        if now_ts - state["last_heartbeat_ts"] >= HEARTBEAT_INTERVAL:
            state["last_heartbeat_ts"] = now_ts
            should_heartbeat = True

    if should_heartbeat and ENABLE_STATUS_NOTIFICATIONS:
        send_telegram(
            f"Watcher running. New-window filter: {POSTED_WITHIN_MINUTES} minute(s).",
            title="Heartbeat - OnlineJobs Watcher",
        )

    if ENABLE_DIGEST_NOTIFICATIONS:
        now_local = datetime.now(DASHBOARD_TZ)
        digest_date = now_local.strftime("%Y-%m-%d")
        with state_lock:
            already_sent_for_day = state.get("last_digest_date", "") == digest_date
        if now_local.hour >= DIGEST_SEND_HOUR_LOCAL and not already_sent_for_day:
            digest_text = build_digest_summary_text(mode="daily")
            sent = notify_new_event(
                {
                    "title": "Daily Opportunity Digest",
                    "description": digest_text,
                    "job_score": 100,
                    "priority": "high",
                    "employer_quality_score": 100,
                    "posted_at": "",
                    "type_of_work": "",
                    "wage_salary": "",
                    "hours_per_week": "",
                    "date_updated": "",
                    "detected_at_local": now_local.strftime("%Y-%m-%d %H:%M:%S"),
                    "url": ui_url(),
                    "keyword_matched": True,
                },
                {"name": "Digest"},
            )
            if sent:
                with state_lock:
                    state["last_digest_date"] = digest_date

    with state_lock:
        followup_enabled_runtime = bool(state.get("auto_followup_enabled", AUTO_FOLLOWUP_ENABLED))
    if followup_enabled_runtime:
        add_runtime_log("Cycle stage: follow-up automation pass", "info")
        now_utc = datetime.now(timezone.utc)
        followups_sent_this_cycle = 0
        with state_lock:
            events_snapshot = list(state.get("events", []))
            followups_sent = dict(state.get("followups_sent", {}))
            outcomes = dict(state.get("outcomes", {}))
        for event in events_snapshot:
            if FOLLOWUP_MAX_PER_CYCLE and followups_sent_this_cycle >= FOLLOWUP_MAX_PER_CYCLE:
                break
            key = event.get("event_key", "")
            if not key:
                continue
            if outcomes.get(key, {}).get("status") in {"win", "lost"}:
                continue
            detected = parse_iso_to_utc(event.get("detected_at", ""))
            if not detected:
                continue
            age_hours = (now_utc - detected).total_seconds() / 3600.0
            if age_hours < FOLLOWUP_AFTER_HOURS:
                continue
            sent_count = int(followups_sent.get(key, 0))
            if sent_count >= FOLLOWUP_MAX_PER_EVENT:
                continue
            msg = build_followup_message(event)
            sent = notify_new_event(
                {
                    "title": event.get("title", ""),
                    "description": msg,
                    "job_score": event.get("job_score", 0),
                    "priority": event.get("priority", "medium"),
                    "employer_quality_score": event.get("employer_quality_score", 0),
                    "posted_at": event.get("posted_at", ""),
                    "type_of_work": event.get("type_of_work", ""),
                    "wage_salary": event.get("wage_salary", ""),
                    "hours_per_week": event.get("hours_per_week", ""),
                    "date_updated": event.get("date_updated", ""),
                    "detected_at_local": event.get("detected_at_local", ""),
                    "url": event.get("url", ""),
                    "keyword_matched": True,
                },
                {"name": event.get("site", "OnlineJobsPH") or "OnlineJobsPH"},
            )
            if sent:
                followups_sent[key] = sent_count + 1
                followups_sent_this_cycle += 1
        with state_lock:
            state["followups_sent"] = followups_sent
        if followups_sent_this_cycle:
            add_runtime_log(f"Follow-up automation sent {followups_sent_this_cycle} reminder(s) this cycle.", "info")

    with state_lock:
        state["last_check_at"] = cycle_started
        state["last_cycle_summary"] = cycle_summary
    add_runtime_log("Cycle stage: run_check_cycle completed", "success")

    return cycle_summary


def execute_scan_cycle(trigger_label="auto"):
    if not scan_cycle_lock.acquire(blocking=False):
        return False, None, "Scan already in progress."

    started_at = now_utc_iso()
    with state_lock:
        state["scan_in_progress"] = True
        state["last_scan_started_at"] = started_at
        state["last_scan_result"] = "scanning"

    add_runtime_log(f"Scan started ({trigger_label}).", "info")
    cycle_start_ts = time.time()
    with state_lock:
        metrics = state.setdefault("metrics", {})
        metrics["scan_cycles_total"] = int(metrics.get("scan_cycles_total", 0)) + 1

    try:
        summary = run_check_cycle()
        with state_lock:
            state["last_error"] = ""
            state["last_scan_result"] = "ok"
        add_runtime_log(
            f"Cycle complete: new_events={summary['new_events']} "
            f"skipped_outside_window={summary['skipped_outside_window']} "
            f"duration={round(time.time() - cycle_start_ts, 2)}s",
            "success",
        )
        return True, summary, ""
    except Exception as e:
        error_text = f"{type(e).__name__}: {e}"
        with state_lock:
            state["last_error"] = error_text
            state["last_scan_result"] = "error"
            metrics = state.setdefault("metrics", {})
            metrics["scan_cycles_failed"] = int(metrics.get("scan_cycles_failed", 0)) + 1
        add_runtime_log(f"Watcher cycle error: {error_text}", "error")
        return False, None, error_text
    finally:
        finished_at = now_utc_iso()
        with state_lock:
            state["scan_in_progress"] = False
            state["last_scan_finished_at"] = finished_at
        scan_cycle_lock.release()


def set_auto_scan_paused(paused):
    paused = bool(paused)
    interval_seconds = get_runtime_scan_interval_seconds()
    with state_lock:
        state["auto_scan_paused"] = paused
        if paused:
            state["next_check_due_ts"] = 0.0
        elif state.get("watcher_running"):
            state["next_check_due_ts"] = time.time() + interval_seconds
    scan_wakeup_event.set()
    return paused


def request_manual_scan():
    with state_lock:
        state["manual_scan_requested"] = True
        if state.get("watcher_running"):
            state["next_check_due_ts"] = time.time()
    scan_wakeup_event.set()


def set_auto_followup_enabled(enabled):
    enabled = bool(enabled)
    with state_lock:
        state["auto_followup_enabled"] = enabled
    add_runtime_log(f"Automation (auto follow-up) {'enabled' if enabled else 'disabled'}.", "info")
    return enabled


def watcher_loop(stop_event):
    with state_lock:
        state["watcher_running"] = True
        state["auto_scan_paused"] = False
        state["manual_scan_requested"] = False
        state["next_check_due_ts"] = time.time()

    add_runtime_log("Watcher loop started.", "info")

    while not stop_event.is_set():
        with state_lock:
            scan_started_iso = str(state.get("last_scan_started_at", "")).strip()
            scan_in_progress = bool(state.get("scan_in_progress", False))
        if scan_in_progress:
            started_dt = parse_iso_to_utc(scan_started_iso)
            if started_dt:
                elapsed = (datetime.now(timezone.utc) - started_dt).total_seconds()
                if elapsed > max(120, SITE_FETCH_BUDGET_SECONDS * 3):
                    with state_lock:
                        state["scan_in_progress"] = False
                        state["last_error"] = f"Watchdog recovered long-running scan after {int(elapsed)}s."
                        metrics = state.setdefault("metrics", {})
                        metrics["scan_cycles_failed"] = int(metrics.get("scan_cycles_failed", 0)) + 1
                    add_runtime_log(f"Watchdog reset stuck scan after {int(elapsed)}s.", "warn")

        with state_lock:
            paused = bool(state.get("auto_scan_paused", False))
            manual_requested = bool(state.get("manual_scan_requested", False))
            next_due_ts = float(state.get("next_check_due_ts", 0.0) or 0.0)

        now_ts = time.time()
        should_scan = manual_requested or (not paused and (next_due_ts <= 0.0 or now_ts >= next_due_ts))

        if should_scan:
            with state_lock:
                state["manual_scan_requested"] = False

            trigger = "manual" if manual_requested else "auto"
            execute_scan_cycle(trigger_label=trigger)

            interval_seconds = get_runtime_scan_interval_seconds()
            with state_lock:
                if state.get("watcher_running") and not state.get("auto_scan_paused"):
                    state["next_check_due_ts"] = time.time() + interval_seconds
                else:
                    state["next_check_due_ts"] = 0.0
            continue

        wait_seconds = 1.0
        if not paused and next_due_ts > 0:
            wait_seconds = max(0.2, min(1.0, next_due_ts - now_ts))

        if scan_wakeup_event.wait(timeout=wait_seconds):
            scan_wakeup_event.clear()

    with state_lock:
        state["watcher_running"] = False
        state["next_check_due_ts"] = 0.0
        state["manual_scan_requested"] = False
        state["auto_scan_paused"] = False
        if state.get("last_scan_result") == "scanning":
            state["last_scan_result"] = "idle"

    add_runtime_log("Watcher loop stopped.", "warn")


def start_watcher():
    global watcher_thread
    with watcher_thread_lock:
        if watcher_thread and watcher_thread.is_alive():
            return True, "Watcher is already running."

        watcher_stop_event.clear()
        scan_wakeup_event.clear()
        with state_lock:
            state["auto_scan_paused"] = False
            state["manual_scan_requested"] = False
            state["next_check_due_ts"] = time.time()
        watcher_thread = threading.Thread(target=watcher_loop, args=(watcher_stop_event,), daemon=True)
        watcher_thread.start()

    return True, "Watcher started."


def stop_watcher(join_timeout=0.25):
    global watcher_thread
    with watcher_thread_lock:
        thread = watcher_thread
        if not thread or not thread.is_alive():
            with state_lock:
                state["watcher_running"] = False
                state["next_check_due_ts"] = 0.0
                state["manual_scan_requested"] = False
                state["auto_scan_paused"] = False
            return True, "Watcher is already stopped."
        watcher_stop_event.set()
        scan_wakeup_event.set()

    thread.join(timeout=join_timeout)
    if not thread.is_alive():
        with watcher_thread_lock:
            watcher_thread = None
        return True, "Watcher stopped."
    return True, "Stop requested. Watcher will stop after the current cycle."


def reload_runtime_data():
    loaded_seen = load_seen_jobs()
    loaded_events, loaded_keys = load_job_events()
    loaded_events, loaded_keys = prune_events_outside_window(loaded_events)
    telegram_settings = load_telegram_settings()
    feedback = load_feedback()
    analytics = load_analytics()
    outcomes = load_outcomes()
    goals = load_goals()
    templates = load_templates()
    interviews = load_interviews()
    rules = load_rules()
    team_data = load_team_data()
    recent_fps = {}
    for event in loaded_events:
        fp = event.get("fingerprint") or event_fingerprint(event)
        recent_fps[fp] = event.get("detected_at", "")

    with state_lock:
        state["seen"] = loaded_seen
        state["events"] = loaded_events
        state["event_keys"] = loaded_keys
        state["telegram"] = telegram_settings
        state["feedback"] = feedback
        state["analytics"] = analytics
        state["recent_fingerprints"] = recent_fps
        state["outcomes"] = outcomes
        state["followups_sent"] = {}
        state["auto_followup_enabled"] = AUTO_FOLLOWUP_ENABLED
        state["goals"] = goals
        state["templates"] = templates
        state["interviews"] = interviews
        state["rules"] = rules
        state["team"] = team_data

    add_runtime_log(
        f"Runtime reloaded from disk: seen={len(loaded_seen)} events={len(loaded_events)}",
        "info",
    )
    return len(loaded_seen), len(loaded_events)


def initialize_state():
    loaded_seen = load_seen_jobs()
    loaded_events, loaded_keys = load_job_events()
    loaded_events, loaded_keys = prune_events_outside_window(loaded_events)
    telegram_settings = load_telegram_settings()
    feedback = load_feedback()
    analytics = load_analytics()
    outcomes = load_outcomes()
    goals = load_goals()
    templates = load_templates()
    interviews = load_interviews()
    rules = load_rules()
    team_data = load_team_data()
    recent_fps = {}
    for event in loaded_events:
        fp = event.get("fingerprint") or event_fingerprint(event)
        recent_fps[fp] = event.get("detected_at", "")

    if SEED_SEEN_ON_STARTUP and (not SEED_ONLY_IF_EMPTY or not loaded_seen):
        added = seed_seen_from_current_listings(loaded_seen)
        save_seen_jobs(loaded_seen)
        print(f"Startup seeding complete. Added {added} jobs to seen store.")
    elif SEED_SEEN_ON_STARTUP:
        print("Startup seeding skipped because seen store is not empty (SEED_ONLY_IF_EMPTY=true).")

    with state_lock:
        state["seen"] = loaded_seen
        state["events"] = loaded_events
        state["event_keys"] = loaded_keys
        state["telegram"] = telegram_settings
        state["feedback"] = feedback
        state["analytics"] = analytics
        state["started_at"] = now_utc_iso()
        state["last_check_at"] = ""
        state["last_cycle_summary"] = {}
        state["last_error"] = ""
        state["last_heartbeat_ts"] = 0.0
        state["watcher_running"] = False
        state["next_check_due_ts"] = 0.0
        state["check_interval_seconds"] = CHECK_INTERVAL_SECONDS
        state["auto_scan_paused"] = False
        state["manual_scan_requested"] = False
        state["scan_in_progress"] = False
        state["last_scan_started_at"] = ""
        state["last_scan_finished_at"] = ""
        state["last_scan_result"] = "idle"
        state["logs"] = []
        state["recent_fingerprints"] = recent_fps
        state["last_digest_date"] = ""
        state["followups_sent"] = {}
        state["outcomes"] = outcomes
        state["goals"] = goals
        state["templates"] = templates
        state["interviews"] = interviews
        state["rules"] = rules
        state["team"] = team_data
        state["auto_followup_enabled"] = AUTO_FOLLOWUP_ENABLED
        state["metrics"] = {
            "scan_cycles_total": 0,
            "scan_cycles_failed": 0,
            "notifications_attempted": 0,
            "notifications_sent": 0,
            "events_created": 0,
        }

    startup_message = "Watcher started successfully"
    if DRY_RUN:
        startup_message = f"{startup_message} (DRY_RUN)"

    if ENABLE_STATUS_NOTIFICATIONS:
        send_telegram(startup_message, "Watcher Status")

    add_runtime_log(
        "Watcher initialized. "
        f"seen={len(loaded_seen)} events={len(loaded_events)} "
        f"posted_within_minutes={POSTED_WITHIN_MINUTES} "
        f"telegram_enabled={telegram_settings['enabled']} "
        f"telegram_configured={bool(telegram_settings['bot_token'] and telegram_settings['chat_id'])}",
        "info",
    )


# ======================
# API + UI
# ======================


def dashboard_html():
    refresh_ms = UI_REFRESH_SECONDS * 1000
    template_path = os.path.join(os.path.dirname(__file__), "dashboard_template.html")
    try:
        with open(template_path, "r", encoding="utf-8") as fp:
            template = fp.read()
    except Exception as exc:
        return f"<h1>Dashboard template missing</h1><pre>{exc}</pre>"

    return template.replace("__REFRESH_MS__", str(refresh_ms))


@app.get("/")
def index():
    response = Response(dashboard_html(), mimetype="text/html")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/api/jobs")
def api_jobs():
    limit = request.args.get("limit", default=200, type=int) or 200
    limit = max(1, min(limit, MAX_STORED_EVENTS))

    with state_lock:
        jobs = [event for event in state["events"] if event_within_current_window(event)]

    jobs.sort(
        key=lambda e: (
            int((event_posted_datetime_utc(e).timestamp()) if event_posted_datetime_utc(e) else 0),
            str(e.get("detected_at", "")),
        ),
        reverse=True,
    )
    jobs = jobs[:limit]

    payload_jobs = [enrich_event_for_ui(event, include_heavy=False) for event in jobs]

    return jsonify({"jobs": payload_jobs, "count": len(payload_jobs)})


@app.get("/api/status")
def api_status():
    now_ts = time.time()
    with state_lock:
        telegram = normalize_telegram_settings(state.get("telegram", {}))
        events_snapshot = list(state["events"])
        goals = dict(state.get("goals", {}))
        analytics = dict(state.get("analytics", {"applied": {}, "wins": {}}))
        followups_sent = dict(state.get("followups_sent", {}))
        next_due_ts = float(state.get("next_check_due_ts", 0.0) or 0.0)
        auto_scan_paused = bool(state.get("auto_scan_paused", False))
        scan_in_progress = bool(state.get("scan_in_progress", False))
        watcher_running = bool(state.get("watcher_running", False))
        next_scan_in = int(max(0, next_due_ts - now_ts)) if watcher_running and not auto_scan_paused and next_due_ts else None
        interval_seconds = normalize_scan_interval_seconds(state.get("check_interval_seconds", CHECK_INTERVAL_SECONDS))
        age_counts = age_bucket_counts(events_snapshot)
        if scan_in_progress:
            scan_status = "Scanning"
        elif state.get("last_error"):
            scan_status = "Error"
        elif watcher_running and not auto_scan_paused and state.get("last_check_at"):
            scan_status = "OK"
        else:
            scan_status = "Idle"
        snapshot = {
            "watcher_running": watcher_running,
            "started_at": state["started_at"],
            "started_at_local": format_local_time(state["started_at"], DASHBOARD_TZ),
            "last_check_at": state["last_check_at"],
            "last_check_local": format_local_time(state["last_check_at"], DASHBOARD_TZ),
            "seen_count": len(state["seen"]),
            "events_count": len(state["events"]),
            "last_cycle_summary": state["last_cycle_summary"],
            "last_error": state["last_error"],
            "posted_within_minutes": POSTED_WITHIN_MINUTES,
            "check_interval_seconds": interval_seconds,
            "dashboard_timezone": DASHBOARD_TIMEZONE,
            "dry_run": DRY_RUN,
            "telegram_enabled": telegram["enabled"],
            "telegram_configured": bool(telegram["bot_token"] and telegram["chat_id"]),
            "telegram_masked_token": mask_telegram_token(telegram["bot_token"]),
            "telegram_chat_id": telegram["chat_id"],
            "trigger_words_count": len(csv_words(telegram.get("trigger_words", []))),
            "keywords_count": len(KEYWORDS),
            "next_scan_in_seconds": next_scan_in,
            "age_green_count": age_counts["green"],
            "age_yellow_count": age_counts["yellow"],
            "age_red_count": age_counts["red"],
            "severity_new_count": age_counts["green"],
            "severity_old_count": age_counts["yellow"],
            "severity_really_old_count": age_counts["red"],
            "scan_status": scan_status,
            "scan_in_progress": scan_in_progress,
            "auto_scan_paused": auto_scan_paused,
            "last_scan_result": state.get("last_scan_result", "idle"),
            "last_scan_started_at": state.get("last_scan_started_at", ""),
            "last_scan_started_local": format_local_time(state.get("last_scan_started_at", ""), DASHBOARD_TZ),
            "last_scan_finished_at": state.get("last_scan_finished_at", ""),
            "last_scan_finished_local": format_local_time(state.get("last_scan_finished_at", ""), DASHBOARD_TZ),
            "learning_loop_enabled": ENABLE_LEARNING_LOOP,
            "multi_channel_alerts_enabled": ENABLE_MULTI_CHANNEL_ALERTS,
            "auto_followup_enabled": bool(state.get("auto_followup_enabled", AUTO_FOLLOWUP_ENABLED)),
            "followup_after_hours": FOLLOWUP_AFTER_HOURS,
            "followup_max_per_cycle": FOLLOWUP_MAX_PER_CYCLE,
            "proposal_tone": PROPOSAL_TONE,
            "metrics": dict(state.get("metrics", {})),
            "workspace_name": WORKSPACE_NAME,
            "site_fetch_budget_seconds": SITE_FETCH_BUDGET_SECONDS,
            "daily_progress": compute_daily_progress(goals, analytics, followups_sent),
            "interviews_count": len(state.get("interviews", [])),
            "rules_count": len(state.get("rules", [])),
        }
    return jsonify(snapshot)


@app.get("/api/logs")
def api_logs():
    limit = request.args.get("limit", default=200, type=int) or 200
    limit = max(1, min(limit, MAX_LOG_LINES))
    with state_lock:
        logs = list(state.get("logs", [])[:limit])
    return jsonify({"logs": logs, "count": len(logs)})


@app.post("/api/control/start")
def api_control_start():
    started, message = start_watcher()
    add_runtime_log(message, "info" if started else "warn")
    return jsonify({"ok": started, "message": message})


@app.post("/api/control/stop")
def api_control_stop():
    stopped, message = stop_watcher(join_timeout=0.2)
    add_runtime_log(message, "warn" if stopped else "info")
    return jsonify({"ok": stopped, "message": message})


@app.post("/api/control/reload")
def api_control_reload():
    seen_count, events_count = reload_runtime_data()
    message = f"Reloaded DB. seen={seen_count} events={events_count}"
    return jsonify({"ok": True, "message": message, "seen_count": seen_count, "events_count": events_count})


@app.post("/api/control/scan-interval")
def api_control_scan_interval():
    body = request.get_json(silent=True) or {}
    _requested_seconds = body.get("seconds", CHECK_INTERVAL_SECONDS)
    interval_seconds = set_runtime_scan_interval_seconds(CHECK_INTERVAL_SECONDS, reset_next_scan=True)
    message = "Scan interval is fixed at 20 second(s)."
    add_runtime_log(message, "info")
    return jsonify({"ok": True, "message": message, "check_interval_seconds": interval_seconds})


@app.post("/api/control/scan-now")
def api_control_scan_now():
    with state_lock:
        running = bool(state.get("watcher_running", False))
        scan_in_progress = bool(state.get("scan_in_progress", False))
        paused = bool(state.get("auto_scan_paused", False))

    if scan_in_progress:
        return jsonify({"ok": True, "message": "Scan already in progress.", "queued": False})

    if running:
        request_manual_scan()
        if paused:
            message = "Manual scan requested (auto-scan is paused)."
        else:
            message = "Manual scan requested."
        add_runtime_log(message, "info")
        return jsonify({"ok": True, "message": message, "queued": True})

    ok, summary, error_text = execute_scan_cycle(trigger_label="manual")
    if ok:
        message = f"Manual scan completed. new_events={summary.get('new_events', 0)}"
        return jsonify({"ok": True, "message": message, "queued": False, "summary": summary})
    return jsonify({"ok": False, "error": error_text or "Manual scan failed.", "queued": False}), 500


@app.post("/api/control/pause")
def api_control_pause():
    paused = set_auto_scan_paused(True)
    message = "Auto-scan paused." if paused else "Auto-scan state unchanged."
    add_runtime_log(message, "warn")
    return jsonify({"ok": True, "message": message, "auto_scan_paused": paused})


@app.post("/api/control/resume")
def api_control_resume():
    paused = set_auto_scan_paused(False)
    message = "Auto-scan resumed."
    add_runtime_log(message, "info")
    return jsonify({"ok": True, "message": message, "auto_scan_paused": paused})


@app.post("/api/control/automation")
def api_control_automation():
    body = request.get_json(silent=True) or {}
    enabled = bool(body.get("enabled", True))
    value = set_auto_followup_enabled(enabled)
    return jsonify({"ok": True, "auto_followup_enabled": value, "message": f"Automation {'enabled' if value else 'disabled'}."})


@app.get("/api/jobs/export.csv")
def api_export_jobs_csv():
    with state_lock:
        events_snapshot = list(state["events"])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "event_key",
            "event_date",
            "posted_at",
            "detected_at_local",
            "title",
            "type_of_work",
            "wage_salary",
            "hours_per_week",
            "date_updated",
            "age_minutes",
            "age_bucket",
            "severity_label",
            "job_score",
            "priority",
            "employer_quality_score",
            "normalized_monthly_usd",
            "budget_type",
            "competitor_density",
            "repost_suspected",
            "keyword_matched",
            "notification_sent",
            "url",
            "description",
        ]
    )

    for event in events_snapshot:
        enriched = enrich_event_for_ui(event, include_heavy=False)
        writer.writerow(
            [
                enriched.get("event_key", ""),
                enriched.get("event_date", ""),
                enriched.get("posted_at", ""),
                enriched.get("detected_at_local", ""),
                enriched.get("title", ""),
                enriched.get("type_of_work", ""),
                enriched.get("wage_salary", ""),
                enriched.get("hours_per_week", ""),
                enriched.get("date_updated", ""),
                enriched.get("age_minutes", ""),
                enriched.get("age_bucket", ""),
                enriched.get("severity_label", ""),
                enriched.get("job_score", ""),
                enriched.get("priority", ""),
                enriched.get("employer_quality_score", ""),
                enriched.get("normalized_monthly_usd", ""),
                enriched.get("budget_type", ""),
                enriched.get("job_brief", {}).get("competitor_density", {}).get("density", ""),
                bool(enriched.get("repost_suspected")),
                bool(enriched.get("keyword_matched")),
                bool(enriched.get("notification_sent")),
                enriched.get("url", ""),
                enriched.get("description", ""),
            ]
        )

    filename = f"onlinejobs_events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/jobs/delete")
def api_delete_jobs():
    body = request.get_json(silent=True) or {}
    target_date = str(body.get("date", "")).strip()
    raw_keys = body.get("event_keys", [])

    event_keys = set()
    if isinstance(raw_keys, (list, tuple, set)):
        for item in raw_keys:
            key = str(item).strip()
            if key:
                event_keys.add(key)

    if not target_date and not event_keys:
        return jsonify({"ok": False, "error": "Provide date or event_keys to delete."}), 400

    deleted = 0
    with state_lock:
        kept_events = []
        for event in state["events"]:
            delete_this = False
            if event_keys and event.get("event_key") in event_keys:
                delete_this = True
            if target_date and event_date_key(event) == target_date:
                delete_this = True

            if delete_this:
                deleted += 1
            else:
                kept_events.append(event)

        state["events"] = kept_events
        state["event_keys"] = {event["event_key"] for event in kept_events}

    if deleted:
        with state_lock:
            snapshot = list(state["events"])
        save_job_events(snapshot)
        add_runtime_log(f"Deleted {deleted} job event(s). date={target_date or '-'}", "warn")

    return jsonify({"ok": True, "deleted": deleted})


@app.get("/api/settings/telegram")
def api_get_telegram_settings():
    with state_lock:
        settings = normalize_telegram_settings(state.get("telegram", {}))

    payload = dict(settings)
    payload["masked_bot_token"] = mask_telegram_token(settings["bot_token"])
    payload["trigger_words_csv"] = ", ".join(settings.get("trigger_words", []))
    return jsonify({"ok": True, "settings": payload})


@app.post("/api/settings/telegram")
def api_set_telegram_settings():
    body = request.get_json(silent=True) or {}
    current = get_runtime_telegram_settings()

    if "bot_token" in body:
        current["bot_token"] = str(body.get("bot_token", "")).strip()
    if "chat_id" in body:
        current["chat_id"] = str(body.get("chat_id", "")).strip()
    if "enabled" in body:
        current["enabled"] = bool(body.get("enabled"))
    if "trigger_words" in body:
        current["trigger_words"] = csv_words(body.get("trigger_words", ""))

    if current["enabled"] and (not current["bot_token"] or not current["chat_id"]):
        return jsonify({"ok": False, "error": "bot_token and chat_id are required when Telegram is enabled."}), 400
    if current["enabled"] and not csv_words(current.get("trigger_words", [])):
        return jsonify({"ok": False, "error": "At least one trigger word is required when Telegram is enabled."}), 400

    saved = update_runtime_telegram_settings(
        bot_token=current["bot_token"],
        chat_id=current["chat_id"],
        enabled=current["enabled"],
        trigger_words=current.get("trigger_words", []),
        persist=True,
    )
    payload = dict(saved)
    payload["masked_bot_token"] = mask_telegram_token(saved["bot_token"])
    payload["trigger_words_csv"] = ", ".join(saved.get("trigger_words", []))
    return jsonify({"ok": True, "settings": payload})


@app.post("/api/settings/telegram/test")
def api_test_telegram():
    settings = get_runtime_telegram_settings()
    if not settings["enabled"]:
        return jsonify({"ok": False, "error": "Telegram is disabled."}), 400
    if not settings["bot_token"] or not settings["chat_id"]:
        return jsonify({"ok": False, "error": "Telegram bot token/chat ID is missing."}), 400
    if not csv_words(settings.get("trigger_words", [])):
        return jsonify({"ok": False, "error": "Set at least one trigger word before testing."}), 400

    ok = send_telegram(
        "If you received this, your mobile alert configuration is working.",
        title="OnlineJobs Watcher Test",
    )
    if not ok:
        return jsonify({"ok": False, "error": "Telegram API send failed."}), 502

    return jsonify({"ok": True})


@app.post("/api/events/<event_key>/feedback")
def api_event_feedback(event_key):
    body = request.get_json(silent=True) or {}
    label = str(body.get("label", "")).strip().lower()
    if label not in {"good", "bad"}:
        return jsonify({"ok": False, "error": "label must be good or bad"}), 400

    with state_lock:
        events = list(state.get("events", []))
        feedback = dict(state.get("feedback", {}))

    matched = None
    for event in events:
        if event.get("event_key") == event_key:
            matched = event
            break
    if not matched:
        return jsonify({"ok": False, "error": "event not found"}), 404

    feedback.setdefault("event_feedback", {})[event_key] = label
    bag = normalize_match_text(f"{matched.get('title', '')} {matched.get('type_of_work', '')}").split(" ")
    bag = [w for w in bag if len(w) >= 4][:8]
    if label == "good":
        feedback["good_words"] = csv_words(list(feedback.get("good_words", [])) + bag)
    else:
        feedback["bad_words"] = csv_words(list(feedback.get("bad_words", [])) + bag)

    saved = save_feedback(feedback)
    with state_lock:
        state["feedback"] = saved
    return jsonify({"ok": True, "feedback": saved})


@app.post("/api/events/<event_key>/proposal")
def api_event_proposal(event_key):
    with state_lock:
        events = list(state.get("events", []))
    matched = None
    for event in events:
        if event.get("event_key") == event_key:
            matched = enrich_event_for_ui(event, include_heavy=True, all_events=events)
            break
    if not matched:
        return jsonify({"ok": False, "error": "event not found"}), 404

    portfolio = select_portfolio_links(matched)
    tone_line = proposal_tone_prefix()
    portfolio_lines = ""
    if portfolio:
        portfolio_lines = "\n".join([f"- {link}" for link in portfolio])
        portfolio_lines = f"\nRelevant samples:\n{portfolio_lines}\n"

    proposal = (
        f"{tone_line}\n\n"
        f"I saw your {matched.get('title', 'project')} post and I can help immediately.\n\n"
        f"I specialize in {matched.get('type_of_work') or 'this role type'} and similar projects. "
        f"Based on your requirements, I can deliver a clean first milestone within 24-48 hours.\n\n"
        f"Why I fit:\n"
        f"- Relevant niche match: {'yes' if matched.get('keyword_matched') else 'partly'}\n"
        f"- Priority score: {matched.get('job_score', 'N/A')}/100\n"
        f"- Competitor density: {matched.get('job_brief', {}).get('competitor_density', {}).get('density', 'unknown')}\n"
        f"- Focus: quality, communication, and fast turnaround\n\n"
        f"{portfolio_lines}"
        f"If helpful, I can send a short action plan tailored to your scope right away.\n\n"
        f"Job link: {matched.get('url', '')}"
    )
    return jsonify({"ok": True, "event_key": event_key, "proposal": proposal, "portfolio_links": portfolio})


@app.get("/api/events/<event_key>/brief")
def api_event_brief(event_key):
    with state_lock:
        events = list(state.get("events", []))
    matched = None
    for event in events:
        if event.get("event_key") == event_key:
            matched = enrich_event_for_ui(event, include_heavy=True, all_events=events)
            break
    if not matched:
        return jsonify({"ok": False, "error": "event not found"}), 404
    brief = matched.get("job_brief", {})
    return jsonify({"ok": True, "event_key": event_key, "brief": brief})


@app.get("/api/events/<event_key>/followup")
def api_event_followup(event_key):
    with state_lock:
        events = list(state.get("events", []))
    matched = None
    for event in events:
        if event.get("event_key") == event_key:
            matched = enrich_event_for_ui(event, include_heavy=True, all_events=events)
            break
    if not matched:
        return jsonify({"ok": False, "error": "event not found"}), 404
    return jsonify({"ok": True, "event_key": event_key, "followup": build_followup_message(matched)})


@app.get("/api/events/<event_key>/interview-prep")
def api_event_interview_prep(event_key):
    if not ENABLE_INTERVIEW_PREP:
        return jsonify({"ok": False, "error": "interview prep disabled"}), 400
    with state_lock:
        events = list(state.get("events", []))
    matched = None
    for event in events:
        if event.get("event_key") == event_key:
            matched = enrich_event_for_ui(event, include_heavy=True, all_events=events)
            break
    if not matched:
        return jsonify({"ok": False, "error": "event not found"}), 404
    return jsonify({"ok": True, "event_key": event_key, "interview_prep": build_interview_prep(matched)})


@app.get("/api/events/<event_key>/bid-suggestion")
def api_event_bid_suggestion(event_key):
    with state_lock:
        events = list(state.get("events", []))
    matched = None
    for event in events:
        if event.get("event_key") == event_key:
            matched = enrich_event_for_ui(event, include_heavy=True, all_events=events)
            break
    if not matched:
        return jsonify({"ok": False, "error": "event not found"}), 404
    return jsonify({"ok": True, "event_key": event_key, "bid_suggestion": suggest_bid_range(matched)})


@app.get("/api/events/<event_key>/skill-gap")
def api_event_skill_gap(event_key):
    with state_lock:
        events = list(state.get("events", []))
    matched = None
    for event in events:
        if event.get("event_key") == event_key:
            matched = enrich_event_for_ui(event, include_heavy=True, all_events=events)
            break
    if not matched:
        return jsonify({"ok": False, "error": "event not found"}), 404
    return jsonify({"ok": True, "event_key": event_key, "skill_gap": detect_skill_gaps(matched)})


@app.get("/api/events/<event_key>/proposal-variants")
def api_event_proposal_variants(event_key):
    with state_lock:
        events = list(state.get("events", []))
    matched = None
    for event in events:
        if event.get("event_key") == event_key:
            matched = enrich_event_for_ui(event, include_heavy=True, all_events=events)
            break
    if not matched:
        return jsonify({"ok": False, "error": "event not found"}), 404
    return jsonify({"ok": True, "event_key": event_key, "variants": proposal_variants(matched)})


@app.get("/api/events/<event_key>/voice-script")
def api_event_voice_script(event_key):
    with state_lock:
        events = list(state.get("events", []))
    matched = None
    for event in events:
        if event.get("event_key") == event_key:
            matched = enrich_event_for_ui(event, include_heavy=True, all_events=events)
            break
    if not matched:
        return jsonify({"ok": False, "error": "event not found"}), 404
    return jsonify({"ok": True, "event_key": event_key, "voice_script": build_voice_note_script(matched)})


@app.get("/api/events/<event_key>/apply-pack")
def api_event_apply_pack(event_key):
    with state_lock:
        events = list(state.get("events", []))
    matched = None
    for event in events:
        if event.get("event_key") == event_key:
            matched = enrich_event_for_ui(event, include_heavy=True, all_events=events)
            break
    if not matched:
        return jsonify({"ok": False, "error": "event not found"}), 404
    payload = {
        "proposal": proposal_variants(matched).get("consultative"),
        "portfolio_links": select_portfolio_links(matched),
        "interview_prep": build_interview_prep(matched),
        "followup": build_followup_message(matched),
    }
    return jsonify({"ok": True, "event_key": event_key, "apply_pack": payload})


@app.get("/api/analytics")
def api_analytics():
    with state_lock:
        events_snapshot = list(state.get("events", []))
        analytics = dict(state.get("analytics", {"applied": {}, "wins": {}}))
        outcomes = dict(state.get("outcomes", {}))
        metrics = dict(state.get("metrics", {}))
    events = [enrich_event_for_ui(e, include_heavy=False) for e in events_snapshot]
    top = sorted(events, key=lambda e: e.get("job_score", 0), reverse=True)[:10]
    avg_score = int(sum(e.get("job_score", 0) for e in events) / len(events)) if events else 0
    high_priority = len([e for e in events if e.get("priority") == "high"])
    total_applied = sum(int(v) for v in analytics.get("applied", {}).values())
    total_wins = sum(int(v) for v in analytics.get("wins", {}).values())
    conversion = round((total_wins / total_applied) * 100, 2) if total_applied else 0.0
    return jsonify(
        {
            "ok": True,
            "totals": {
                "events": len(events),
                "avg_score": avg_score,
                "high_priority": high_priority,
                "applied": total_applied,
                "wins": total_wins,
                "win_rate_percent": conversion,
            },
            "top_opportunities": top,
            "applications": analytics.get("applied", {}),
            "wins": analytics.get("wins", {}),
            "outcomes": outcomes,
            "metrics": metrics,
        }
    )


@app.get("/api/smart-queue")
def api_smart_queue():
    with state_lock:
        events_snapshot = list(state.get("events", []))
    events = [enrich_event_for_ui(e, include_heavy=False) for e in events_snapshot]
    return jsonify({"ok": True, "workspace": WORKSPACE_NAME, "tasks": build_smart_queue(events)})


@app.get("/api/coach/weekly")
def api_weekly_coach():
    with state_lock:
        events_snapshot = list(state.get("events", []))
        analytics = dict(state.get("analytics", {"applied": {}, "wins": {}}))
        outcomes = dict(state.get("outcomes", {}))
    events = [enrich_event_for_ui(e, include_heavy=False) for e in events_snapshot]
    return jsonify({"ok": True, "coach": build_weekly_coach(events, analytics, outcomes)})


@app.get("/api/competitor-heatmap")
def api_competitor_heatmap():
    with state_lock:
        events_snapshot = list(state.get("events", []))
    events = [enrich_event_for_ui(e, include_heavy=True, all_events=events_snapshot) for e in events_snapshot]
    return jsonify({"ok": True, "heatmap": competitor_heatmap(events)})


@app.get("/api/duplicates")
def api_duplicates():
    with state_lock:
        events_snapshot = list(state.get("events", []))
    events = [enrich_event_for_ui(e, include_heavy=False) for e in events_snapshot]
    return jsonify({"ok": True, "clusters": duplicate_clusters(events)})


@app.get("/api/calendar/followups.ics")
def api_calendar_followups():
    with state_lock:
        events_snapshot = list(state.get("events", []))
    events = [enrich_event_for_ui(e, include_heavy=False) for e in events_snapshot]
    now_utc = datetime.now(timezone.utc)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//OnlineJobsWatcher//EN"]
    count = 0
    for event in events:
        detected = parse_iso_to_utc(event.get("detected_at", ""))
        if not detected:
            continue
        due = detected.timestamp() + (FOLLOWUP_AFTER_HOURS * 3600)
        if due < now_utc.timestamp():
            due = now_utc.timestamp() + 3600
        due_dt = datetime.fromtimestamp(due, timezone.utc)
        uid = f"{event.get('event_key','evt')}-{int(due)}@onlinejobs-watcher"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now_utc.strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART:{due_dt.strftime('%Y%m%dT%H%M%SZ')}",
                f"SUMMARY:Follow up - {truncate_text(event.get('title','Job'), 60)}",
                f"DESCRIPTION:{truncate_text(event.get('url',''), 180)}",
                "END:VEVENT",
            ]
        )
        count += 1
        if count >= 30:
            break
    lines.append("END:VCALENDAR")
    return Response("\r\n".join(lines), mimetype="text/calendar")


@app.get("/api/pipeline")
def api_pipeline():
    with state_lock:
        events_snapshot = list(state.get("events", []))
        outcomes = dict(state.get("outcomes", {}))
    events = [enrich_event_for_ui(e, include_heavy=False) for e in events_snapshot]
    return jsonify({"ok": True, "board": pipeline_board(events, outcomes)})


@app.get("/api/goals")
def api_goals():
    with state_lock:
        goals = dict(state.get("goals", {}))
        analytics = dict(state.get("analytics", {"applied": {}, "wins": {}}))
        followups_sent = dict(state.get("followups_sent", {}))
    return jsonify({"ok": True, "goals": goals, "progress": compute_daily_progress(goals, analytics, followups_sent)})


@app.post("/api/goals")
def api_set_goals():
    body = request.get_json(silent=True) or {}
    saved = save_goals(body)
    with state_lock:
        state["goals"] = saved
    return jsonify({"ok": True, "goals": saved})


@app.get("/api/templates")
def api_templates():
    with state_lock:
        templates = dict(state.get("templates", {}))
    return jsonify({"ok": True, "templates": templates})


@app.post("/api/templates")
def api_set_templates():
    body = request.get_json(silent=True) or {}
    saved = save_templates(body)
    with state_lock:
        state["templates"] = saved
    return jsonify({"ok": True, "templates": saved})


@app.get("/api/best-times")
def api_best_times():
    with state_lock:
        events_snapshot = list(state.get("events", []))
        outcomes = dict(state.get("outcomes", {}))
    events = [enrich_event_for_ui(e, include_heavy=False) for e in events_snapshot]
    return jsonify({"ok": True, "best_hours": best_apply_hours(events, outcomes)})


@app.get("/api/replies")
def api_replies():
    with state_lock:
        events_snapshot = list(state.get("events", []))
        outcomes = dict(state.get("outcomes", {}))
    rows = []
    for event in events_snapshot:
        status = str(outcomes.get(event.get("event_key", ""), {}).get("status", "")).lower()
        if status in {"applied", "win"}:
            rows.append({"event_key": event.get("event_key"), "title": event.get("title"), "status": status, "url": event.get("url")})
    return jsonify({"ok": True, "items": rows[:300], "count": len(rows)})


@app.get("/api/interviews")
def api_interviews():
    with state_lock:
        items = list(state.get("interviews", []))
    return jsonify({"ok": True, "items": items})


@app.post("/api/interviews")
def api_add_interview():
    body = request.get_json(silent=True) or {}
    item = {
        "id": f"iv-{int(time.time() * 1000)}",
        "event_key": str(body.get("event_key", "")).strip(),
        "when": str(body.get("when", "")).strip(),
        "notes": str(body.get("notes", "")).strip(),
        "created_at": now_utc_iso(),
    }
    with state_lock:
        items = list(state.get("interviews", []))
    items.insert(0, item)
    saved = save_interviews(items[:500])
    with state_lock:
        state["interviews"] = saved
    return jsonify({"ok": True, "item": item, "count": len(saved)})


@app.get("/api/rules")
def api_rules():
    with state_lock:
        rules = list(state.get("rules", []))
    return jsonify({"ok": True, "rules": rules})


@app.post("/api/rules")
def api_add_rule():
    body = request.get_json(silent=True) or {}
    item = {
        "id": f"rule-{int(time.time() * 1000)}",
        "name": str(body.get("name", "Custom rule")).strip() or "Custom rule",
        "keyword": str(body.get("keyword", "")).strip(),
        "min_score": int(body.get("min_score", 0) or 0),
        "action": str(body.get("action", "flag")).strip() or "flag",
    }
    with state_lock:
        rules = list(state.get("rules", []))
    rules.insert(0, item)
    saved = save_rules(rules[:500])
    with state_lock:
        state["rules"] = saved
    return jsonify({"ok": True, "rule": item, "count": len(saved)})


@app.get("/api/profile-optimizer")
def api_profile_optimizer():
    with state_lock:
        events_snapshot = list(state.get("events", []))
    events = [enrich_event_for_ui(e, include_heavy=False) for e in events_snapshot[:300]]
    gaps = {}
    for event in events:
        for gap in detect_skill_gaps(event).get("gaps", []):
            gaps[gap] = int(gaps.get(gap, 0)) + 1
    top_gaps = sorted(gaps.items(), key=lambda x: x[1], reverse=True)[:10]
    suggestions = [f"Add proof for skill: {name} ({count} jobs mention this)." for name, count in top_gaps]
    return jsonify({"ok": True, "top_gaps": top_gaps, "suggestions": suggestions})


@app.get("/api/mobile/summary")
def api_mobile_summary():
    with state_lock:
        events_snapshot = list(state.get("events", []))
    events = [enrich_event_for_ui(e, include_heavy=False) for e in events_snapshot]
    top = sorted(events, key=lambda e: e.get("job_score", 0), reverse=True)[:5]
    return jsonify({"ok": True, "top": top, "counts": {"total": len(events), "high": len([e for e in events if e.get("priority") == "high"])}})


@app.get("/api/reports/weekly")
def api_reports_weekly():
    with state_lock:
        events_snapshot = list(state.get("events", []))
        analytics = dict(state.get("analytics", {"applied": {}, "wins": {}}))
        outcomes = dict(state.get("outcomes", {}))
    events = [enrich_event_for_ui(e, include_heavy=False) for e in events_snapshot]
    coach = build_weekly_coach(events, analytics, outcomes)
    return jsonify({"ok": True, "weekly_report": {"coach": coach, "best_hours": best_apply_hours(events, outcomes), "heatmap": competitor_heatmap(events)}})


@app.get("/api/team/comments")
def api_team_comments():
    with state_lock:
        team = dict(state.get("team", {"comments": []}))
    return jsonify({"ok": True, "comments": team.get("comments", [])})


@app.post("/api/team/comments")
def api_team_add_comment():
    body = request.get_json(silent=True) or {}
    comment = {
        "id": f"c-{int(time.time() * 1000)}",
        "event_key": str(body.get("event_key", "")).strip(),
        "author": str(body.get("author", "owner")).strip() or "owner",
        "message": str(body.get("message", "")).strip(),
        "created_at": now_utc_iso(),
    }
    if not comment["message"]:
        return jsonify({"ok": False, "error": "message is required"}), 400
    with state_lock:
        team = dict(state.get("team", {"comments": []}))
    comments = list(team.get("comments", []))
    comments.insert(0, comment)
    team["comments"] = comments[:1000]
    saved = save_team_data(team)
    with state_lock:
        state["team"] = saved
    return jsonify({"ok": True, "comment": comment, "count": len(saved.get("comments", []))})


@app.get("/api/plugins/export")
def api_plugins_export():
    target = str(request.args.get("target", "generic")).strip().lower()
    with state_lock:
        events_snapshot = list(state.get("events", []))
    events = [enrich_event_for_ui(e, include_heavy=False) for e in events_snapshot[:200]]
    payload = [{"title": e.get("title"), "score": e.get("job_score"), "url": e.get("url"), "priority": e.get("priority")} for e in events]
    return jsonify({"ok": True, "target": target, "items": payload, "count": len(payload)})


@app.get("/api/event-enhanced/<event_key>")
def api_event_enhanced(event_key):
    with state_lock:
        events_snapshot = list(state.get("events", []))
        rules = list(state.get("rules", []))
    matched = None
    for event in events_snapshot:
        if event.get("event_key") == event_key:
            matched = enrich_event_for_ui(event, include_heavy=True, all_events=events_snapshot)
            break
    if not matched:
        return jsonify({"ok": False, "error": "event not found"}), 404
    payload = {
        "trust_index": employer_trust_index(matched),
        "opportunity_index": opportunity_index(matched),
        "bid_suggestion": suggest_bid_range(matched),
        "skill_gap": detect_skill_gaps(matched),
        "proposal_variants": proposal_variants(matched),
        "voice_script": build_voice_note_script(matched),
        "rules_triggered": evaluate_rules(matched, rules),
    }
    return jsonify({"ok": True, "event_key": event_key, "enhanced": payload})


@app.get("/api/digest")
def api_digest():
    mode = str(request.args.get("mode", "daily")).strip().lower()
    window_hours = 24 if mode == "daily" else 24 * 7
    now_dt = datetime.now(timezone.utc)
    with state_lock:
        events_snapshot = list(state.get("events", []))
    events = [enrich_event_for_ui(e) for e in events_snapshot]
    selected = []
    for event in events:
        detected = parse_iso_to_utc(event.get("detected_at", ""))
        if not detected:
            continue
        if (now_dt - detected).total_seconds() <= window_hours * 3600:
            selected.append(event)
    top = sorted(selected, key=lambda e: e.get("job_score", 0), reverse=True)[:5]
    summary = {
        "mode": mode,
        "window_hours": window_hours,
        "count": len(selected),
        "high_priority_count": len([e for e in selected if e.get("priority") == "high"]),
        "top_jobs": top,
    }
    return jsonify({"ok": True, "digest": summary})


@app.post("/api/events/<event_key>/status")
def api_event_status(event_key):
    body = request.get_json(silent=True) or {}
    status = str(body.get("status", "")).strip().lower()
    reason = str(body.get("reason", "")).strip()
    if status not in {"applied", "win", "lost"}:
        return jsonify({"ok": False, "error": "status must be applied, win, or lost"}), 400

    date_key = datetime.now(DASHBOARD_TZ).strftime("%Y-%m-%d")
    with state_lock:
        analytics = dict(state.get("analytics", {"applied": {}, "wins": {}}))
        outcomes = dict(state.get("outcomes", {}))

    if status in {"applied", "win"}:
        bucket = "applied" if status == "applied" else "wins"
        store = analytics.setdefault(bucket, {})
        store[date_key] = int(store.get(date_key, 0)) + 1

    outcomes[event_key] = {
        "status": status,
        "reason": reason,
        "updated_at": now_utc_iso(),
    }
    saved = save_analytics(analytics)
    saved_outcomes = save_outcomes(outcomes)
    with state_lock:
        state["analytics"] = saved
        state["outcomes"] = saved_outcomes
    return jsonify({"ok": True, "analytics": saved, "outcomes": saved_outcomes})


@app.get("/api/metrics")
def api_metrics():
    with state_lock:
        metrics = dict(state.get("metrics", {}))
        events_count = len(state.get("events", []))
        last_error = state.get("last_error", "")
    payload = {
        "ok": True,
        "metrics": metrics,
        "events_count": events_count,
        "last_error": last_error,
    }
    return jsonify(payload)


@app.post("/api/control/backup")
def api_control_backup():
    ts = datetime.now(DASHBOARD_TZ).strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(DATA_DIR, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    files = [SEEN_FILE, EVENTS_FILE, TELEGRAM_SETTINGS_FILE, FEEDBACK_FILE, ANALYTICS_FILE, OUTCOMES_FILE]
    backed_up = []
    for src in files:
        if not os.path.exists(src):
            continue
        name = os.path.basename(src)
        dst = os.path.join(backup_dir, f"{ts}_{name}")
        try:
            with open(src, "rb") as fsrc:
                data = fsrc.read()
            with open(dst, "wb") as fdst:
                fdst.write(data)
            backed_up.append(dst)
        except Exception as exc:
            add_runtime_log(f"Backup failed for {src}: {exc}", "error")
    return jsonify({"ok": True, "backup_files": backed_up, "count": len(backed_up)})


@app.post("/api/control/restore-latest")
def api_control_restore_latest():
    backup_dir = os.path.join(DATA_DIR, "backups")
    if not os.path.isdir(backup_dir):
        return jsonify({"ok": False, "error": "No backups directory found."}), 404
    candidates = sorted([f for f in os.listdir(backup_dir) if f.endswith(".json")], reverse=True)
    if not candidates:
        return jsonify({"ok": False, "error": "No backup files found."}), 404
    restored = []
    for filename in candidates:
        path = os.path.join(backup_dir, filename)
        parts = filename.split("_", 2)
        if len(parts) < 3:
            continue
        target_name = parts[2]
        target = os.path.join(DATA_DIR, target_name)
        if not os.path.basename(target) in {
            os.path.basename(SEEN_FILE),
            os.path.basename(EVENTS_FILE),
            os.path.basename(TELEGRAM_SETTINGS_FILE),
            os.path.basename(FEEDBACK_FILE),
            os.path.basename(ANALYTICS_FILE),
            os.path.basename(OUTCOMES_FILE),
        }:
            continue
        try:
            with open(path, "rb") as fsrc:
                data = fsrc.read()
            with open(target, "wb") as fdst:
                fdst.write(data)
            restored.append(target)
        except Exception as exc:
            add_runtime_log(f"Restore failed for {filename}: {exc}", "error")
    reload_runtime_data()
    return jsonify({"ok": True, "restored_files": restored, "count": len(restored)})


@app.post("/api/open-url")
def api_open_url():
    body = request.get_json(silent=True) or {}
    url = str(body.get("url", "")).strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"ok": False, "error": "Invalid URL."}), 400
    try:
        webbrowser.open(url, new=2)
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Open failed: {exc}"}), 500


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True})


# ======================
# ENTRYPOINT
# ======================


def main():
    initialize_state()
    try:
        added = startup_backfill_recent_jobs(hours=STARTUP_BACKFILL_HOURS)
        add_runtime_log(f"Startup backfill complete: {added} job(s) loaded from last {STARTUP_BACKFILL_HOURS}h.", "info")
    except Exception as exc:
        add_runtime_log(f"Startup backfill failed: {type(exc).__name__}: {exc}", "error")

    if ENABLE_UI:
        start_watcher()

        if DESKTOP_APP:
            ui_thread = threading.Thread(
                target=lambda: app.run(host=UI_HOST, port=UI_PORT, debug=False, use_reloader=False),
                daemon=True,
            )
            ui_thread.start()
            launch_url = ui_url()

            try:
                import webview

                add_runtime_log(f"Desktop app enabled at {launch_url}", "info")
                webview.create_window(
                    title="OnlineJobs Watcher",
                    url=launch_url,
                    width=1280,
                    height=900,
                    min_size=(960, 640),
                )
                webview.start()
            except Exception as exc:
                add_runtime_log(f"Desktop UI unavailable ({exc}). Falling back to browser mode at {launch_url}", "warn")
                webbrowser.open(launch_url)
                ui_thread.join()
        else:
            launch_url = ui_url()
            add_runtime_log(f"UI enabled at {launch_url}", "info")
            app.run(host=UI_HOST, port=UI_PORT, debug=False, use_reloader=False)
    else:
        add_runtime_log("UI disabled. Running watcher-only mode.", "info")
        try:
            watcher_stop_event.clear()
            watcher_loop(watcher_stop_event)
        except KeyboardInterrupt:
            watcher_stop_event.set()
            add_runtime_log("Watcher interrupted by user.", "warn")


if __name__ == "__main__":
    main()
