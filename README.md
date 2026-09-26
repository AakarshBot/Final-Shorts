# Final Shorts

A simple, free-tier YouTube Shorts factory built one independently testable function at a time.

## Current

Functions 01–04 are implemented and accepted:
- **01 — Topic Fetching**
- **02 — Scriptwriter**
- **03 — Audio**
- **04 — Visuals Phase 1 + Phase 2**

Visuals Phase 1 and Phase 2 are complete. The Subtitles implementation is intentionally not present yet. The Function 06 Renderer now has a final visual preview desk.

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


### Renderer Test

Function 06 is an isolated final visual preview desk. It uses only generated filler content and a generic local background; it does not call the Topic Fetcher, Scriptwriter, Audio, Visuals, or any AI/API provider.

The final preview uses one canonical style:
- **Headline:** Bebas Neue-style condensed display face, single line, dynamically fitted to the safe width, with the existing left-entry animation.
- **Subtitles:** bold sans-serif, word-level timing, white text with a dark outline, one gold active-word highlight, lower-middle placement, no permanent caption box.
- **Branding:** the real `logo.png` in the top-right and a simple source label in the bottom-right.
- **No decorative borders, lines, dots, glass panels, or extra motion.**

### Subtitle handoff contract

Function 05 should hand Function 06 a Python/JSON-compatible object shaped like:

```json
{
  "schema": "final-shorts.subtitles.v1",
  "language": "english",
  "cues": [
    {
      "start": 0.30,
      "end": 1.28,
      "words": [
        {"text": "India", "start": 0.30, "end": 0.52},
        {"text": "started", "start": 0.52, "end": 0.75}
      ]
    }
  ]
}
```

Times are absolute seconds from the start of the final video. Each cue contains the words that should be displayed together. The Renderer derives the active word from the word timestamps and does not need a second transcription pass.

Use this JSON contract internally. SRT/VTT/ASS can be derived later only when an external subtitle file is required; they should not be the production handoff between Functions 05 and 06.
