# Final Shorts — Project Context

## Current state
Functions 01–05 are implemented, tested, and accepted for development use:
1. Topic Fetching
2. Scriptwriter
3. Audio
4. Visuals — Phase 1 + Phase 2 complete
5. Subtitles

Function 04 Visuals Phase 1 and Phase 2 are complete. Function 05 Subtitles converts approved Edge-TTS word timings into SRT before Renderer.

## Factory order
01. Topic Fetching
02. Scriptwriter
03. Audio
04. Visuals
05. Subtitles
06. Renderer
07. Metadata
08. Upload

Only completed functions should exist in the repository. Do not scaffold future stages.

## Dashboard
- The dashboard is currently a Test desk only while the factory is built.
- Test exposes each completed function independently: Topic Fetcher, Scriptwriter, Audio, Visuals and Subtitles.
- Function handoffs are human-approved in the dashboard.
- No Live-production screen is present yet; it will be added when the production pipeline actually exists.
- Dashboard visual polish is parked. Change only functional test behavior while building the factory.

## Non-negotiables
- Keep the code simple and direct.
- Smallest change that works.
- Few API/AI calls.
- Free-tier services only.
- Human approval gates remain part of the factory flow.
- No runtime patching, compatibility wrappers, duplicate stage implementations, or future-stage placeholders.
- Add focused tests for each function.
- Run `python -m pytest -q` and CI before moving to the next function.
- Do not change unrelated functions.
- Never hardcode or commit secrets.

## Topic Fetcher contract
- Sports-first discovery.
- Cricket desk split into India/Asia and Global.
- Niche Sports desk.
- Fresh event-level stories, not stale pages.
- Exclude schedules, standings, scorecards, squads, medal-tally and similar utility pages.
- Cluster multiple publisher headlines describing the same event.
- Keep genuinely different events separate even when the same person appears.
- Return up to 20 topics.
- Find 20 more uses a different query set and excludes already returned topics/events.
- Google News is the primary source.
- GDELT is a fallback only when the primary source does not produce enough topics.

## Scriptwriter contract
The old `AakarshBot/viral-shorts-factory` Scriptwriter is the behavioral baseline. Its current output is considered the desired baseline by the project owner.

Function 02 rules:
- Sports only.
- Regular Shorts only; no Top-5 or Deep-Dive architecture.
- One sports persona: HYPE COMMENTATOR.
- Primary writer: Groq `openai/gpt-oss-120b`.
- Logical recovery: Groq `openai/gpt-oss-20b` only when the primary call fails or its output fails local validation.
- Keep 4–5 scenes.
- Scene 1 targets 10–12 words, hard maximum 14.
- Target roughly 22–27 seconds; never exceed 30 seconds.
- Complete, information-dense story using only supplied evidence.
- No invented facts/quotes/motives/numbers/predictions, filler, CTA, generic setup, or retention bait.
- Generate exactly 3 titles, but do not show them during Scriptwriter manual QC. Preserve them in the output for a later title-selection step.
- Keep visual metadata per scene: primary_entity, visual_intent, specific_search_prompt, sport_or_topic_category. Visual entity grounding is handled by Function 04.
- No hook scoring.
- Human QC shows one editable voiceover box per scene and an Approve action.
- Do not copy code from the old factory; reproduce only the agreed behavior.

## Audio contract
Function 03 rules:
- Input is only the approved Scriptwriter handoff.
- One direct Audio module; no runtime patching or provider-wrapper chain.
- Edge-TTS is the only speech provider.
- HYPE COMMENTATOR uses the female Indian voice for the selected language, with +8% rate and +4Hz pitch.
- Generate scenes with a maximum of two concurrent TTS requests.
- Cache audio and word timings by narration text, language, voice settings and rate.
- Capture native Edge-TTS WordBoundary timings and validate them against the encoded duration.
- Retry only transient failures, with one bounded retry/backoff.
- Measure real encoded duration with ffprobe.
- If the full Short exceeds 30 seconds, apply one measured speed correction and regenerate once. Fail closed if it still exceeds the limit.
- No WhisperX, second ASR pass, extra LLM call, BGM/SFX mixing, voice cloning, pronunciation AI, or alternate TTS provider in the normal path.
- Human Audio approval stores the verified payload as the handoff for Visuals.
- Audio has been manually tested and accepted by the project owner.

