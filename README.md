# Final Shorts

A simple, free-tier YouTube Shorts factory built one independently testable function at a time.

## Current

Functions 01–04 are implemented and accepted:
- **01 — Topic Fetching**
- **02 — Scriptwriter**
- **03 — Audio**
- **04 — Visuals Phase 1 (scraping) + Phase 2 (manual real/AI image testing)**

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


### Visuals Phase 2

The Visuals test desk has three independent options. Option 1 is the Phase 1 scraper/crawler. Option 2 accepts only a manual query and searches Commons, DuckDuckGo, Wikipedia, Openverse, and any configured Pixabay/Pexels/Unsplash APIs. Option 3 accepts only a manual prompt and currently supports Hugging Face Inference Providers and Cloudflare Workers AI.

Optional .env keys:

HF_TOKEN, HF_IMAGE_MODEL
CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, CLOUDFLARE_IMAGE_MODEL
PIXABAY_API_KEY, PEXELS_API_KEY, UNSPLASH_ACCESS_KEY
