# Final Shorts

A simple, free-tier YouTube Shorts factory built one independently testable function at a time.

## Current

Functions 01–07 are implemented and accepted:
- **01 — Topic Fetching**
- **02 — Scriptwriter**
- **03 — Audio**
- **04 — Visuals Phase 1 + Phase 2**
- **05 — Subtitles**
- **06 — Renderer**
- **07 — YouTube Upload QC**

The Scriptwriter now supplies the opening heading, three title candidates, description, hashtags and public-upload comment in the same generation call. Function 06 hands the approved heading into the renderer. Function 07 provides the final human metadata/video QC and Public or Private upload lane.

The Streamlit dashboard keeps the upload decision human-controlled: review the rendered video and metadata once, approve the QC, then choose Public or Private.

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

The Visuals desk is shared across Shorts, Cricket, YouTube Trends, Top-5, Test, and Live. Option 1 is the automatic scraper/crawler; Option 2 is the manual real-image scraper; Option 3 searches open image sources plus any optional configured stock/search APIs; Option 4 uses the shared AI image generator.

**AI image generation is no-cost by default.** It uses the volunteer-run AI Horde queue and supports anonymous requests, although anonymous requests have the lowest queue priority and can take longer. For better priority without paying, create a free AI Horde account at https://stablehorde.net/ and set `AI_HORDE_API_KEY` in your local environment. The default wait limit is five minutes and can be changed with `AI_HORDE_TIMEOUT`.

Optional hosted image APIs (Pollinations, Hugging Face Inference Providers, Cloudflare Workers AI) are **disabled by default**, even when their tokens happen to be present, because they may use credits or incur charges. Enable them only by deliberately setting `VISUAL_ALLOW_METERED_PROVIDERS=true`. Long-form uses the same generator in landscape mode with a bounded two-minute wait and otherwise retains its evidence-safe chapter-card fallback. No new dependency is required.


### Renderer Test

Function 06 is an isolated final visual preview desk. It uses only generated filler content and a generic local background; it does not call the Topic Fetcher, Scriptwriter, Audio, Visuals, or any AI/API provider.

The final preview uses one canonical style:
- **Headline:** large Oswald Bold block display face, dynamically fitted to one, two or three lines with screen-safe wrapping and stroke-aware bounds, with the existing left-entry animation and moving blue/yellow brand marker.
- **Subtitles:** large bold sans-serif, word-level timing, white phrase text with dark outline, yellow active word, lower-middle safe placement, no background capsule.
- **Branding:** the real `logo.png` in the top-right and a simple source label in the bottom-right.
- **No decorative borders, lines, dots, glass panels, or extra motion.**

### Function 05 · Subtitles

Function 05 takes the approved Scriptwriter narration and approved Audio word timings and converts them directly into `final-shorts.subtitles.v1`. There is no second transcription pass and no AI call. Cues are grouped into short readable phrases with absolute timestamps.

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

### YouTube Upload QC

Function 07 uses a local `token.json` for YouTube OAuth. The QC desk shows the rendered video plus the three Scriptwriter title candidates, editable description, hashtags and comment. One QC approval unlocks the Public and Private upload buttons. A Public upload automatically posts the approved comment; a Private upload does not.

Place your authorized `token.json` beside `app.py`. The token must include YouTube upload permission and YouTube comment permission (or the full YouTube scope). The token file is ignored by Git.

### Free Channel Analytics

Open **Channel Analytics** in the Streamlit page navigation to view channel totals, 7/28/90/365-day performance, daily trends, top videos, traffic sources, and CSV exports. This feature uses Google's official YouTube Analytics API and YouTube Data API; it adds no analytics subscription or paid service.

One-time setup, from the project folder:

    python authorize_youtube_analytics.py

Sign in to the target channel's owner account and approve the read-only permissions. The script creates a separate `analytics_token.json`; it does not replace the upload token. Both token files must remain private and are ignored by Git. The report intentionally ends two days before today to reduce incomplete latest-day metrics. More details: [Free YouTube Channel Analytics](CHANNEL_ANALYTICS_SETUP.md).
