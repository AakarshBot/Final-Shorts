# Final Shorts — Project Context

## Current state
Functions 01–03 are implemented, tested, and accepted for development use:
1. Topic Fetching
2. Scriptwriter
3. Audio

Function 04 — Visuals Phase 1 is implemented and awaiting manual dashboard validation. Do not start Renderer, Metadata, or Upload yet.

## Factory order
01. Topic Fetching
02. Scriptwriter
03. Audio
04. Visuals
05. Renderer
06. Metadata
07. Upload

Only completed functions should exist in the repository. Do not scaffold future stages.

## Dashboard
- The dashboard is currently a Test desk only while the factory is built.
- Test exposes each completed function independently: Topic Fetcher, Scriptwriter and Audio.
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
- Do not re-open or redesign Functions 01–03 unless a concrete regression is found.
- Do not copy the old visual-fetch runtime architecture into this repo.
- Function 04 should be a new, direct visual-fetch module with focused tests and a Streamlit test desk.
- Start by auditing the user's existing visual-fetch requirements and available free sources, then implement only the smallest useful Visuals function.
- Keep manual visual approval gates.
- Keep the factory free-tier only.
- Run tests and CI before moving beyond Visuals.

## Repository shape
```
app.py
topic_fetcher.py
script_writer.py
audio.py
tests/test_topic_fetcher.py
tests/test_script_writer.py
tests/test_audio.py
requirements.txt
PROJECT_CONTEXT.md
README.md
.github/workflows/test.yml
.gitignore
```

## Last completed
Function 03 — Audio. Manual test passed.

## Current development
Function 04 — Visuals Phase 1 is implemented:
- Original selected story URL is the first web source.
- Two compact automatic visual-search queries are derived from the selected headline/evidence.
- Related publisher pages are scraped in one shared Chromium session.
- Images are filtered for decodeability, size, obvious non-photo assets, and duplicates.
- A conditional entity/profile search is used only when the first pass returns fewer than 10 images.
- The Test dashboard displays 10–15 scraped images when available.
- A manual keyword/phrase/query reruns the same web crawler against the same original story URL and only that manual query.
- The automatic visual queries used are displayed in the Test dashboard so manual queries can be chosen deliberately.
- No AI visual gate is added in Phase 1; human review remains available in the dashboard.

## Next gate
Manually test Function 04 with current sports headlines, including at least one cricketer/action story. Record image count, source diversity, query quality, and whether manual queries return useful new images before extending the function.
