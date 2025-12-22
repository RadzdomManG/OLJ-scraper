import requests
import time
import json
import os
from bs4 import BeautifulSoup
from config import *

DATA_FILE = "data/seen_jobs.json"
MAX_RETRIES = 2  # Retry failed job detail pages this many times

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/118.0.5993.118 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Referer": JOB_URL
}

session = requests.Session()
session.headers.update(HEADERS)


def load_seen_jobs():
    if not os.path.exists(DATA_FILE):
        return set()
    with open(DATA_FILE, "r") as f:
        return set(json.load(f))


def save_seen_jobs(jobs):
    os.makedirs("data", exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(list(jobs), f)


def send_push(message, title="OnlineJobsPH"):
    url = "https://api.pushover.net/1/messages.json"
    data = {
        "token": PUSHOVER_API_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "device": DEVICE_NAME,
        "title": title,
        "message": message,
        "priority": 1
    }
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print("Pushover error:", e)


def fetch_job_detail(url):
    """Fetch job description + skills with retry"""
    for attempt in range(MAX_RETRIES):
        try:
            r2 = session.get(url, timeout=20)
            r2.raise_for_status()
            job_soup = BeautifulSoup(r2.text, "lxml")
            desc_div = job_soup.find("div", {"id": "jobdescription"})
            description = desc_div.get_text(separator=" ", strip=True) if desc_div else ""
            skills_div = job_soup.find("div", {"id": "skills"})
            skills = skills_div.get_text(separator=" ", strip=True) if skills_div else ""
            return description, skills
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1} failed for {url}: {e}")
            time.sleep(2)  # short delay before retry
    print(f"Failed to fetch job details after {MAX_RETRIES} attempts: {url}")
    return "", ""  # fallback empty content


def fetch_jobs():
    try:
        r = session.get(JOB_URL, timeout=20)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching main page: {e}")
        return {}

    soup = BeautifulSoup(r.text, "lxml")
    jobs = {}

    for a in soup.select("a[href^='/jobseekers/job/']"):
        href = a["href"]
        job_id = href.split("/")[-1]
        title = a.get_text(strip=True)
        url = "https://www.onlinejobs.ph" + href

        description, skills = fetch_job_detail(url)
        jobs[job_id] = {
            "title": title,
            "url": url,
            "description": description,
            "skills": skills
        }

    return jobs


def main():
    seen = load_seen_jobs()
    print(f"Monitoring OnlineJobsPH Data Entry jobs at {JOB_URL}")
    print(f"Already seen {len(seen)} jobs.\n")

    while True:
        print(f"[{time.strftime('%H:%M:%S')}] Checking for jobs...", end="", flush=True)
        jobs = fetch_jobs()
        print(f" found {len(jobs)} jobs.")

        new_jobs = []
        for job_id, job in jobs.items():
            if job_id not in seen:
                new_jobs.append(job)
                seen.add(job_id)

        if new_jobs:
            print(f"--> {len(new_jobs)} new job(s) found!")
            for job in new_jobs:
                msg = f"🔥 New Job: {job['title']}\n{job['url']}"
                send_push(msg)
                print(f"Sent notification: {job['title']}")
            save_seen_jobs(seen)
        else:
            print("--> No new jobs.")

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

from flask import Flask
app = Flask(__name__)

@app.route("/")
def index():
    return "Watcher alive!"

if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=10000)).start()
    main()  # run your watcher


