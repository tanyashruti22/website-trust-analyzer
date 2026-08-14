"""
Phase 6c: Lightweight content scraper (deployment-friendly alternative to Playwright).

Playwright launches a full Chromium browser per request - heavy on memory/CPU,
which is risky for a free-tier host serving multiple concurrent users. This
uses plain HTTP + HTML parsing instead: much lighter and faster, at the cost
of not executing JavaScript (so heavily JS-rendered pages may return sparse
text). Good tradeoff for a shared, publicly-deployed instance.
"""

import requests
from bs4 import BeautifulSoup

MAX_PAGE_CHARS = 6000
REQUEST_TIMEOUT = 10

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def scrape_page_text_lightweight(url: str) -> dict:
    """
    Fetch a page with plain HTTP and extract visible text via BeautifulSoup.
    Same return shape as the Playwright version in content_analyzer.py, so
    it's a drop-in replacement.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # strip non-visible/non-content tags before extracting text
        for tag in soup(["script", "style", "noscript", "head"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else None
        text = soup.get_text(separator=" ", strip=True)[:MAX_PAGE_CHARS]

        return {"title": title, "text": text, "error": None}

    except Exception as e:
        return {"title": None, "text": None, "error": str(e)}