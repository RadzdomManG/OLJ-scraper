import requests
import time
import json
import os
from bs4 import BeautifulSoup

# ======================
# CONFIG
# ======================

JOB_SITES = [
    {
        "name": "OnlineJobsPH Data Entry",
        "url": "https://www.onlinejobs.ph/jobseekers/search/c/office-and-administration--data-entry",
        "pushover_user": "u6ckbmp23xewib4aenxto4ozzkxdrh",
        "pushover_token": "ao75gi1uday5j316o26x2s2nuaewf5",
        "device": "Rn13pp",
        "type": "onlinejobsph"
    },
    {
        "name": "Freelancer Data Entry",
        "url": "https://www.freelancer.ph/jobs/data-entry",
        "pushover_user": "u6ckbmp23xewib4aenxto4ozzkxdrh",
        "pushover_token": "a4x8icij6x5f2osisxp6qpvkrknjtr",
        "device": "Rn13pp",
        "type": "freelancer"
    }
]

CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", 30))
HEARTBEAT_INTERVAL = 3600  # 1 hour
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

def send_push(message, title="Job Alert", pushover_user=None, pushover_token=None, device=None):
    try:
        requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": pushover_token,
                "user": pushover_user,
                "device": device or "",
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
# FETCH JOBS
# ======================

def fetch_job_detail_onlinejobsph(url):
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
            print(f"OnlineJobsPH detail fetch failed ({attempt+1}/{MAX_RETRIES}): {e}")
            time.sleep(2)
    return "", ""


def fetch_jobs(site):
    jobs = {}
    try:
        r = session.get(site["url"], timeout=TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        print(f"{site['name']} fetch error:", e)
        return jobs

    soup = BeautifulSoup(r.text, "lxml")

    if site["type"] == "onlinejobsph":
        for a in soup.select("a[href^='/jobseekers/job/']"):
            href = a["href"]
            job_id = href.split("/")[-1]
            title = a.get_text(strip=True)
            url_full = "https://www.onlinejobs.ph" + href
            desc, skills = fetch_job_detail_onlinejobsph(url_full)
            combined_text = f"{title} {desc} {skills}"
            if keyword_match(combined_text):
                jobs[job_id] = {
                    "title": f"[OnlineJobsPH] {title}",
                    "url": url_full
                }

    elif site["type"] == "freelancer":
        for job_card in soup.select("div.JobSearchCard-item"):
            a = job_card.select_one("a")
            if not a:
                continue
            href = a.get("href")
            job_id = href.split("/")[-1]
            title = a.get_text(strip=True)
            url_full = "https://www.freelancer.ph" + href
            combined_text = title.lower()  # Freelancer doesn’t give detailed description easily
            if keyword_match(combined_text):
                jobs[job_id] = {
                    "title": f"[Freelancer] {title}",
                    "url": url_full
                }

    return jobs


# ======================
# MAIN LOOP
# ======================

def main():
    seen = load_seen_jobs()
    last_heartbeat = 0

    # Send startup notification using first site's Pushover
    send_push("🟢 Watcher started successfully", "Watcher Status",
              pushover_user=JOB_SITES[0]["pushover_user"],
              pushover_token=JOB_SITES[0]["pushover_token"],
              device=JOB_SITES[0]["device"])

    print("Watcher started. Seen jobs:", len(seen))

    while True:
        now = time.time()
        new_jobs_all = []

        for site in JOB_SITES:
            print(f"[{time.strftime('%H:%M:%S')}] Checking {site['name']}...", end=" ")
            jobs = fetch_jobs(site)
            print(f"found {len(jobs)} jobs")

            for job_id, job in jobs.items():
                if job_id not in seen:
                    new_jobs_all.append((job, site))
                    seen.add(job_id)

        if new_jobs_all:
            for job, site in new_jobs_all:
                send_push(
                    f"🔥 {job['title']}\n{job['url']}",
                    title=f"New Job from {site['name']}",
                    pushover_user=site["pushover_user"],
                    pushover_token=site["pushover_token"],
                    device=site["device"]
                )
                print("New job:", job["title"])
            save_seen_jobs(seen)
        else:
            print("No new jobs.")

        # Heartbeat
        if now - last_heartbeat >= HEARTBEAT_INTERVAL:
            for site in JOB_SITES:
                send_push("💓 Watcher running", f"Heartbeat - {site['name']}",
                          pushover_user=site["pushover_user"],
                          pushover_token=site["pushover_token"],
                          device=site["device"])
            last_heartbeat = now

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()