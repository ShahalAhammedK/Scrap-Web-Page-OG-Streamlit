"""
Social Media Info Fetcher — Streamlit edition.

This replaces the original Flask app (app.py + templates/index.html) with a
single Streamlit UI. All of the scraping logic in the `scrapers/` package is
reused unchanged.

Run locally:
    pip install -r requirements.txt
    streamlit run streamlit_app.py

Deploy on Streamlit Community Cloud:
    Push this folder to GitHub, point Streamlit Cloud at `streamlit_app.py`,
    and add your RapidAPI keys under Settings -> Secrets (see
    .streamlit/secrets.toml.example).
"""

import io
import os
import traceback

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# 1. Make API keys available as environment variables BEFORE importing the
#    scrapers package. `scrapers/api_key_manager.py` reads RAPIDAPI_KEY_* from
#    os.environ at import time, so secrets have to be in place first.
# ---------------------------------------------------------------------------
load_dotenv()  # picks up a local .env if present

# Pull anything that looks like a RapidAPI key out of st.secrets and push it
# into the environment so the existing key manager keeps working untouched.
try:
    for _key, _val in st.secrets.items():
        if _key.upper().startswith("RAPIDAPI_KEY"):
            os.environ[_key] = str(_val)
except Exception:
    # No secrets.toml configured (e.g. running purely off .env) — that's fine.
    pass

# ---------------------------------------------------------------------------
# 2. Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Social Media Info Fetcher",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------------------------
# 3. Import the scrapers. The key manager raises if no keys are configured, so
#    we import lazily and surface a friendly message instead of a stack trace.
# ---------------------------------------------------------------------------
SCRAPERS = None
IMPORT_ERROR = None
try:
    from scrapers import (
        fetch_instagram_post_info,
        fetch_instagram_profile_info,
        fetch_instagram_hashtag_media,
        fetch_tiktok_post_info,
        fetch_tiktok_profile_info,
        fetch_youtube_post_info,
        fetch_youtube_profile_info,
        fetch_snapchat_profile_info,
    )

    SCRAPERS = {
        "instagram_post": fetch_instagram_post_info,
        "instagram_profile": fetch_instagram_profile_info,
        "instagram_hashtag": fetch_instagram_hashtag_media,
        "tiktok_post": fetch_tiktok_post_info,
        "tiktok_profile": fetch_tiktok_profile_info,
        "youtube_post": fetch_youtube_post_info,
        "youtube_profile": fetch_youtube_profile_info,
        "snapchat_profile": fetch_snapchat_profile_info,
    }
except Exception as exc:  # noqa: BLE001
    IMPORT_ERROR = str(exc)

# Human-friendly labels for the dropdown, grouped like the original optgroups.
INFO_TYPES = {
    "Instagram — Post Info": "instagram_post",
    "Instagram — Profile Info": "instagram_profile",
    "Instagram — Hashtag Media": "instagram_hashtag",
    "TikTok — Post Info": "tiktok_post",
    "TikTok — Profile Info": "tiktok_profile",
    "YouTube — Post Info": "youtube_post",
    "YouTube — Profile Info": "youtube_profile",
    "Snapchat — Profile Info": "snapchat_profile",
}

# Per-type hint for the input box.
PLACEHOLDERS = {
    "instagram_post": "Post/Reel URL or shortcode  (e.g. https://www.instagram.com/p/ABC123/)",
    "instagram_profile": "Username or profile URL  (e.g. vivo_global)",
    "instagram_hashtag": "Hashtag without the #  (e.g. honor400)",
    "tiktok_post": "TikTok video URL",
    "tiktok_profile": "Username or profile URL  (e.g. @vivo.global)",
    "youtube_post": "YouTube video URL",
    "youtube_profile": "Channel URL, @handle, or channel ID",
    "snapchat_profile": "Username or profile URL",
}


