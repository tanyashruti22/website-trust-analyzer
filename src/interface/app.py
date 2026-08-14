"""
Phase 6: Streamlit interface (playful theme).

A simple web app: paste a URL, see the full verdict with evidence - this is
what makes the project demo-able to anyone, not just runnable from a terminal.

Includes result caching (avoids re-running the pipeline for repeat URLs -
important once multiple people share one API quota) and graceful handling
of rate-limit errors from the free-tier LLM API.

Run:
    streamlit run src/interface/app.py
"""

import sys
from pathlib import Path

import streamlit as st
from groq import RateLimitError

# make sibling modules importable regardless of where streamlit is launched from
sys.path.append(str(Path(__file__).resolve().parents[1] / "agent"))
sys.path.append(str(Path(__file__).resolve().parents[1] / "collectors"))

from reasoning_agent import get_final_verdict
from cache import get_cached, set_cached

st.set_page_config(page_title="Website Trust Analyzer", page_icon="🕵️", layout="centered")

VERDICT_STYLES = {
    "safe": {
        "color": "#059669", "bg": "linear-gradient(135deg, #d1fae5, #a7f3d0)",
        "emoji": "✅", "label": "Looking Good!", "sub": "This site seems totally legit 🎉",
    },
    "suspicious": {
        "color": "#d97706", "bg": "linear-gradient(135deg, #fef3c7, #fde68a)",
        "emoji": "🤔", "label": "Hmm, Sketchy...", "sub": "A few things don't quite add up",
    },
    "likely_scam": {
        "color": "#e11d48", "bg": "linear-gradient(135deg, #fecdd3, #fda4af)",
        "emoji": "🚨", "label": "Scam Alert!", "sub": "This one's giving major red flags",
    },
    "likely_phishing": {
        "color": "#e11d48", "bg": "linear-gradient(135deg, #fecdd3, #fda4af)",
        "emoji": "🎣", "label": "Phishing Alert!", "sub": "Looks like it's fishing for your info",
    },
    "unknown": {
        "color": "#6b7280", "bg": "linear-gradient(135deg, #f3f4f6, #e5e7eb)",
        "emoji": "❓", "label": "Not Sure...", "sub": "Couldn't quite figure this one out",
    },
}

