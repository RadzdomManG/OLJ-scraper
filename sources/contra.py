from .common import SourceBlocked, public_page


LIST_URL = "https://contra.com/jobs"


def fetch():
    status, url, _ = public_page(LIST_URL)
    if status >= 400 or "/log-in" in url:
        raise SourceBlocked("Contra's job feed requires an account login")
    raise SourceBlocked("Contra has no verified public job listing feed")
