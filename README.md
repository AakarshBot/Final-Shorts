# Final Shorts

A simple, free-tier YouTube Shorts factory built one independently testable function at a time.

## Current

Functions 01–04 are implemented and accepted:
- **01 — Topic Fetching**
- **02 — Scriptwriter**
- **03 — Audio**
- **04 — Visuals Phase 1 + Phase 2**

Visuals Phase 1 and Phase 2 are complete. The next function will be designed later; no subtitle implementation is currently present.

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


### Visuals

The Visuals test desk has four independent options. Option 1 is the automatic scraper/crawler and starts when a headline is selected. Option 2 is the standalone manual scraper. It uses an AI query planner: a name-only query searches normally, while a contextual query generates up to two useful variants and searches older publisher pages as well. Option 3 searches Commons, DuckDuckGo, Wikipedia, Openverse, and any configured Pixabay/Pexels/Unsplash APIs. Option 4 generates images with Hugging Face Inference Providers and Cloudflare Workers AI.