## Audit / handoff rules for the next chat
- Treat the current `main` branch as the clean working baseline.
- Do not re-open or redesign completed Functions unless a concrete regression is found.
- Do not copy the old visual-fetch runtime architecture into this repo.
- Function 04 remains a direct visual module with focused tests and a Streamlit test desk. Phase 1 and Phase 2 are complete; its four visual test options remain independent.
- Start by auditing the user's existing visual-fetch requirements and available free sources, then implement only the smallest useful Visuals function.
- Keep manual visual approval gates.
- Keep the factory free-tier only.
- Run tests and CI before moving to the next function.

## Repository shape
```
app.py
topic_fetcher.py
script_writer.py
audio.py
tests/test_topic_fetcher.py
tests/test_script_writer.py
tests/test_audio.py
tests/test_subtitles.py
requirements.txt
PROJECT_CONTEXT.md
README.md
.github/workflows/test.yml
.gitignore
```

## Last completed
Function 05 — Subtitles.

## Current development
Function 05 — Subtitles is implemented:
- Visuals Phase 1 and Phase 2 are complete.
- Option 1 is the automatic scraper/crawler.
- Option 2 is the standalone manual scraper.
- Option 3 is manual real-image search.
- Option 4 is manual AI generation.
- Option 1 remains the Phase 1 scraper/crawler.
- Option 2 is manual-query-only real-image retrieval across all configured real-image sources.
- Option 3 is manual-prompt-only AI generation across configured AI providers.
- No semantic, licensing or monetization filtering is active in Phase 2.
- The two new manual paths run their configured providers independently and fail safely per provider.
- Automatic discovery uses the exact selected headline plus entity/context queries.
- The manual scraper accepts arbitrary people, events or phrases and searches current publisher pages without requiring a selected headline.
- Google News RSS and DDGS/Bing/Yahoo discovery run as complementary free search lanes.
- Related publisher pages are relevance-filtered, freshness-filtered and host-diversified before scraping.
- If the first pass is still underfilled, real web profile/action pages are searched separately.
- One shared Chromium session handles concurrent publisher-page scraping.
- Browser-loaded image responses are reused when direct image requests are invalid.
- Static HTML extraction is a real fallback for pages the browser path cannot use.
- Responsive image attributes, JSON-LD images, article metadata and page publication dates are handled.
- Images are filtered for decodeability, minimum dimensions, obvious non-photo assets and duplicates.
- The target pool is 15 images with 10 treated as ready for the next human-review step.
- Option 2 is a standalone manual crawler. A name-only query searches normally; a contextual query is expanded by one lightweight AI query-planning call and searches older publisher pages as well.
- The Test dashboard shows the automatic queries used and exposes crawler diagnostics.
- No AI visual-verification call is used in Phase 1; human review remains the final image-selection gate.
- Visuals uses only free services. DDGS is a discovery dependency; Playwright/Chromium is the browser scraper.

## Visuals Phase 2 contract
- Option 1: existing Phase 1 scraper/crawler.
- Option 2: manual query → real-image sources → image download → basic image validation/deduplication → dashboard.
- Option 2 real sources: Commons, DuckDuckGo, Wikipedia, Openverse, plus Pixabay/Pexels/Unsplash when their API keys are configured.
- Option 2 has no semantic, licensing, monetization or identity filter in this phase.
- Option 3: manual prompt → configured AI image providers → dashboard.
- Current AI providers: Hugging Face Inference Providers with FLUX.1-schnell and Cloudflare Workers AI with FLUX.1-schnell.
- Option 2 and Option 3 never trigger automatically.

## Subtitles contract
- Input is only the approved Audio handoff.
- Use the native Edge-TTS word timings already produced by Function 03.
- Build deterministic SRT cues with readable word grouping; no AI call is used.
- Write one scene SRT plus one combined SRT for Renderer.
- Human approval stores the verified subtitle payload as the Renderer handoff.
- Reject missing, invalid or out-of-order timings.

## Next gate
Function 06 — Renderer starts only after Subtitles is tested and accepted.
