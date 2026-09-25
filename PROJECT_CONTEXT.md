# Final Shorts — Project Context

## Current stage
Function 01 — Topic Fetching

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
- For now Test exposes only Topic Fetcher.
- The Topic Fetcher must be testable from Streamlit before Function 02 is started.

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

## Last completed
Fresh repository baseline with only the first function and its testing dashboard.

## Next gate
Run the Topic Fetcher from Streamlit against live feeds, inspect the actual results, then refine only Function 01 before moving to Function 02.
