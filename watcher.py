import requests
import time
import json
import os
from bs4 import BeautifulSoup

# ======================
# CONFIG
# ======================

JOB_URL = "https://www.onlinejobs.ph/jobseekers/search/c/office-and-administration--data-entry"

CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", 30))
HEARTBEAT_INTERVAL = 3600  # 1 hour

PUSHOVER_USER_KEY = os.environ.get("PUSHOVER_USER_KEY")
PUSHOVER_API_TOKEN = os.environ.get("PUSHOVER_API_TOKEN")
DEVICE_NAME = os.environ.get("DEVICE_NAME", "")

DATA_FILE = "data/seen_jobs.json"
KEYWORDS = ["data entry"]

MAX_RETRIES = 2
TIMEOUT = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120 Safari/537.36"
}

session = requests.Session()
session.headers.update(HEADERS)

# ======================
# UTILS
# ======================

def send_push(message, title="OnlineJobs Watcher"):
    try:
        requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": PUSHOVER_API_TOKEN,
                "user": PUSHOVER_USER_KEY,
                "device": DEVICE_NAME,
                "title": title,
                "message": message,
                "priority": 0
            },
            timeout=10
        )
    except Exception as e:
        print("Pushover error:", e)


def load_seen_jobs():
    if not os.path.exists(DATA_FILE):
        return set()
    with open(DATA_FILE, "r") as f:
        return set(json.load(f))


def save_seen_jobs(seen):
    os.makedirs("data", exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(list(seen), f)


def keyword_match(text):
    text = text.lower()
    return any(k in text for k in KEYWORDS)


# ======================
# SCRAPING
# ======================

def fetch_job_detail(url):
    for attempt in range(MAX_RETRIES):
        try:
            r = session.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")

            desc = soup.find("div", id="jobdescription")
            skills = soup.find("div", id="skills")

            description = desc.get_text(" ", strip=True) if desc else ""
            skills_text = skills.get_text(" ", strip=True) if skills else ""

            return description, skills_text
        except Exception as e:
            print(f"Detail fetch failed ({attempt+1}/{MAX_RETRIES}): {e}")
            time.sleep(2)

    return "", ""


def fetch_jobs():
    jobs = {}

    try:
        r = session.get(JOB_URL, timeout=TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        print("Main page fetch error:", e)
        return jobs

    soup = BeautifulSoup(r.text, "lxml")

    for a in soup.select("a[href^='/jobseekers/job/']"):
        href = a["href"]
        job_id = href.split("/")[-1]
        title = a.get_text(strip=True)
        url = "https://www.onlinejobs.ph" + href

        desc, skills = fetch_job_detail(url)
        combined_text = f"{title} {desc} {skills}"

        if keyword_match(combined_text):
            jobs[job_id] = {
                "title": title,
                "url": url
            }

    return jobs


# ======================
# MAIN LOOP
# ======================

def main():
    seen = load_seen_jobs()
    last_heartbeat = 0

    send_push("🟢 Watcher started successfully on Google Cloud", "Watcher Status")

    print("Watcher started. Seen jobs:", len(seen))

    while True:
        now = time.time()

        print(f"[{time.strftime('%H:%M:%S')}] Checking jobs...", end=" ")
        jobs = fetch_jobs()
        print(f"found {len(jobs)} matching jobs")

        new_jobs = []

        for job_id, job in jobs.items():
            if job_id not in seen:
                new_jobs.append(job)
                seen.add(job_id)

        if new_jobs:
            for job in new_jobs:
                send_push(
                    f"🔥 {job['title']}\n{job['url']}",
                    title="New Data Entry Job"
                )
                print("New job:", job["title"])

            save_seen_jobs(seen)
        else:
            print("No new jobs.")

        # Heartbeat
        if now - last_heartbeat >= HEARTBEAT_INTERVAL:
            send_push("💓 Watcher is running normally", "Heartbeat")
            last_heartbeat = now

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