# --- playful custom styling ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Nunito:wght@400;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Nunito', sans-serif; }

    .stApp {
        background: linear-gradient(160deg, #fdf4ff 0%, #fce7f3 45%, #fef3c7 100%);
        background-attachment: fixed;
    }

    header[data-testid="stHeader"] {
        background: transparent;
    }

    .main > div { padding-top: 1.5rem; }
    .big-title {
        font-family: 'Fredoka', sans-serif;
        font-size: 42px;
        background: linear-gradient(135deg, #8b5cf6, #ec4899, #f59e0b);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }

    .verdict-card {
        border-radius: 28px;
        padding: 28px 32px;
        margin: 20px 0;
        box-shadow: 0 8px 24px rgba(139, 92, 246, 0.15);
        border: 3px solid rgba(255,255,255,0.6);
    }

    div.stButton > button {
        border-radius: 999px !important;
        font-weight: 700 !important;
        border: none !important;
        transition: transform 0.15s ease;
    }
    div.stButton > button:hover { transform: scale(1.04); }

    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #8b5cf6, #ec4899) !important;
        color: white !important;
        font-size: 17px !important;
        padding: 10px 0 !important;
    }

    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #f3e8ff, #fce7f3);
        border-radius: 18px;
        padding: 14px;
        border: 2px solid #e9d5ff;
    }

    div[data-testid="stTextInput"] input {
        border-radius: 999px !important;
        padding: 12px 20px !important;
        border: 2px solid #ddd6fe !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- header ---
st.markdown(
    "<p class='big-title'>🕵️ Website Trust Analyzer</p>"
    "<p style='color:#7c3aed; font-size:16px; margin-top:2px; font-weight:600;'>"
    "Paste any link and let's find out if it's the real deal 🔍✨"
    "</p>",
    unsafe_allow_html=True,
)

# --- input area ---
if "url_input" not in st.session_state:
    st.session_state.url_input = ""

st.markdown("**✨ Or try one of these:**")
col_a, col_b, col_c = st.columns(3)
example_urls = ["github.com", "paypal.com", "wikipedia.org"]
for col, example in zip([col_a, col_b, col_c], example_urls):
    if col.button(f"🔗 {example}", use_container_width=True):
        st.session_state.url_input = example

url = st.text_input(
    "URL",
    placeholder="🌐 Paste a URL here, e.g. https://example.com",
    label_visibility="collapsed",
    key="url_input",
)
analyze_clicked = st.button("🔎 Let's Check It!", type="primary", use_container_width=True)

if analyze_clicked and url:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url  # be forgiving if someone forgets the scheme

    cached_result = get_cached(url)

    if cached_result:
        result = cached_result
        st.caption("⚡ Served from cache — we checked this one recently!")
    else:
        with st.status("🕵️ Investigating...", expanded=True) as status:
            st.write("🔬 Sniffing out domain age, SSL, redirects...")
            st.write("📄 Reading through the page content...")
            st.write("🧠 Putting it all together...")

            try:
                result = get_final_verdict(url)
                set_cached(url, result)
                status.update(label="🎉 Done!", state="complete", expanded=False)

            except RateLimitError:
                status.update(label="😴 Taking a quick nap", state="error")
                st.warning(
                    "⏳ **We've used up today's free checks!** "
                    "This app runs on a free-tier API with a shared daily limit. "
                    "Please try again a little later, or come back tomorrow. Thanks for being patient! 💜"
                )
                st.stop()

            except Exception as e:
                status.update(label="😬 Oops, something broke", state="error")
                st.error(f"Something went wrong analyzing this URL: {e}")
                st.stop()

    verdict_key = result["verdict"].get("final_verdict", "unknown")
    style = VERDICT_STYLES.get(verdict_key, VERDICT_STYLES["unknown"])
    confidence = result["verdict"].get("confidence", 0) or 0
    explanation = result["verdict"].get("explanation", "No explanation available.")

    # --- main verdict card ---

    # --- main verdict card ---
    st.markdown(
        f"""
        <div class="verdict-card" style="background:{style['bg']};">
            <div style="display:flex; align-items:center; justify-content:space-between;">
                <div>
                    <h2 style="color: {style['color']}; margin: 0; font-family:'Fredoka',sans-serif;">
                        {style['emoji']} {style['label']}
                    </h2>
                    <p style="margin:2px 0 0 0; color:{style['color']}; font-weight:600; opacity:0.85;">
                        {style['sub']}
                    </p>
                </div>
                <span style="background:{style['color']}; color:white; padding:6px 16px; border-radius:999px; font-size:13px; font-weight:700; white-space:nowrap;">
                    {confidence:.0%} sure
                </span>
            </div>
            <p style="margin: 16px 0 0 0; font-size: 15px; line-height: 1.6; color:#374151; background:rgba(255,255,255,0.5); padding:14px; border-radius:16px;">
                {explanation}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- evidence breakdown ---
    col1, col2 = st.columns(2)
    with col1:
        tech_score = result["technical_risk_score"]
        st.metric("🔧 Technical Risk", f"{tech_score:.2f}" if tech_score is not None else "N/A")
    with col2:
        content_score = result["content_risk_score"]
        st.metric("📄 Content Risk", f"{content_score:.2f}" if content_score is not None else "N/A")

    if result.get("content_flags"):
        st.markdown("**🚩 Flags we spotted:**")
        for flag in result["content_flags"]:
            st.write(f"- {flag}")

    with st.expander("🔬 See the full evidence (raw data)"):
        st.json(result)

elif analyze_clicked and not url:
    st.warning("👀 Don't forget to paste a URL first!")

st.divider()
st.caption(
    "🎓 Built as an AI Engineer portfolio project — combines an XGBoost model on "
    "technical signals with LLM-based content analysis and reasoning, fused into "
    "one evidence-backed verdict. Runs on a free-tier API with a shared daily "
    "quota, so thanks for your patience if it's ever busy! 💜"
)