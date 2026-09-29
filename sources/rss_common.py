"""Small helpers for public, account-free job feeds."""

import hashlib
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from xml.etree import ElementTree

from bs4 import BeautifulSoup


CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"


def rss_items(content):
    root = ElementTree.fromstring(content)
    if root.tag != "rss":
        raise ValueError("Source did not return RSS")
    return root.findall("./channel/item")


def field(item, name):
    return (item.findtext(name) or "").strip()


def html_text(value):
    return BeautifulSoup(value or "", "lxml").get_text(" ", strip=True)


def iso_date(value):
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError):
        return ""


def valid_link(url, domains):
    return urlparse(url).hostname in domains


def link_id(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
