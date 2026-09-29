import random
import re
import time


GENERATION_TERMS = (
    "comfyui", "flux", "lora", "stable diffusion", "sdxl", "controlnet",
    "ip-adapter", "image generation", "generative image", "generative art",
    "ai image", "ai artist", "ai video", "video generation", "generative video",
    "ai filmmaker", "ai film", "text-to-video", "text to video", "image-to-video",
    "image to video", "kling", "runway", "hunyuanvideo", "animatediff",
    "ai content creator", "ai creative", "ai production", "generative ai",
    "ai automation", "chatbot", "automation engineer", "n8n", "make.com",
    "zapier", "python automation",
)


class SourceBlocked(RuntimeError):
    """The platform requires login or served a security challenge."""


def is_generation_job(title, description=""):
    text = f"{title} {description}".lower()
    return any(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text) for term in GENERATION_TERMS)


def with_retries(fetch, attempts=2):
    for attempt in range(attempts):
        try:
            return fetch()
        except SourceBlocked:
            raise
        except Exception:
            if attempt + 1 >= attempts:
                raise
            time.sleep(random.uniform(1.0, 2.0))


def public_page(url, timeout_ms=15000):
    """Read public browser content; never log in or solve challenges."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if response and response.status in {202, 403, 429}:
                return response.status, page.url, ""
            time.sleep(random.uniform(0.6, 1.4))
            try:
                html = page.content()
            except Exception:
                html = ""
            return (response.status if response else 0), page.url, html
        finally:
            browser.close()
