import csv
import sys
from pathlib import Path

SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "labeled" / "scam_seed.csv"
VALID_LABELS = {"spam", "scam"}
VALID_CATEGORIES = {"seo_spam", "fake_shop", "content_farm", "fake_reviews", "other"}


def main():
    if len(sys.argv) != 5:
        print("Usage: python add_scam_entry.py <url> <label> <category> <notes>")
        sys.exit(1)

    url, label, category, notes = sys.argv[1:5]

    if label not in VALID_LABELS:
        print(f"Error: label must be one of {VALID_LABELS}, got '{label}'")
        sys.exit(1)
    if category not in VALID_CATEGORIES:
        print(f"Error: category must be one of {VALID_CATEGORIES}, got '{category}'")
        sys.exit(1)

    file_exists = SEED_PATH.exists() and SEED_PATH.stat().st_size > 0

    with open(SEED_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["url", "label", "category", "notes"])
        writer.writerow([url, label, category, notes])

    with open(SEED_PATH, encoding="utf-8") as f:
        n = sum(1 for _ in f) - 1
    print(f"Added. Seed file now has {n} entries.")


if __name__ == "__main__":
    main()