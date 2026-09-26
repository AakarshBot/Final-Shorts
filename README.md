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

The Visuals test desk has four independent options. Option 1 is the automatic scraper/crawler and starts when a headline is selected. Option 2 is the standalone manual scraper. It uses an AI query planner: a name-only query searches normally, while a contextual query generates up to two useful variants and searches older publisher pages as well. Option 3 searches Commons, DuckDuckGo, Wikipedia, Openverse, and any configured Pixabay/Pexels/Unsplash APIs. Option 4 generates images with Hugging Face Inference Providers and Cloudflare Workers AI.


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
