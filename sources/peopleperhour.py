from bs4 import BeautifulSoup

from .common import SourceBlocked, public_page


LIST_URL = "https://www.peopleperhour.com/freelance-jobs/artificial-intelligence"


def fetch():
    status, _, html = public_page(LIST_URL)
    soup = BeautifulSoup(html, "lxml")
    if status in {202, 403, 429} or not soup.select('a[href*="/freelance-jobs/"]'):
        raise SourceBlocked("PeoplePerHour served a bot challenge or no public listings")
    # Public access varies by region and session. Do not report coverage until
    # the listing format can be verified against actual source posts.
    raise SourceBlocked("PeoplePerHour public listings are not reliably accessible")
