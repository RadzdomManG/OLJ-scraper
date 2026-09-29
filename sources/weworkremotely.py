"""We Work Remotely's official all-jobs RSS feed."""

from .rss_common import field, html_text, iso_date, link_id, rss_items, valid_link


FEED_URL = "https://weworkremotely.com/remote-jobs.rss"


def parse(content):
    jobs = {}
    for item in rss_items(content):
        title, url = field(item, "title"), field(item, "link")
        if not title or not valid_link(url, {"weworkremotely.com", "www.weworkremotely.com"}):
            continue
        company, separator, role = title.partition(": ")
        jobs[link_id(url)] = {
            "title": role if separator else title,
            "url": url,
            "description": html_text(field(item, "description")),
            "posted_at": iso_date(field(item, "pubDate")),
            "type_of_work": field(item, "type"),
            "wage_salary": "",
            "hours_per_week": "",
            "company": company if separator else "",
            "skills": [field(item, "skills")] if field(item, "skills") else [],
            "location": ", ".join(x for x in (field(item, "region"), field(item, "country")) if x),
            "remote": True,
        }
    return jobs


def fetch(http, url=FEED_URL, timeout=20):
    response = http.get(url, timeout=timeout)
    response.raise_for_status()
    return parse(response.content)
