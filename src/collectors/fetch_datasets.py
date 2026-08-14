"""
Phase 1: Data collection.

Pulls three categories of labeled URLs:
  1. Phishing        -> OpenPhish (free feed, no API key needed)
  2. Legitimate       -> Tranco top sites list
  3. Spam/scam (other than phishing) -> hand-labeled, see data/labeled/scam_seed.csv

Run this on your own machine (needs open internet access):
    python src/collectors/fetch_datasets.py
"""

import csv
import io
import zipfile
from pathlib import Path

import requests

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

OPENPHISH_URL = "https://openphish.com/feed.txt"
TRANCO_URL = "https://tranco-list.eu/top-1m.csv.zip"

# How many legit domains to keep (Tranco file has 1M rows, we don't need that many for v1)
TRANCO_SAMPLE_SIZE = 5000


def fetch_openphish() -> list[str]:
    """OpenPhish free feed: plain text, one URL per line, updated every ~12h."""
    print("Fetching OpenPhish feed...")
    resp = requests.get(OPENPHISH_URL, timeout=30)
    resp.raise_for_status()
    urls = [line.strip() for line in resp.text.splitlines() if line.strip()]
    print(f"  -> {len(urls)} phishing URLs")

    out_path = RAW_DIR / "phishing_openphish.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "label"])
        for url in urls:
            writer.writerow([url, "phishing"])
    print(f"  -> saved to {out_path}")
    return urls


def fetch_tranco() -> list[str]:
    """Tranco top sites list: reputable ranking of legitimate domains."""
    print("Fetching Tranco top sites list...")
    resp = requests.get(TRANCO_URL, timeout=60)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        inner_name = zf.namelist()[0]
        with zf.open(inner_name) as f:
            reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8"))
            domains = [row[1] for i, row in enumerate(reader) if i < TRANCO_SAMPLE_SIZE]

    print(f"  -> {len(domains)} legitimate domains")

    out_path = RAW_DIR / "legit_tranco.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "label"])
        for domain in domains:
            writer.writerow([f"https://{domain}", "legit"])
    print(f"  -> saved to {out_path}")
    return domains


def check_scam_seed():
    """
    Spam/scam (non-phishing) sites have no clean public dataset, so this project
    uses a small hand-labeled seed file. See data/labeled/scam_seed.csv for the
    template and instructions on growing it.
    """
    seed_path = RAW_DIR.parent / "labeled" / "scam_seed.csv"
    if seed_path.exists():
        with open(seed_path, encoding="utf-8") as f:
            n = sum(1 for _ in f) - 1  # minus header
        print(f"Scam/spam seed file found: {n} entries at {seed_path}")
    else:
        print(f"No scam seed file yet. Create one at {seed_path} (see template).")


if __name__ == "__main__":
    fetch_openphish()
    fetch_tranco()
    check_scam_seed()
    print("\nDone. Raw data saved in data/raw/")
