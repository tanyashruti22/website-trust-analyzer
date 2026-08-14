"""
Phase 2a: Technical signal collector.

Given a URL, gathers "hard" technical facts that are hard for a scammer to fake
quickly:
  - Domain age (via WHOIS) — scam/phishing domains are usually very new
  - SSL certificate info — self-signed or very new certs are a red flag
  - Redirect chain — excessive redirects across domains is suspicious

Run standalone for testing:
    python src/collectors/technical_signals.py https://example.com
"""

import socket
import ssl
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
import whois  # from python-whois package


def get_domain(url: str) -> str:
    """Extract just the domain from a full URL, e.g. https://a.b.com/x -> b.com"""
    parsed = urlparse(url)
    return parsed.netloc or parsed.path  # handles URLs typed without scheme


def get_domain_age_days(domain: str) -> dict:
    """
    Look up WHOIS registration data for a domain.
    Returns dict with age_days (None if lookup failed) and raw creation_date.
    """
    try:
        w = whois.whois(domain)
        creation_date = w.creation_date

        # whois library sometimes returns a list of dates instead of one
        if isinstance(creation_date, list):
            creation_date = creation_date[0]

        if creation_date is None:
            return {"age_days": None, "creation_date": None, "error": "no creation_date in WHOIS record"}

        # normalize timezone so subtraction works
        if creation_date.tzinfo is None:
            creation_date = creation_date.replace(tzinfo=timezone.utc)

        age_days = (datetime.now(timezone.utc) - creation_date).days
        return {"age_days": age_days, "creation_date": str(creation_date), "error": None}

    except Exception as e:
        return {"age_days": None, "creation_date": None, "error": str(e)}


def get_ssl_info(domain: str, port: int = 443, timeout: int = 8) -> dict:
    """
    Connect to the domain over HTTPS and inspect its SSL certificate.
    Returns issuer, validity dates, and whether it looks self-signed.
    """
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()

        issuer = dict(x[0] for x in cert.get("issuer", []))
        subject = dict(x[0] for x in cert.get("subject", []))
        not_before = cert.get("notBefore")
        not_after = cert.get("notAfter")

        # self-signed heuristic: issuer organization == subject organization
        is_self_signed_like = issuer.get("organizationName") == subject.get("organizationName")

        return {
            "has_valid_ssl": True,
            "issuer": issuer.get("organizationName", "Unknown"),
            "valid_from": not_before,
            "valid_until": not_after,
            "self_signed_like": is_self_signed_like,
            "error": None,
        }
    except Exception as e:
        return {
            "has_valid_ssl": False,
            "issuer": None,
            "valid_from": None,
            "valid_until": None,
            "self_signed_like": None,
            "error": str(e),
        }


def get_redirect_chain(url: str, timeout: int = 10) -> dict:
    """
    Follow redirects and record the chain. Excessive redirects, or redirects
    across many different domains, are a common spam/scam pattern.

    Uses a realistic browser User-Agent - without one, many legitimate sites'
    bot-protection systems (Cloudflare, Akamai, etc.) silently block or reject
    the request, making a perfectly reachable site falsely appear "unreachable".
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True, headers=headers)
        chain = [r.url for r in resp.history] + [resp.url]
        domains_in_chain = {urlparse(u).netloc for u in chain}

        return {
            "final_url": resp.url,
            "redirect_count": len(resp.history),
            "chain": chain,
            "unique_domains_in_chain": len(domains_in_chain),
            "status_code": resp.status_code,
            "error": None,
        }
    except Exception as e:
        return {
            "final_url": None,
            "redirect_count": None,
            "chain": [],
            "unique_domains_in_chain": None,
            "status_code": None,
            "error": str(e),
        }

def collect_technical_signals(url: str) -> dict:
    """Run all technical checks for a URL and return one combined dict."""
    domain = get_domain(url)
    return {
        "url": url,
        "domain": domain,
        "whois": get_domain_age_days(domain),
        "ssl": get_ssl_info(domain),
        "redirects": get_redirect_chain(url),
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python src/collectors/technical_signals.py <url>")
        sys.exit(1)

    target_url = sys.argv[1]
    print(f"Collecting technical signals for: {target_url}\n")

    result = collect_technical_signals(target_url)

    import json
    print(json.dumps(result, indent=2, default=str))