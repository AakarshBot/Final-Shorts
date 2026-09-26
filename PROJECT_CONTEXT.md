# Final Shorts — Project Context

## Current state
Functions 01–04 are implemented, tested, and accepted for development use.
Function 06 Renderer is complete as the final canonical visual treatment and isolated preview desk.
Function 05 Subtitles is the current development stage.

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
- Test exposes the completed function desks plus an isolated Function 06 Renderer preview desk.
- Function handoffs are human-approved in the dashboard.
- No Live-production screen is present yet; it will be added when the production pipeline actually exists.
- Dashboard visual polish is parked. Function 06's renderer test desk is intentionally a small final UI preview, not production functionality.

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
- Find 20 more uses a different query set, excludes already returned topics/events, and appends new topics to the existing dashboard pool.
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
- Start from the current project context and implement only the next requested function.
- Keep human approval gates where the function contract requires them.
- Keep the factory free-tier only.
- Run tests and CI before moving to the next function.

## Repository shape
```
app.py
topic_fetcher.py
script_writer.py
audio.py
subtitles.py
tests/test_topic_fetcher.py
tests/test_script_writer.py
tests/test_audio.py
tests/test_subtitles.py
tests/test_visual_fetcher.py
tests/test_visual_search.py
tests/test_visual_generator.py
tests/test_renderer.py
renderer.py
requirements.txt
PROJECT_CONTEXT.md
README.md
.github/workflows/test.yml
.gitignore
```

## Last completed
Function 06 — Renderer.

## Current development
Function 05 — Subtitles. Function 06 Renderer is complete as an isolated preview desk; its previews use filler content only and are not a production handoff:
- Visuals Option 1 is the automatic scraper/crawler.
- Visuals Option 2 is the standalone manual scraper with lightweight AI query planning and historical retrieval for contextual queries.
- Visuals Option 3 is manual real-image search across configured sources.
- Visuals Option 4 is manual AI image generation across configured providers.
- Visuals remains manual-review driven; no AI visual-verification gate is used in the completed Visuals phases.

Function 05 is the direct Scriptwriter + Audio timing handoff. It uses no transcription or AI call and produces the renderer subtitle payload from the approved narration and native Edge-TTS word timings.

## Visuals Phase 2 contract
- Option 1: existing Phase 1 scraper/crawler.
- Option 2: manual query → real-image sources → image download → basic image validation/deduplication → dashboard.
- Option 2 real sources: Commons, DuckDuckGo, Wikipedia, Openverse, plus Pixabay/Pexels/Unsplash when their API keys are configured.
- Option 2 has no semantic, licensing, monetization or identity filter in this phase.
- Option 3: manual prompt → configured AI image providers → dashboard.
- Current AI providers: Hugging Face Inference Providers with FLUX.1-schnell and Cloudflare Workers AI with FLUX.1-schnell.
- Option 2 and Option 3 never trigger automatically.


## Next gate
Function 05 — Subtitles is the current build stage. Once its focused tests and CI are green, the approved subtitle payload becomes the handoff available to Function 06 Renderer.


## Renderer contract

Function 06 currently exists as an isolated final preview desk and does not consume factory handoffs yet.

Final visual system:
- one canonical **Editorial Highlight** style
- headline uses a large, heavy block display face (Anton preferred, with local bold fallbacks), single line, dynamically fitted to available width, with a moving blue/yellow brand marker
- subtitle styling uses a large bold sans-serif, dark outline, white phrase text and a blue active-word capsule with yellow active text
- subtitles use word-level timing, stable phrase layout and restrained keyword emphasis in the lower-middle safe area
- logo is the real local `logo.png`, top-right
- source label is plain text, bottom-right
- no permanent border, decorative graphics, glass panel, or universal Ken-Burns effect
- when the opening headline is enabled, audio may already be running but subtitles remain hidden until the 1.15-second headline window ends

Function 05 subtitle handoff to Function 06 must use `final-shorts.subtitles.v1` JSON-compatible data with absolute seconds and grouped cues containing per-word `start` and `end` timestamps. The Renderer must not transcribe, regroup semantically, or call an AI provider.
