"""
Phase 5: Evaluation harness.

Runs the FULL pipeline (technical model + content analyzer + fusion agent)
across a held-out sample of URLs not used in Phase 3 training, and computes
real precision/recall/F1/false-positive-rate for the whole system - not
just the ML model in isolation.

Saves per-URL results for error analysis, and prints a summary report.

Run:
    python src/eval/run_evaluation.py
"""

import csv
import random
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "agent"))
from reasoning_agent import get_final_verdict

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
TRAINING_FEATURES_PATH = PROCESSED_DIR / "technical_features.csv"
EVAL_OUT_PATH = PROCESSED_DIR / "eval_results.csv"

SAMPLE_SIZE_PER_CLASS = 15  # 15 phishing + 15 legit = 30 total (kept modest: each row costs 2 LLM calls + network)
SLEEP_BETWEEN_REQUESTS = 1.0

RISKY_LABELS = {"phishing", "scam", "spam"}

# A final_verdict of "safe" is predicted-legit; anything else (suspicious,
# likely_scam, likely_phishing) counts as predicted-risky for scoring purposes.
def verdict_to_binary(final_verdict: str) -> int:
    return 0 if final_verdict == "safe" else 1


def load_urls(path: Path) -> list[tuple[str, str]]:
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [(row["url"], row["label"]) for row in reader]


def get_already_used_urls() -> set[str]:
    """URLs already used in Phase 3 training data - excluded here for an honest held-out test."""
    if not TRAINING_FEATURES_PATH.exists():
        return set()
    with open(TRAINING_FEATURES_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["url"] for row in reader}


def build_eval_set() -> list[tuple[str, str]]:
    random.seed(123)  # different seed than training sampling, deliberately

    phishing = load_urls(RAW_DIR / "phishing_openphish.csv")
    legit = load_urls(RAW_DIR / "legit_tranco.csv")
    already_used = get_already_used_urls()

    phishing_unseen = [pair for pair in phishing if pair[0] not in already_used]
    legit_unseen = [pair for pair in legit if pair[0] not in already_used]

    phishing_sample = random.sample(phishing_unseen, min(SAMPLE_SIZE_PER_CLASS, len(phishing_unseen)))
    legit_sample = random.sample(legit_unseen, min(SAMPLE_SIZE_PER_CLASS, len(legit_unseen)))

    combined = phishing_sample + legit_sample
    random.shuffle(combined)
    return combined


def run_evaluation():
    eval_set = build_eval_set()
    print(f"Evaluating on {len(eval_set)} held-out URLs (not seen during Phase 3 training).\n")

    results = []

    for i, (url, true_label) in enumerate(eval_set, start=1):
        print(f"[{i}/{len(eval_set)}] {true_label:10s} {url[:60]}")
        true_binary = 1 if true_label in RISKY_LABELS else 0

        try:
            result = get_final_verdict(url)
            verdict = result["verdict"].get("final_verdict", "unknown")
            confidence = result["verdict"].get("confidence")
            predicted_binary = verdict_to_binary(verdict)

            results.append({
                "url": url,
                "true_label": true_label,
                "true_binary": true_binary,
                "predicted_verdict": verdict,
                "predicted_binary": predicted_binary,
                "confidence": confidence,
                "technical_risk_score": result["technical_risk_score"],
                "content_risk_score": result["content_risk_score"],
                "correct": int(true_binary == predicted_binary),
                "error": "",
            })
            print(f"    -> predicted: {verdict} (correct: {true_binary == predicted_binary})")

        except Exception as e:
            results.append({
                "url": url, "true_label": true_label, "true_binary": true_binary,
                "predicted_verdict": "error", "predicted_binary": None, "confidence": None,
                "technical_risk_score": None, "content_risk_score": None,
                "correct": 0, "error": str(e),
            })
            print(f"    -> ERROR: {e}")

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    # save raw results
    with open(EVAL_OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"\nRaw results saved to {EVAL_OUT_PATH}")

    print_summary(results)


def print_summary(results: list[dict]):
    valid = [r for r in results if r["predicted_binary"] is not None]
    errors = [r for r in results if r["predicted_binary"] is None]

    tp = sum(1 for r in valid if r["true_binary"] == 1 and r["predicted_binary"] == 1)
    tn = sum(1 for r in valid if r["true_binary"] == 0 and r["predicted_binary"] == 0)
    fp = sum(1 for r in valid if r["true_binary"] == 0 and r["predicted_binary"] == 1)
    fn = sum(1 for r in valid if r["true_binary"] == 1 and r["predicted_binary"] == 0)

    accuracy = (tp + tn) / len(valid) if valid else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    false_positive_rate = fp / (fp + tn) if (fp + tn) > 0 else 0

    print("\n" + "=" * 50)
    print("EVALUATION SUMMARY (full fused pipeline)")
    print("=" * 50)
    print(f"Total evaluated: {len(results)}  (errors/skipped: {len(errors)})")
    print()
    print("Confusion Matrix:")
    print("                 Predicted Legit  Predicted Risky")
    print(f"Actual Legit          {tn:>6}          {fp:>6}")
    print(f"Actual Risky          {fn:>6}          {tp:>6}")
    print()
    print(f"Accuracy:             {accuracy:.3f}")
    print(f"Precision (risky):    {precision:.3f}")
    print(f"Recall (risky):       {recall:.3f}")
    print(f"F1 Score:             {f1:.3f}")
    print(f"False Positive Rate:  {false_positive_rate:.3f}  <- legit sites incorrectly flagged")


if __name__ == "__main__":
    run_evaluation()