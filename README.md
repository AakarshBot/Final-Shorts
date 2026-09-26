# Final Shorts

A simple, free-tier YouTube Shorts factory built one independently testable function at a time.

## Current

Functions 01–04 are implemented and accepted:
- **01 — Topic Fetching**
- **02 — Scriptwriter**
- **03 — Audio**
- **04 — Visuals Phase 1 (scraping)**

Visuals Phase 1 has been live-tested successfully. The next function is **05 — Renderer** only after its handoff is defined.

The Streamlit dashboard is currently a Test desk for independent function testing. Live production is intentionally not present until the full factory exists.

Run locally:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
streamlit run app.py
```

For Function 04 Visuals, install the Chromium browser once after dependencies: 

```bash
python -m playwright install chromium
```
