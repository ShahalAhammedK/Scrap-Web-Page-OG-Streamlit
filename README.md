# Social Media Info Fetcher (Streamlit)

Fetches Instagram / TikTok / YouTube / Snapchat info via RapidAPI, with
automatic key rotation.

## Files
- `app.py`          — the Streamlit app. **This is what Streamlit Cloud runs.**
- `streamlit_app.py`— identical copy (works if your main file is set to this name).
- `flask_app.py`    — the original Flask version, preserved. Run locally with `python flask_app.py`.
- `scrapers/`       — all scraping logic (unchanged).

## Run locally (Streamlit)
```bash
pip install -r requirements.txt
cp .env.example .env          # add your real RAPIDAPI_KEY_1, _2, ... keys
streamlit run app.py
```

## Deploy on Streamlit Community Cloud
1. Push this folder to GitHub.
2. Main file path = `app.py` (the default — no change needed).
3. Settings -> Secrets: add your keys (see `.streamlit/secrets.toml.example`).

## Notes
- Add as many `RAPIDAPI_KEY_N` keys as you like; the app rotates through them.
