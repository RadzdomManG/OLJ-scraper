"""SQLite persistence for jobs, deduplication, and owner settings."""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone


DEFAULT_KEYWORDS = [
    "ComfyUI", "AI automation", "AI image", "AI video", "LoRA",
    "Stable Diffusion", "Flux", "generative AI", "chatbot",
    "automation engineer", "n8n", "Make.com", "Zapier", "Python automation",
]


class JobStore:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    event_key TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS jobs_source_detected ON jobs(source, detected_at DESC);
                CREATE TABLE IF NOT EXISTS seen_jobs (event_key TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS source_settings (
                    source TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL,
                    interval_seconds INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS job_stages (
                    event_key TEXT PRIMARY KEY,
                    stage TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA journal_mode=WAL")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def load_jobs(self):
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM jobs ORDER BY detected_at DESC").fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_jobs(self, jobs):
        with self.connect() as db:
            db.execute("CREATE TEMP TABLE current_keys (event_key TEXT PRIMARY KEY)")
            db.executemany("INSERT INTO current_keys VALUES (?)", ((job["event_key"],) for job in jobs))
            db.executemany(
                "INSERT INTO jobs (event_key, source, detected_at, payload) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(event_key) DO UPDATE SET source=excluded.source, detected_at=excluded.detected_at, payload=excluded.payload",
                ((job["event_key"], job.get("site_type", ""), job.get("detected_at", ""), json.dumps(job, ensure_ascii=False)) for job in jobs),
            )
            db.execute("DELETE FROM jobs WHERE event_key NOT IN (SELECT event_key FROM current_keys)")

    def load_seen(self):
        with self.connect() as db:
            return {row[0] for row in db.execute("SELECT event_key FROM seen_jobs")}

    def add_seen(self, keys):
        with self.connect() as db:
            db.executemany("INSERT OR IGNORE INTO seen_jobs (event_key) VALUES (?)", ((key,) for key in keys))

    def source_settings(self, defaults):
        with self.connect() as db:
            for source, enabled, interval in defaults:
                db.execute("INSERT OR IGNORE INTO source_settings VALUES (?, ?, ?)", (source, int(enabled), int(interval)))
                if source == "remotive" and interval == 1800:
                    db.execute("UPDATE source_settings SET interval_seconds = 1800 WHERE source = 'remotive' AND interval_seconds = 21600")
            rows = db.execute("SELECT source, enabled, interval_seconds FROM source_settings").fetchall()
        return {source: {"enabled": bool(enabled), "interval_seconds": interval} for source, enabled, interval in rows}

    def set_source(self, source, enabled, interval_seconds):
        with self.connect() as db:
            db.execute("INSERT INTO source_settings VALUES (?, ?, ?) ON CONFLICT(source) DO UPDATE SET enabled=excluded.enabled, interval_seconds=excluded.interval_seconds", (source, int(enabled), int(interval_seconds)))

    def match_settings(self):
        with self.connect() as db:
            rows = dict(db.execute("SELECT key, value FROM settings WHERE key IN ('include_keywords', 'exclude_keywords')"))
        return {
            "include_keywords": json.loads(rows["include_keywords"]) if "include_keywords" in rows else DEFAULT_KEYWORDS[:],
            "exclude_keywords": json.loads(rows["exclude_keywords"]) if "exclude_keywords" in rows else [],
        }

    def set_match_settings(self, include_keywords, exclude_keywords):
        with self.connect() as db:
            db.executemany(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (("include_keywords", json.dumps(include_keywords)), ("exclude_keywords", json.dumps(exclude_keywords))),
            )

    def stages(self):
        with self.connect() as db:
            return {key: stage for key, stage in db.execute("SELECT event_key, stage FROM job_stages")}

    def set_stage(self, event_key, stage):
        with self.connect() as db:
            db.execute(
                "INSERT INTO job_stages (event_key, stage, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(event_key) DO UPDATE SET stage=excluded.stage, updated_at=excluded.updated_at",
                (event_key, stage, datetime.now(timezone.utc).isoformat()),
            )
