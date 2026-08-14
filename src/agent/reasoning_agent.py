"""
Phase 4b: Reasoning / fusion agent.

This is the core differentiator of the project: takes the ML model's
technical risk score AND the LLM content analyzer's score, plus the raw
evidence behind both, and asks an LLM to synthesize ONE final verdict with
an evidence-backed explanation - each claim traceable to actual extracted
data, not just an LLM guessing.

Run standalone for testing:
    python src/agent/reasoning_agent.py https://example.com
"""

import json
import sys
from pathlib import Path

import joblib
from groq import Groq
from dotenv import load_dotenv

# import sibling/parent modules
sys.path.append(str(Path(__file__).resolve().parents[1] / "collectors"))
from technical_signals import collect_technical_signals
from feature_extraction import extract_features
from content_analyzer import analyze_url_content

load_dotenv()

MODEL = "llama-3.3-70b-versatile"
TECHNICAL_MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "technical_model.joblib"

FEATURE_COLUMNS = [
    "domain_age_days", "domain_age_missing",
    "has_valid_ssl", "ssl_self_signed_like", "is_reachable",
    "redirect_count", "unique_domains_in_chain",
    "domain_length", "num_hyphens", "num_digits", "num_subdomains", "uses_https",
]

_technical_model = None  # lazy-loaded singleton, avoid reloading from disk every call


def get_technical_model():
    global _technical_model
    if _technical_model is None:
        _technical_model = joblib.load(TECHNICAL_MODEL_PATH)
    return _technical_model


def get_technical_verdict(url: str) -> dict:
    """Run the Phase 2/3 pipeline: collect signals, extract features, score with the trained model."""
    raw_signals = collect_technical_signals(url)
    features = extract_features(raw_signals)

    model = get_technical_model()
    feature_row = [[features[col] for col in FEATURE_COLUMNS]]
    risk_probability = model.predict_proba(feature_row)[0][1]  # probability of class "risky"

    return {
        "technical_risk_score": round(float(risk_probability), 3),
        "raw_signals": raw_signals,
        "features": features,
    }


FUSION_PROMPT = """You are a senior security analyst producing a final verdict on whether a website \
is safe, given evidence from TWO independent detection systems. Synthesize them into one \
coherent, evidence-backed explanation. Every claim you make must be traceable to the \
evidence provided below - do not invent details not present in the evidence.

=== TECHNICAL SIGNAL EVIDENCE ===
URL: __URL__
Domain: __DOMAIN__
Technical model risk score: __TECH_SCORE__ (0.0 = safe, 1.0 = risky)
Domain age: __DOMAIN_AGE__
Domain age unknown: __AGE_MISSING__
Has valid SSL: __HAS_SSL__
SSL looks self-signed: __SELF_SIGNED__
Site reachable: __REACHABLE__
Redirect count: __REDIRECT_COUNT__
Unique domains in redirect chain: __UNIQUE_DOMAINS__
Domain length: __DOMAIN_LENGTH__ characters
Number of hyphens in domain: __NUM_HYPHENS__
Number of digits in domain: __NUM_DIGITS__
Number of subdomains: __NUM_SUBDOMAINS__

=== CONTENT ANALYSIS EVIDENCE ===
Content model risk score: __CONTENT_SCORE__ (0.0 = safe, 1.0 = deceptive, null = could not be analyzed)
Flags found in content: __CONTENT_FLAGS__
Content analyzer's notes: __CONTENT_REASONING__

IMPORTANT: If the content risk score is null/None, this means the page could
NOT be scraped for a technical reason (bot blocking, connection timeout,
JavaScript rendering issue, temporary downtime, etc.) - it is common and
happens to many legitimate sites. A failed scrape is NOT evidence of risk
by itself and must NOT be used to justify a higher risk verdict. In this
case, base your verdict primarily on the technical signal evidence above.

IMPORTANT - UNKNOWN DOMAIN AGE IS NOT AUTOMATICALLY SUSPICIOUS: A domain age
of "Unknown" means the WHOIS lookup failed or returned no data - this has
several common, entirely legitimate causes: privacy-protected registrations,
corporate-owned custom top-level domains (e.g. a company's own ".brand" TLD),
or WHOIS servers that don't respond to automated queries. Do NOT treat an
unknown domain age as strong evidence of risk on its own. Weigh it alongside
other evidence (SSL validity, reachability, content) rather than as a red
flag by itself.

=== YOUR TASK ===
Respond ONLY with valid JSON in exactly this format, no other text:
{
  "final_verdict": "<one of: safe, suspicious, likely_scam, likely_phishing>",
  "confidence": <float 0.0 to 1.0>,
  "explanation": "<2-4 sentences citing SPECIFIC evidence values above, written like a security analyst's summary for a non-technical reader>"
}
"""

