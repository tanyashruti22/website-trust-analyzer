"""
Phase 3: Train the ML model on technical signals.

Loads data/processed/technical_features.csv, trains an XGBoost binary
classifier (legit vs risky), evaluates it, and saves the trained model.

Run:
    python src/models/train_technical_model.py
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "technical_features.csv"
MODEL_OUT_PATH = Path(__file__).resolve().parents[2] / "src" / "models" / "technical_model.joblib"

FEATURE_COLUMNS = [
    "domain_age_days", "domain_age_missing",
    "has_valid_ssl", "ssl_self_signed_like", "is_reachable",
    "redirect_count", "unique_domains_in_chain",
    "domain_length", "num_hyphens", "num_digits", "num_subdomains", "uses_https",
]

# Simplification for v1: collapse phishing/scam/spam into one "risky" class.
# Rationale: with ~400 total rows, splitting into 4 fine-grained classes leaves
# too few examples per class to learn from reliably. Binary is also the more
# realistic MVP question: "is this safe or not."
RISKY_LABELS = {"phishing", "scam", "spam"}


def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    df["target"] = df["label"].apply(lambda x: 1 if x in RISKY_LABELS else 0)
    return df


def train_and_evaluate():
    df = load_data()
    print(f"Loaded {len(df)} rows.")
    print(f"Class balance:\n{df['target'].value_counts()}\n")
    print("  (target: 1 = risky [phishing/scam/spam], 0 = legit)\n")

    X = df[FEATURE_COLUMNS]
    y = df["target"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Train set: {len(X_train)} rows, Test set: {len(X_test)} rows\n")

    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    print("=" * 50)
    print("EVALUATION RESULTS")
    print("=" * 50)
    print(f"Accuracy:  {accuracy_score(y_test, y_pred):.3f}")
    print(f"Precision: {precision_score(y_test, y_pred):.3f}")
    print(f"Recall:    {recall_score(y_test, y_pred):.3f}")
    print(f"F1 Score:  {f1_score(y_test, y_pred):.3f}")
    print()
    print("Confusion Matrix:")
    print("                 Predicted Legit  Predicted Risky")
    cm = confusion_matrix(y_test, y_pred)
    print(f"Actual Legit          {cm[0][0]:>6}          {cm[0][1]:>6}")
    print(f"Actual Risky          {cm[1][0]:>6}          {cm[1][1]:>6}")
    print()
    print("Full classification report:")
    print(classification_report(y_test, y_pred, target_names=["legit", "risky"]))

    print("Feature importance (what the model relies on most):")
    importances = sorted(
        zip(FEATURE_COLUMNS, model.feature_importances_),
        key=lambda x: x[1], reverse=True,
    )
    for name, score in importances:
        print(f"  {name:30s} {score:.3f}")

    MODEL_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_OUT_PATH)
    print(f"\nModel saved to {MODEL_OUT_PATH}")


if __name__ == "__main__":
    train_and_evaluate()