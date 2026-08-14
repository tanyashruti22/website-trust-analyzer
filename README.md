# 🕵️ Website Trust Analyzer

A multi-signal system that classifies a website as safe / suspicious / likely
scam / likely phishing — combining a custom-trained ML model on technical
signals with LLM-based content analysis, fused into one evidence-backed
verdict with a plain-English explanation.

**Live demo:** _[add your deployed URL here once live]_

## Why this exists

Most spam/phishing detectors give you a black-box score with no explanation.
This project instead combines two independent detection systems and asks an
LLM to synthesize them into a verdict that cites specific, real evidence —
closer to how a human security analyst would explain a decision.

## Architecture

```
URL input
   |
   +--> Technical Signal Collector (WHOIS, SSL, DNS, redirects, domain structure)
   |         |
   |         v
   |    XGBoost model (trained from scratch on ~400 labeled sites)
   |         |
   |         v
   |    technical_risk_score
   |
   +--> Content Collector (lightweight HTTP scrape)
   |         |
   |         v
   |    LLM content analyzer (Llama 3.3 70B via Groq) -> content_risk_score + flags
   |
   +--> Fusion Reasoning Agent (LLM)
              synthesizes both signals + raw evidence into:
              final_verdict, confidence, evidence-backed explanation
```

## What's genuinely custom vs. what uses an API

Being precise about this on purpose:

- **The ML model (technical signals) is trained from scratch** on a
  self-built, labeled dataset (OpenPhish phishing feed + Tranco top-sites
  list + hand-labeled scam/spam examples). Real feature engineering, real
  train/test split, real evaluated metrics — no API involved in this layer.
- **The content analysis and fusion reasoning use an LLM (Llama 3.3 70B via
  Groq's free API)** rather than a custom-trained language model — building
  a production system *on top of* a foundation model, including prompt
  design, structured output, and multi-signal reasoning, is itself the core
  skill this layer demonstrates.

## Results

Evaluated on 30 held-out URLs never seen during training:

| Metric | Score |
|---|---|
| Accuracy | 80.0% |
| Recall (catching phishing/scam) | 100% |
| Precision | 71.4% |
| False Positive Rate | 40% |

See [`data/processed/LIMITATIONS.md`](data/processed/LIMITATIONS.md) for a
full, honest log of 8 real bugs found and fixed during development — dataset
artifacts, LLM reasoning errors, and how each was diagnosed and verified.

## Tech stack

- **ML:** scikit-learn, XGBoost, pandas
- **LLM:** Groq API (Llama 3.3 70B), prompt engineering for structured JSON output
- **Signal collection:** python-whois, requests, BeautifulSoup
- **Interface:** Streamlit
- **Data sources:** OpenPhish (phishing feed), Tranco (top sites list), hand-labeled scam/spam set

## Project structure

```
src/
├── collectors/       # WHOIS/SSL/redirect signals, content scraping, feature extraction
├── models/           # ML training script + saved trained model
├── agent/            # LLM content analyzer + fusion reasoning agent
├── eval/             # Evaluation harness against held-out data
└── interface/         # Streamlit web app + result caching
data/
├── raw/              # Downloaded phishing/legit URL lists
├── labeled/          # Hand-labeled scam/spam dataset
└── processed/        # Training features, eval results, LIMITATIONS.md
```

## Running it locally

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# add your own free Groq API key to a .env file:
# GROQ_API_KEY=your-key-here

streamlit run src/interface/app.py
```

## Known limitations

This project's dataset and model have known, documented weaknesses (e.g. the
"legit" training sample skews toward large popular domains, which doesn't
fully generalize). Full write-up with root-cause analysis for each:
[`data/processed/LIMITATIONS.md`](data/processed/LIMITATIONS.md).

## What I'd build next

- Grow the hand-labeled scam/spam dataset beyond the current small seed set
- Multi-category verdicts (distinguish phishing vs. scam vs. spam, not just binary risky/safe)
- Automated test suite for the feature extraction and prompt-building logic
- Retrain the technical model on a more diverse "legit" sample to reduce the documented false-positive patterns