"""Read Remotive's public category RSS feeds without an API or account."""

import hashlib
import random
import time
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

from bs4 import BeautifulSoup


FEED_INDEX_URL = "https://remotive.com/remote-jobs/rss-feed"
FEED_PREFIX = "/remote-jobs/feed/"


def feed_urls(html):
    soup = BeautifulSoup(html, "lxml")
    urls = []
    for anchor in soup.select("a[href]"):
        url = urljoin(FEED_INDEX_URL, anchor["href"])
        parsed = urlparse(url)
        if parsed.hostname in {"remotive.com", "www.remotive.com"} and parsed.path.startswith(FEED_PREFIX):
            urls.append(url)
    return list(dict.fromkeys(urls))


def parse_feed(content):
    root = ElementTree.fromstring(content)
    if root.tag != "rss":
        raise ValueError("Remotive did not return an RSS feed")
    jobs = {}
    for item in root.findall("./channel/item"):
        def field(tag):
            return (item.findtext(tag) or "").strip()

        title, url = field("title"), field("link")
        if not title or urlparse(url).hostname not in {"remotive.com", "www.remotive.com"}:
            continue
        job_id = field("jobId") or hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        posted = field("pubDate")
        if posted:
            try:
                posted = parsedate_to_datetime(posted).isoformat()
            except (TypeError, ValueError):
                posted = ""
        jobs[job_id] = {
            "title": title, "url": url,
            "description": BeautifulSoup(field("description"), "lxml").get_text(" ", strip=True),
            "posted_at": posted, "type_of_work": field("type").replace("_", " "),
            "wage_salary": field("salary"), "hours_per_week": "",
            "company": field("company"), "skills": [], "location": field("location"),
            "remote": True,
        }
    return jobs


def fetch(http, index_url=FEED_INDEX_URL, timeout=20):
    response = http.get(index_url, timeout=timeout)
    response.raise_for_status()
    urls = feed_urls(response.text)
    if not urls:
        raise ValueError("Remotive has no public category feed links")
    jobs = {}
    errors = []
    for index, url in enumerate(urls):
        if index:
            time.sleep(random.uniform(0.15, 0.4))
        try:
            feed = http.get(url, timeout=timeout)
            feed.raise_for_status()
            jobs.update(parse_feed(feed.content))
        except Exception as exc:
            errors.append(f"{urlparse(url).path}: {exc}")
    if errors:
        raise RuntimeError("Remotive category feeds failed: " + "; ".join(errors[:3]))
    return jobs
