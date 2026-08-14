"""
Phase 2c: Batch dataset builder.

Runs feature_extraction.py across a sample of URLs from each labeled source
(phishing, legit, scam/spam) and saves one combined CSV — this becomes the
actual training data for the Phase 3 ML model.

Writes progress incrementally (one row at a time), so if this gets
interrupted partway through, you don't lose everything already processed.

Run:
    python src/collectors/build_dataset.py
"""

import csv
import random
import time
from pathlib import Path

from feature_extraction import extract_features_from_url

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
LABELED_DIR = Path(__file__).resolve().parents[2] / "data" / "labeled"
OUT_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "technical_features.csv"

SAMPLE_SIZE_PER_SOURCE = 200  # phishing and legit each capped at this
SLEEP_BETWEEN_REQUESTS = 0.5  # seconds, be polite to WHOIS/DNS servers

FEATURE_COLUMNS = [
    "url", "label",
    "domain_age_days", "domain_age_missing",
    "has_valid_ssl", "ssl_self_signed_like", "is_reachable",
    "redirect_count", "unique_domains_in_chain",
    "domain_length", "num_hyphens", "num_digits", "num_subdomains", "uses_https",
]


def load_urls(path: Path, label_column: str = "label") -> list[tuple[str, str]]:
    """Read a CSV with url,label columns into a list of (url, label) tuples."""
    if not path.exists():
        print(f"  Warning: {path} not found, skipping.")
        return []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [(row["url"], row[label_column]) for row in reader]


def sample(items: list, n: int) -> list:
    if len(items) <= n:
        return items
    return random.sample(items, n)


def build_dataset():
    random.seed(42)  # reproducible sampling

    print("Loading source URL lists...")
    phishing = load_urls(RAW_DIR / "phishing_openphish.csv")
    legit = load_urls(RAW_DIR / "legit_tranco.csv")
    scam = load_urls(LABELED_DIR / "scam_seed.csv")  # uses all entries, no cap

    phishing_sample = sample(phishing, SAMPLE_SIZE_PER_SOURCE)
    legit_sample = sample(legit, SAMPLE_SIZE_PER_SOURCE)

    all_targets = phishing_sample + legit_sample + scam
    random.shuffle(all_targets)

    print(f"  Phishing: {len(phishing_sample)} (of {len(phishing)} available)")
    print(f"  Legit:    {len(legit_sample)} (of {len(legit)} available)")
    print(f"  Scam/spam (hand-labeled): {len(scam)}")
    print(f"  Total to process: {len(all_targets)}\n")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Resume support: if the output file already exists, skip URLs already done
    already_done = set()
    file_exists = OUT_PATH.exists() and OUT_PATH.stat().st_size > 0
    if file_exists:
        with open(OUT_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            already_done = {row["url"] for row in reader}
        print(f"Found existing output with {len(already_done)} rows already done — resuming.\n")

    success_count = 0
    error_count = 0

    with open(OUT_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FEATURE_COLUMNS)
        if not file_exists:
            writer.writeheader()

        for i, (url, label) in enumerate(all_targets, start=1):
            if url in already_done:
                continue

            try:
                features = extract_features_from_url(url)
                features["label"] = label
                writer.writerow(features)
                f.flush()  # write to disk immediately, don't lose progress on crash
                success_count += 1
                status = "OK"
            except Exception as e:
                error_count += 1
                status = f"FAILED ({e})"

            print(f"[{i}/{len(all_targets)}] {label:10s} {url[:60]:60s} {status}")
            time.sleep(SLEEP_BETWEEN_REQUESTS)

    print(f"\nDone. {success_count} succeeded, {error_count} failed.")
    print(f"Saved to {OUT_PATH}")


if __name__ == "__main__":
    build_dataset()