# ---------------------------------------------------------------------------
# 4. Core fetch routine — mirrors the logic from the old /api/fetch-info route.
# ---------------------------------------------------------------------------
def fetch_all(info_type: str, identifiers: list[str]):
    """Run the appropriate scraper for each identifier and collect results.

    Returns (results, warning) where results is a list of dicts and warning is
    a string (or None) when at least one identifier failed.
    """
    fetch_fn = SCRAPERS[info_type]
    platform = info_type.split("_")[0].capitalize()

    results: list[dict] = []
    had_error = False

    progress = st.progress(0.0, text="Starting…")
    total = len(identifiers)

    for i, identifier in enumerate(identifiers, start=1):
        progress.progress(i / total, text=f"Fetching {i}/{total}: {identifier}")
        try:
            if info_type == "instagram_hashtag":
                # This scraper returns a LIST of posts (or a dict with "error").
                posts = fetch_fn(identifier)
                if isinstance(posts, list) and posts:
                    results.extend(posts)
                elif isinstance(posts, dict) and posts.get("error"):
                    had_error = True
                    results.append(_error_record(identifier, posts["error"], platform))
                else:
                    had_error = True
                    results.append(
                        _error_record(
                            identifier,
                            "No data or unexpected format from the Hashtag Media API.",
                            platform,
                        )
                    )
                continue

            info = fetch_fn(identifier)
            if isinstance(info, dict) and not info.get("error"):
                results.append(info)
            elif isinstance(info, dict) and info.get("error"):
                had_error = True
                results.append(_error_record(identifier, info["error"], platform))
            else:
                had_error = True
                results.append(
                    _error_record(identifier, "No data returned.", platform)
                )

        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            had_error = True
            results.append(
                _error_record(
                    identifier,
                    f"Unexpected error: {exc}",
                    platform,
                )
            )

    progress.empty()

    warning = None
    if had_error and any("Error Details" not in r for r in results):
        warning = (
            "Some identifiers failed. Check the 'Status' / 'Error Details' "
            "columns for the affected rows."
        )
    elif had_error:
        warning = "All identifiers failed. Check your inputs and API keys."

    return results, warning


def _error_record(identifier: str, message: str, platform: str) -> dict:
    return {
        "Requested Identifier": identifier,
        "Status": "Failed",
        "Error Details": message,
        "Platform": platform,
    }


# ---------------------------------------------------------------------------
# 5. UI
# ---------------------------------------------------------------------------
# Optional logo (kept from the original static/ folder).
_logo = "static/Vivo_(technology_company)-Logo.wine (1).png"
col_logo, col_title = st.columns([1, 6])
with col_logo:
    if os.path.exists(_logo):
        st.image(_logo, width=90)
with col_title:
    st.title("Social Media Info Fetcher")
    st.caption("Instagram · TikTok · YouTube · Snapchat — powered by your RapidAPI keys")

# Hard stop if scrapers couldn't import (almost always missing API keys).
if SCRAPERS is None:
    st.error(
        "Couldn't start the scrapers.\n\n"
        f"**Details:** {IMPORT_ERROR}\n\n"
        "Add your RapidAPI keys before running. Locally, put them in a `.env` "
        "file as `RAPIDAPI_KEY_1=...`, `RAPIDAPI_KEY_2=...`. On Streamlit Cloud, "
        "add them under **Settings → Secrets** (see "
        "`.streamlit/secrets.toml.example`)."
    )
    st.stop()

with st.sidebar:
    st.header("Settings")
    label = st.selectbox("Info type", list(INFO_TYPES.keys()))
    info_type = INFO_TYPES[label]
    st.markdown(
        "**Input mode**\n\nPaste one identifier per line below, then click "
        "**Get Info**."
    )
    n_keys = sum(1 for k in os.environ if k.upper().startswith("RAPIDAPI_KEY"))
    st.success(f"{n_keys} RapidAPI key(s) loaded")

st.subheader(label)
raw = st.text_area(
    "Identifiers (one per line)",
    height=180,
    placeholder=PLACEHOLDERS.get(info_type, "Enter identifiers, one per line"),
)

go = st.button("Get Info", type="primary")

# Keep last results in session so the download button survives reruns.
if "results" not in st.session_state:
    st.session_state.results = None
    st.session_state.warning = None

if go:
    identifiers = [line.strip() for line in raw.splitlines() if line.strip()]
    if not identifiers:
        st.warning("Please enter at least one identifier.")
    else:
        with st.spinner("Fetching…"):
            results, warning = fetch_all(info_type, identifiers)
        st.session_state.results = results
        st.session_state.warning = warning

# ---------------------------------------------------------------------------
# 6. Results
# ---------------------------------------------------------------------------
results = st.session_state.results
if results:
    if st.session_state.warning:
        st.warning(st.session_state.warning)

    df = pd.DataFrame(results)
    st.success(f"{len(df)} record(s) fetched.")
    st.dataframe(df, use_container_width=True)

    csv_buf = io.StringIO()
    df.to_csv(csv_buf, index=False)
    st.download_button(
        "Download as CSV",
        data=csv_buf.getvalue(),
        file_name="social_media_info.csv",
        mime="text/csv",
    )
elif results == []:
    st.info("No data could be fetched for the provided identifiers.")
else:
    st.info("Pick an info type, paste identifiers, and click **Get Info**.")