def build_fusion_prompt(technical_result: dict, content_result: dict, url: str) -> str:
    features = technical_result["features"]
    raw = technical_result["raw_signals"]

    # Present missing domain age in human-readable form - never leak the raw
    # -1 sentinel value, which reads as a nonsensical "negative age" to the LLM.
    if features["domain_age_missing"]:
        domain_age_display = "Unknown (WHOIS lookup failed or returned no data)"
    else:
        domain_age_display = f"{features['domain_age_days']} days"

    prompt = FUSION_PROMPT
    prompt = prompt.replace("__URL__", url)
    prompt = prompt.replace("__DOMAIN__", raw["domain"])
    prompt = prompt.replace("__TECH_SCORE__", str(technical_result["technical_risk_score"]))
    prompt = prompt.replace("__DOMAIN_AGE__", domain_age_display)
    prompt = prompt.replace("__AGE_MISSING__", str(bool(features["domain_age_missing"])))
    prompt = prompt.replace("__HAS_SSL__", str(bool(features["has_valid_ssl"])))
    prompt = prompt.replace("__SELF_SIGNED__", str(bool(features["ssl_self_signed_like"])))
    prompt = prompt.replace("__REACHABLE__", str(bool(features["is_reachable"])))
    prompt = prompt.replace("__REDIRECT_COUNT__", str(features["redirect_count"]))
    prompt = prompt.replace("__UNIQUE_DOMAINS__", str(features["unique_domains_in_chain"]))
    prompt = prompt.replace("__DOMAIN_LENGTH__", str(features["domain_length"]))
    prompt = prompt.replace("__NUM_HYPHENS__", str(features["num_hyphens"]))
    prompt = prompt.replace("__NUM_DIGITS__", str(features["num_digits"]))
    prompt = prompt.replace("__NUM_SUBDOMAINS__", str(features["num_subdomains"]))
    prompt = prompt.replace("__CONTENT_SCORE__", str(content_result.get("content_risk_score")))
    prompt = prompt.replace("__CONTENT_FLAGS__", str(content_result.get("flags", [])))
    prompt = prompt.replace("__CONTENT_REASONING__", str(content_result.get("reasoning", "N/A")))

    return prompt


def get_final_verdict(url: str) -> dict:
    """
    Full pipeline: run technical model + content analyzer independently,
    then fuse both into one evidence-backed verdict via LLM reasoning.
    """
    print("  [1/3] Collecting technical signals + scoring with ML model...")
    technical_result = get_technical_verdict(url)

    print("  [2/3] Scraping and analyzing page content...")
    content_result = analyze_url_content(url)

    print("  [3/3] Synthesizing final verdict...")
    prompt = build_fusion_prompt(technical_result, content_result, url)

    client = Groq()
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=500,
        temperature=0,  # deterministic output - critical for reproducible evaluation
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = response.choices[0].message.content.strip()
    raw_text = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        verdict = json.loads(raw_text)
    except json.JSONDecodeError:
        verdict = {
            "final_verdict": "unknown",
            "confidence": 0.0,
            "explanation": f"Failed to parse fusion response as JSON. Raw: {raw_text[:300]}",
        }

    return {
        "url": url,
        "verdict": verdict,
        "technical_risk_score": technical_result["technical_risk_score"],
        "content_risk_score": content_result.get("content_risk_score"),
        "content_flags": content_result.get("flags", []),
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python src/agent/reasoning_agent.py <url>")
        sys.exit(1)

    target_url = sys.argv[1]
    print(f"Running full analysis for: {target_url}\n")

    result = get_final_verdict(target_url)
    print("\n" + "=" * 50)
    print(json.dumps(result, indent=2))