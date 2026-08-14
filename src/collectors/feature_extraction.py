"""
Phase 2b: Feature extraction.

Converts the raw, messy JSON output of technical_signals.py into a clean,
flat dictionary of NUMBERS - this is the actual input format a machine
learning model needs (Phase 3 will train on rows of these).

Key idea: missing/failed data is itself informative (e.g. "domain doesn't
resolve" is a red flag, not just a gap), so we encode "missingness" as its
own feature rather than silently dropping it.
"""

from urllib.parse import urlparse

from technical_signals import collect_technical_signals


def extract_features(raw_signals: dict) -> dict:
    """
    Take the dict returned by collect_technical_signals() and flatten it
    into ML-ready numeric features.

    Convention used throughout:
      - boolean signals -> 0 / 1
      - "we couldn't find this out" -> a *_missing flag set to 1, and the
        underlying value set to a safe default (0 or -1), so the model can
        learn "missing data on this domain is itself suspicious" if that
        pattern exists in the training data.
    """
    domain = raw_signals["domain"]
    whois_data = raw_signals["whois"]
    ssl_data = raw_signals["ssl"]
    redirect_data = raw_signals["redirects"]

    features = {}

    # --- WHOIS / domain age features ---
    if whois_data["age_days"] is not None:
        features["domain_age_days"] = whois_data["age_days"]
        features["domain_age_missing"] = 0
    else:
        features["domain_age_days"] = -1  # sentinel: unknown
        features["domain_age_missing"] = 1

    # --- SSL features ---
    features["has_valid_ssl"] = 1 if ssl_data["has_valid_ssl"] else 0
    features["ssl_self_signed_like"] = 1 if ssl_data.get("self_signed_like") else 0

    # --- Reachability: could we even connect? (this itself is a strong signal) ---
    # If both SSL and redirect checks errored out, the site is very likely dead/unreachable.
    ssl_failed = ssl_data["error"] is not None
    redirect_failed = redirect_data["error"] is not None
    features["is_reachable"] = 0 if (ssl_failed and redirect_failed) else 1

    # --- Redirect features ---
    if redirect_data["redirect_count"] is not None:
        features["redirect_count"] = redirect_data["redirect_count"]
        features["unique_domains_in_chain"] = redirect_data["unique_domains_in_chain"]
    else:
        features["redirect_count"] = -1
        features["unique_domains_in_chain"] = -1

    # --- Cheap lexical/structural features of the domain itself ---
    # These are common, well-documented phishing heuristics: scam domains often
    # cram in extra hyphens, digits, and subdomains to mimic a brand name.
    hostname = urlparse(raw_signals["url"]).hostname or domain
    features["domain_length"] = len(hostname)
    features["num_hyphens"] = hostname.count("-")
    features["num_digits"] = sum(c.isdigit() for c in hostname)
    features["num_subdomains"] = max(hostname.count(".") - 1, 0)  # e.g. a.b.example.com -> 2
    features["uses_https"] = 1 if raw_signals["url"].startswith("https://") else 0

    return features


def extract_features_from_url(url: str) -> dict:
    """Convenience wrapper: collect signals AND extract features in one call."""
    raw = collect_technical_signals(url)
    features = extract_features(raw)
    features["url"] = url  # keep url attached for traceability in the dataset
    return features


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 2:
        print("Usage: python src/collectors/feature_extraction.py <url>")
        sys.exit(1)

    result = extract_features_from_url(sys.argv[1])
    print(json.dumps(result, indent=2, default=str))