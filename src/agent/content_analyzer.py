"""
Phase 4a: LLM content analyzer.

Given a URL, scrapes its visible page text (via Playwright) and asks Claude
to assess it for deceptive/scam/phishing content patterns, returning a
structured JSON verdict — not just a vague "looks suspicious."

Requires ANTHROPIC_API_KEY to be set in a .env file at the project root.

Run standalone for testing:
    python src/agent/content_analyzer.py https://example.com
"""

import json
import os
import sys
from pathlib import Path

from groq import Groq  
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[1] / "collectors"))
from lightweight_scraper import scrape_page_text_lightweight

load_dotenv()  # reads .env and sets CEREBRAS_API_KEY into the environment

MODEL = "llama-3.3-70b-versatile"
MAX_PAGE_CHARS = 6000  # cap how much page text we send, to control cost/latency


def scrape_page_text(url: str, timeout_ms: int = 15000) -> dict:
    """
    Extract a page's visible text content. Uses a lightweight HTTP+HTML-parse
    approach (no full browser) - lower resource use, important for a shared
    deployment serving multiple concurrent users. Trade-off: does not execute
    JavaScript, so heavily JS-rendered pages may return sparse text.
    """
    return scrape_page_text_lightweight(url)


CONTENT_ANALYSIS_PROMPT = """You are a security analyst assessing a webpage for scam, phishing, or spam \
content patterns. You will be given the page title and visible text content.

Analyze it for:
- Urgency/scarcity manipulation ("act now", "account will be suspended", countdown timers implied in text)
- Credential/payment info requests that seem out of place for the apparent site type
- Brand impersonation language (claiming to be a bank/company without matching official patterns)
- Poor grammar/spelling anomalies uncharacteristic of a professional site
- Keyword stuffing or SEO spam patterns (repetitive irrelevant keywords)
- Vague or missing legitimate business information (no real contact info, generic claims)

Respond ONLY with valid JSON in exactly this format, no other text:
{
  "content_risk_score": <float 0.0 to 1.0, where 1.0 = highly deceptive>,
  "flags": [<list of short strings naming specific patterns found, empty list if none>],
  "reasoning": "<1-2 sentence plain-English explanation citing specific evidence from the text>"
}

Page title: __TITLE__

Page text:
__TEXT__
"""


def analyze_content(title: str, text: str) -> dict:
    """Send scraped page content to Cerebras (Llama 3.3 70B) for structured deceptive-pattern analysis."""
    client = Groq()  # reads GROQ_API_KEY from environment automatically

    prompt = CONTENT_ANALYSIS_PROMPT.replace("__TITLE__", title or "(no title)")
    prompt = prompt.replace("__TEXT__", text or "(no text extracted)")

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=500,
        temperature=0,  # deterministic output - critical for reproducible evaluation
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.choices[0].message.content.strip()

    # Claude should return pure JSON per the prompt, but strip markdown fences defensively
    raw_text = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {
            "content_risk_score": None,
            "flags": [],
            "reasoning": f"Failed to parse model response as JSON. Raw response: {raw_text[:300]}",
        }


def analyze_url_content(url: str) -> dict:
    """Full pipeline: scrape a URL's content, then analyze it. Returns combined result."""
    scraped = scrape_page_text(url)

    if scraped["error"] is not None:
        return {
            "url": url,
            "content_risk_score": None,
            "flags": [],
            "reasoning": f"Could not scrape page content: {scraped['error']}",
            "scrape_error": scraped["error"],
        }

    analysis = analyze_content(scraped["title"], scraped["text"])
    analysis["url"] = url
    analysis["scrape_error"] = None
    return analysis


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python src/agent/content_analyzer.py <url>")
        sys.exit(1)

    target_url = sys.argv[1]
    print(f"Analyzing content for: {target_url}\n")

    result = analyze_url_content(target_url)
    print(json.dumps(result, indent=2))