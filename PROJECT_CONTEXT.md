# Final Shorts — Project Context

## Current stage
Function 02 — Scriptwriter

Topic Fetcher is accepted for now. Dashboard UI improvements are parked for later.

## Factory order
01. Topic Fetching
02. Scriptwriter
03. Audio
04. Visuals
05. Renderer
06. Metadata
07. Upload

Only the current function is implemented. Do not scaffold later functions.

## Dashboard
- Test and Live modes are separate.
- Live exists in the dashboard but is disabled until the factory is built.
- Test is an independent-function test desk.
- Test exposes each completed function independently; currently Topic Fetcher and Scriptwriter.
- Each function must be testable from Streamlit before the next function is started.

## Non-negotiables
- Keep the code simple and direct.
- Smallest change that works.
- Few API/AI calls.
- Free-tier services only.
- Human approval gates remain part of the eventual production flow.
- No runtime patching, compatibility wrappers, duplicate stage implementations, or future-stage placeholders.
- Add focused tests for each function.
- Run pytest and CI before moving to the next function.
- Do not change unrelated functions.

## Topic Fetcher requirements
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
The old `AakarshBot/viral-shorts-factory` Scriptwriter is the behavioral baseline. Its current output is considered the desired 10/10 baseline by the project owner.

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
- Generate exactly 3 titles, but do not show them during Scriptwriter manual QC. Preserve them in the output for a later pre-upload title-choice step.
- Keep visual metadata per scene: primary_entity, visual_intent, specific_search_prompt, sport_or_topic_category. Visual entity grounding is a later function.
- No hook scoring.
- Human QC shows one editable voiceover box per scene and an Approve action. Approval marks the script as the handoff for Audio; Audio itself is not implemented yet.
- Do not copy code from the old factory; reproduce only the agreed behavior.

## Last completed
Function 01 — Topic Fetching accepted for now.

## Next gate
Run Function 02 from Streamlit against real selected sports stories, inspect the generated scripts and manual-edit/approve flow, then refine only Scriptwriter before Function 03.
