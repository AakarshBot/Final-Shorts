# FINAL-SHORTS BIGGEST RULE

**TEST FIRST → USER APPROVAL → PUSH TO LIVE.**

This is the governing workflow for the entire factory.

- New functionality, UI changes, pipeline behavior, language options, and other improvements are developed and tested in **Test** first.
- **Test is the proving ground.** The user decides what they like, what they dislike, and what is approved.
- Once the user approves a tested component, moving it to **Live must be easy and direct**. The approved Test behavior should become the Live behavior without rebuilding or re-implementing the component from scratch.
- Test and Live may differ in presentation or in whether a transition is manual versus automatic, but they must share the same approved component logic, inputs, outputs, and handoff contract.
- Do not make Live-only versions of a component when the component is supposed to graduate from Test.
- Do not force experimental features into Live before the user approves them in Test.
- Language support is explicitly part of this model: language options can be introduced and refined in Test first, then promoted to Live once the user approves the result.
- Architecture must make promotion from Test → Live **simple, predictable, and low-risk**. Prefer shared direct implementations over duplicated Test/Live code.
- When cleaning up the factory, aggressively delete unnecessary code, duplicate logic, dead state, obsolete wrappers, and abandoned implementations—but never delete active experimental Test functionality merely because it has not yet been promoted to Live.

This rule takes precedence over convenience in implementation and should guide future architecture decisions throughout Final-Shorts.

## Test-first factory operating model

Test is a modular laboratory; Live is the approved production line.

- Topic selection hands the selected story's URL and story payload to the relevant function.
- Test Scriptwriter can generate a script, and Manual QC can edit and approve it. The Scriptwriter handoff is the canonical package for every later function that needs script data.
- The Scriptwriter Test view should expose the complete editorial handoff: opening headline when enabled, quote/attribution when available, and the slide scripts. For Top-5, this means each slide's spoken headline plus its visual-only body copy.
- Audio consumes the Scriptwriter handoff and returns audio/timing data. Test lets the user listen and approve it.
- Visuals are a modular function. Automatic scraping starts from the selected story URL, while manual scraper/search/AI options can be run independently. Manual inputs may deliberately bypass upstream approvals when the visual function does not actually require that approval.
- Test Visuals uses the same slide-board interaction as Live: script context above each slide, per-slide visual attachment, crop/reposition, and an explicit approved visual handoff. Standard Cricket production uses four visual slides; Top-5 remains a separate six-slide workflow.
- Stats Card, Quote Card, Top-5 card/visual experiments, and other visual sub-functions are independently testable in Test. They must not be blocked merely because an earlier pipeline stage is unapproved. They still receive whatever concrete input they genuinely need, such as an image pool or manually entered quote.
- Subtitles consume approved Audio + Scriptwriter handoffs and produce the subtitle handoff used by Renderer. No visual subtitle preview is required in Test or Live.
- Test Renderer is the integration check. It consumes only the exact approved handoffs it needs—Scriptwriter, Audio, Subtitles and Visuals. When one is missing, Test explicitly identifies the missing approval. Once all required handoffs exist, it builds the real Short.
- Test stage navigation may jump directly to any stage so individual functions can be tested out of order. Live enforces the approved production sequence.
- Once a Test component is approved, its same component logic and handoff should move to Live directly. Live should not require a separate reimplementation of something already proven in Test.
- Language support follows this exact model. Language options are experimental in Test first and should be promoted to Live only after the user approves the Test result. The dormant Live language state is intentional and must not be removed as dead code.

# Final Shorts — Project Context

## Project status

The factory's seven functional stages are **Approved** for the established Deep-Dive / Cricket / Niche Sports line:

01. Topic Fetcher — **Approved**
02. Scriptwriter — **Approved**
03. Audio — **Approved**
04. Visuals — **Approved**
05. Subtitles — **Approved**
06. Renderer — **Approved**
07. YouTube Upload — **Approved**

The Dashboard UI/UX remains **WIP**.

Production lines:
1. **Top 5 cricket stories of the day** — **Test-only / WIP**
2. **On This Day** — **Test-first / WIP**

Top-5 is currently Test-only / WIP. Its Option 9 Manual Subject Cutout remains a Top-5-only experiment. Live Cricket now includes the approved visual option `Option 7 · Text Cutout`, using the proven manual subject cutout rendering path without changing Top-5 Option 7 or Option 9.

## Factory order

01. Topic Fetcher
02. Scriptwriter
03. Audio
04. Visuals
05. Subtitles
06. Renderer
07. YouTube Upload

There is no separate Metadata stage. Publish metadata is generated by Function 02 and carried through to Function 07.

## Non-negotiables

- Keep the code simple and direct.
- Make the smallest change that works.
- Minimise AI/API calls.
- Free-tier services only; no paid production dependency.
- Human review/approval gates remain part of the factory flow.
- Do not add unnecessary gates around manual QC.
- No runtime patching, compatibility wrappers, duplicate stage implementations, or future-stage scaffolding.
- Add focused tests for functional changes.
- Run `python -m pytest -q` before declaring code complete when a local checkout is available.
- Never hardcode or commit secrets.
- `token.json` is local-only and ignored by Git.
- Do not redesign a completed function without a concrete regression.
- Do not copy the old `viral-shorts-factory` runtime architecture into this repo.

## Topic Fetcher — Function 01

Contract:
- Sports-first discovery.
- Cricket split into India/Asia and Global.
- Niche Sports desk.
- Prefer fresh event-level stories rather than stale utility pages.
- Exclude schedules, standings, scorecards, squads, medal-tally and similar utility pages.
- Cluster multiple publisher headlines describing the same event.
- Keep genuinely different events separate even when the same person appears.
- Return up to 20 topics.
- “Find 20 more” uses a different query set, excludes already returned topics/events, and appends new topics.
- Google News is the primary source.
- GDELT is fallback only when the primary source does not produce enough topics.
- Cricket profile relevance is title-led: known cricket players can pass without the word “cricket”, while description-only publisher boilerplate is not treated as proof of relevance.
- Near-identical wording is not used as a blanket duplicate rule; event clustering remains responsible for removing multiple headlines about the same event while preserving genuinely different stories.

Status: **Approved.**

## Scriptwriter — Function 02

Cricket writer:
- Rewritten from scratch as a single direct function.
- Research first uses the selected article and searches for up to two related current reports when available, so the LLM receives enough factual material to compress the story.
- One model call generates the complete four-slide package.
- If the generated package breaks a hard generation rule, the invalid draft is never shown in Manual QC; one hidden rewrite is made with the exact failure.
- The first call uses Groq `openai/gpt-oss-120b`.
- The hidden rewrite/fallback uses Groq `openai/gpt-oss-20b`.
- The writer makes at most two model calls for one generation attempt.
- The LLM is explicitly instructed before generation that Slide 1 must contain 13 words or fewer and the full narration must be 32 seconds or less at roughly 150 words per minute.
- A script at 32 seconds or less is accepted for the downstream Audio speed correction; a script estimated above 32 seconds is hidden and rewritten before Manual QC.
- The main subject name is a required structured field and must appear in spoken narration; a player must not be described only by age, role or pronoun when the exact name is available.

Narration:
- Sports only.
- Regular Shorts only; no Top-5 or Deep-Dive architecture.
- One persona: HYPE COMMENTATOR.
- Exactly 4 scenes.
- Compress all material factual information from the research packet into the four scenes, removing only repetition, boilerplate and low-value wording.
- No invented facts, quotes, motives, numbers, predictions, filler, CTA or viewer-directed retention bait.
- Every scene carries `primary_entity`, `visual_intent`, `specific_search_prompt`, and `sport_or_topic_category`.

Generated publish metadata:
- `headline`: exactly 3 or 4 words.
- `titles`: exactly 3 title candidates.
- `seo_description`: concise story-specific description.
- `hashtags`: 3–5 relevant hashtags.
- `comment`: one concise discussion-oriented public-upload comment.

Human Scriptwriter QC:
- Manual QC receives only a script that has passed the writer's hidden generation/rewrite checks.
- The heading remains editable with the narration.
- Narration scenes remain independently editable.
- Approval stores the complete package in the approved Scriptwriter handoff.
- There is no manual AI rewrite button; regeneration belongs inside the Scriptwriter function before QC.
- Titles, description, hashtags and comment are preserved for the later Upload QC stage.

Status: **Approved after simplification/regression fix.**

## Audio — Function 03

Contract:
- Input is only the approved Scriptwriter handoff.
- Edge-TTS is the only speech provider.
- HYPE COMMENTATOR uses the selected Indian voice with +8% rate and +4Hz pitch.
- Maximum two concurrent TTS requests.
- Audio and native word timings are cached by narration text, language and voice settings.
- Capture native Edge-TTS WordBoundary timings.
- Validate timings against encoded duration.
- Retry only transient failures with one bounded retry/backoff.
- Measure real encoded duration with ffprobe.
- If the full Short exceeds 30 seconds, apply one measured speed correction and regenerate once.
- Fail closed if it remains over the limit.
- No second ASR/transcription pass, alternate TTS provider, voice cloning, pronunciation AI, BGM/SFX mixing or extra LLM call in the normal path.
- Human Audio approval stores the verified payload for later stages.

Status: **Approved / manually tested.**

## Visuals — Function 04

Visual retrieval is complete for the current factory phase.

The standard Cricket/Deep-Dive Visuals desk contains four retrieval options:
1. Automatic scraper/crawler.
2. Manual scraper.
3. Manual real-image search.
4. Manual AI image generation.

Top-5 has eight visual options in Test:
1. Automatic Scraper.
2. Manual Scraper.
3. Manual Fetcher.
4. AI Generation.
5. Stats Card.
6. Quote Card.
7. Subject Cutout.
8. Body Card — **WIP**.

The established Cricket/Deep-Dive visual retrieval options remain unchanged. Top-5 Option 3 is the manual real-image fetcher: it accepts a manual query and returns the real-image provider pool only. It does not render a text card. Top-5 Option 8 is the future Body Card text-based visual and remains dashboard WIP with no active renderer.

Top-5 Test Visuals remains independently runnable. The six-slide production Visual QC uses the approved Top-5 Scriptwriter handoff, while the standalone Test playground can exercise visual functions without upstream approvals.

Crop / Reposition remains the existing shared crop path. Cropped bytes are the exact bytes passed to Top-5 preview, selection and Subject Cutout analysis.

Option 7 · Subject Cutout is optional and user-selected. It is implemented with the existing PyTorch, torchvision and Transformers dependencies and the local `ZhengPeng7/BiRefNet` model. No new Python dependency is introduced. Subject Cutout inference is CPU-only and always uses float32; the renderer never calls `.half()` for this path.

Subject Cutout receives the selected/cropped image, builds one foreground mask, then chooses one composition directly from that mask:
- Centered foreground with useful space on both sides: large horizontal headline crosses the subject field. Text starts outside the leftmost subject and continues outside the rightmost subject.
- Subject predominantly on the right: two-word-per-line headline stack in the left negative space.
- Subject predominantly on the left: two-word-per-line headline stack in the right negative space.
- Otherwise: large headline in the larger top or bottom negative-space region.

The original image is composited back through the foreground mask after the headline is drawn, so the detected foreground remains visibly above the text while real gaps in the mask keep the headline visible.

Top-5 Option 7 has no body copy. It uses the approved headline only. Normal Top-5 cards never run subject segmentation.

## Subtitles — Function 05

Contract:
- Input is approved Scriptwriter narration plus approved Audio native word timings.
- No transcription or second AI call.
- Output schema: `final-shorts.subtitles.v1`.
- Times are absolute seconds from the start of the final video.
- Cues contain grouped words with per-word `start` and `end`.
- The Renderer derives the active word directly from these timings.
- No semantic regrouping or additional transcription occurs in the Renderer.

Status: **Approved.**

## Renderer — Function 06

Top-5 uses a static 9:16 full-bleed editorial-card treatment in the shared renderer.

Normal Top-5 cards:
- Use the direct static editorial typography path.
- No subject detection.
- No image-busyness/negative-space search.
- No broad scrim, transparent/faded type, universal gradient, permanent border, decorative dots/lines or headline motion.
- Logo remains top-right; source label remains bottom-right.
- English headlines use Oswald.

Option 3 · Manual Fetcher is active in Top-5 Test. It performs manual-query real-image retrieval only and hands the returned image pool to the existing image-selection/crop flow.

Option 8 · Body Card is **WIP**. It is reserved for the text-based Top-5 body visual and has no active renderer yet.

Option 7 · Subject Cutout:
- Runs local BiRefNet only when explicitly selected.
- Uses CPU float32 inference with the existing dependency stack.
- Suppresses all body copy.
- Uses the actual foreground mask to keep players/subjects above headline pixels.
- Centered compositions cross the foreground field; side compositions use the opposite-side negative space with two-word-per-line stacks; remaining compositions use the larger top/bottom negative space.
- Multiple subjects are treated as one foreground field for the crossing headline, while genuine gaps in the mask remain visible.
- The renderer never silently turns Subject Cutout into Option 3.
- The same `build_top5_card_preview` / `_draw_top5_editorial_card` contract is used by Test and the eventual Live promotion.

The obsolete Top-5 image-busyness search, multi-stage subject scoring, SciPy connected-component path, body word-cap/rejection helper and FP16 CUDA inference path have been deleted.

## YouTube Upload — Function 07

Authentication:
- Uses a local `token.json` beside `app.py`.
- `token.json` is ignored by Git.
- Google YouTube API client/auth dependencies are installed through `requirements.txt`.
- Upload requires YouTube upload authorization.
- Public comment posting requires comment authorization as well.

Upload flow:
- One manual **Upload QC** gate.
- Shows the rendered video.
- Shows the three Scriptwriter title candidates.
- Title candidates are editable; one is selected for the upload.
- Description is editable.
- Hashtags are editable and appended to the uploaded description.
- Public-upload comment is editable.
- User approves the QC once.
- After approval there are exactly two upload choices:
  - **Upload Public**
  - **Upload Private**
- No additional confirmation gate is added.

Public upload:
- Uploads the video as public.
- Posts the approved comment to the uploaded video as a top-level comment.

Private upload:
- Uploads the video as private.
- Does not post the comment.

The uploader detects the actual privacy status returned by YouTube and reports comment success/failure without introducing another approval gate.

Status: **Approved.**

## Dashboard state

The Dashboard is **WIP**.

Current dashboard contains the approved Test pages and the connected Live production surface, but the Dashboard UI/UX remains under active development.

Implemented:
- Function selector for stages 01–07.
- Scriptwriter manual QC.
- Renderer isolated preview desk.
- Upload QC desk with Public/Private upload lane.

Important:
- Dashboard UI remains to be improved as the Test experience is converted into the Live production flow.
- Do not add new factory logic while doing dashboard UI work unless required to support an existing completed handoff.
- Preserve the already-approved function contracts.

### Top-5 current implementation checkpoint

- Top-5 Visuals Test remains independently runnable with exactly eight dashboard choices.
- Top-5 Option 3 is **Manual Fetcher**: manual query → real-image provider results → existing image pool. It does not render card typography.
- Top-5 Option 8 is **Body Card · WIP** and performs no rendering.
- Cricket's Option 3 / Real Image Search implementation is untouched and remains part of the approved Cricket visual pipeline.
- Top-5 Option 7 has been rewritten from scratch to keep the implementation direct and small.
- Option 7 uses the existing local `ZhengPeng7/BiRefNet` model through the already-installed PyTorch/torchvision/Transformers stack.
- The current supported runtime is CPU-only. Model and input tensors remain float32; no CUDA branch or FP16 conversion is used.
- The model is loaded once per process and the foreground mask is cached per selected image.
- Option 7 analyzes the actual selected/cropped image. Normal Top-5 cards do not run segmentation.
- The Subject Cutout renderer makes one direct composition choice from the foreground bbox and available space: cross-subject, vertical-left, vertical-right, top-negative-space or bottom-negative-space.
- Cross-subject text is deliberately wider than the foreground field and therefore starts outside the first subject, disappears behind foreground, and reappears beyond the last subject.
- Side layouts use at most two words per line and are always positioned inside the safe frame.
- Foreground restoration is done directly with the returned mask after text rendering. This is what creates the real text-behind-subject effect and preserves text through genuine gaps.
- Subject Cutout does not render body copy and ignores upstream body data.
- The previous Top-5 Option 3 adaptive quiet-region/text-card implementation is deleted. Option 3 is now only the manual image fetcher.
- The future text-based body visual is reserved as Top-5 Option 8 · Body Card and remains WIP.
- No wrappers, compatibility layers, new dependencies or duplicate Subject Cutout pipelines are part of this implementation.

Status: **Top-5 Option 3 Manual Fetcher is active in Test. Option 7 Subject Cutout is active in Test/WIP. Option 8 Body Card is WIP. Live Cricket Option 7 · Text Cutout is active in Live.**
### Production Line 03 — On This Day

Purpose:
- Produce a daily sports-focused historical package based on events associated with the current calendar date.
- It uses the same seven factory stages as every other production line.
- Historical stories must be grounded in verifiable source material and clearly separated from current-day news.
- The date matching, story selection, script structure, visual treatment and publishing details will be designed in Test first.

Status: **Planned / Test framework WIP.**

### Live Cricket Option 7 · Text Cutout

Live Cricket's Text Cutout is the visual counterpart of the proven Top-5 manual subject cutout composition, while remaining a separate Live option. It is English-only, has no subtitles, and its own editable headline defaults to the approved Cricket Script headline only as filler. It supports Negative Space and Behind Subject composition, the same font/style choices, and an editable polygon text area drawn directly on the 1080 × 1920 frame. It starts as a four-point rectangle; dragging points reshapes it, and clicking an edge adds another point. The polygon is the sole position/area control; there are no X/Y sliders. Text auto-fits line by line against the usable width of the polygon. Behind Subject restores the detected foreground subjects above the complete text/effects stack, including multiple people and real gaps between them.

Text Cutout shows the same source-image crop control used by the other visual options: **Crop / reposition** opens the existing 9:16 crop function, with the same framing behavior and output path. Each source image keeps its own crop in the existing `live_visual_crops` store, and Text Cutout uses that cropped image when selected. Switching between images, modes, fonts, styles, headlines, sizes and crops is valid and must not crash or contaminate another image's state. The cropper state is keyed to the selected image and composition mode.

The rendered Text Cutout frame is preserved exactly for production handoff: no logo, no source label and no other overlays. A Text Cutout slide also has no subtitles. The headline, text size, font, style, mode and polygon points only become the production configuration when the user presses **Render Now**. Changing polygon points or controls must not regenerate the rendered preview automatically. The editor is an inline Streamlit v2 component with no added package dependency. The Text Cutout UI is isolated from the full dashboard so moving polygon points does not refresh the rest of the Live dashboard; **Render Now** is the explicit preview-generation action. The final rendered frame can be attached to any Cricket slide.

### Test / Live architecture audit

The factory still follows one core implementation per production stage. Test and Live differ in orchestration, not in approved stage logic.

For Top-5 during the current WIP period:
- Test is the only place where Top-5 visual changes are being developed and evaluated.
- Option 3 is active in Test as the manual image fetcher.
- Option 8 is explicitly a dashboard WIP choice with no active renderer.
- Top-5's shared card renderer remains the component that will be promoted to Live after its Test approval.
- Existing Cricket visual retrieval/rendering paths remain unchanged. Live Cricket Option 7 · Text Cutout is a separate visual choice alongside the existing scraper/search/card options.
- Subject Cutout segmentation is never invoked by normal Top-5 rendering.
- No duplicate Live-only Subject Cutout implementation is permitted.

Cleanup rules:
- Delete obsolete Top-5 Option 3 and Subject Cutout code rather than layering patches around it.
- Keep the active implementation direct and small.
- Do not add new dependencies, wrappers, compatibility layers, fallback pipelines or parallel card renderers.
- Do not change Cricket behavior while iterating on Top-5.

### Production-line development rule

- The **production-line menu is the first menu in Test**.
- The three production-line choices are **Deep-Dive**, **Top-5**, and **OTD**.
- **Deep-Dive** carries the current approved Cricket and Niche Sports framework.
- **Top-5 production framework is WIP in Test; Option 3 Manual Fetcher is active, Option 7 Subject Cutout is being tested, and Option 8 Body Card is WIP. Live Cricket Option 7 · Text Cutout is active in the Cricket Visuals desk.**.
- **OTD** is **WIP**.
- All three production lines use the same seven-stage factory framework.
- The seven existing factory stages remain the stages for every production line; only the stage behaviour, inputs, outputs and presentation may differ by line.
- Build new production lines in **Test** first; Top-5 remains in Test/WIP until its current visual work is accepted. OTD remains Test-first.
- Do not create a separate stage pipeline, parallel model, duplicate metadata system or duplicate runtime architecture for a new line.
- **Do not touch, regress, replace or redesign the functionality of the current factory** while building these new production lines.
- Existing approved function behaviour and handoffs remain the baseline.
- New line-specific behaviour must be added only where required and must not change existing Deep-Dive/Cricket/Niche Sports functionality.
- Do not move a new line into Live until its Test implementation is accepted. Once accepted, Live must consume the same approved component contracts and visual treatments directly.

## Repository shape

Core files currently include:
```
app.py
topic_fetcher.py
script_writer.py
audio.py
visual_fetcher.py
visual_search.py
visual_generator.py
subtitles.py
renderer.py
uploader.py
tests/test_topic_fetcher.py
tests/test_script_writer.py
tests/test_audio.py
tests/test_subtitles.py
tests/test_visual_fetcher.py
tests/test_visual_search.py
tests/test_visual_generator.py
tests/test_renderer.py
tests/test_uploader.py
fonts/
requirements.txt
PROJECT_CONTEXT.md
README.md
.github/workflows/test.yml
.gitignore
```

Local-only runtime files:
```
.env
token.json
.audio_cache/
output/
```

## Important recent fixes

- Renderer preview regression fixed: opening preview now uses `PREVIEW_SUBTITLE_DATA` instead of an undefined `subtitle_data`.
- Scriptwriter now generates the strict 3–4 word renderer heading.
- Renderer consumes the approved Scriptwriter heading.
- Scriptwriter now generates hashtags and the public-upload comment in the same generation call.
- YouTube Upload QC was added with editable publish metadata and Public/Private upload lanes.
- Renderer text layout was corrected to use stroke-aware, screen-safe measurements so headline and subtitle characters do not clip at the canvas edges.
- Renderer headline wrapping now supports longer headlines across up to three lines.

## Current baseline

Treat the following as the authoritative working description of the cleaned Cricket Topic Fetcher (Function 01) and Cricket Scriptwriter (Function 02). Older notes below or elsewhere that conflict with this section are superseded.

### Clean-code baseline

Both functions have now been audited against their active callers and tests and cleaned in place.

- No unnecessary runtime wrappers or compatibility layers remain in either function.
- Single-use dispatch/query-construction helpers were removed where inlining made the flow clearer.
- Unused parameters, dead assignments and Niche-only constants/validators were removed from the Cricket Scriptwriter.
- Behaviour-bearing research, scoring, clustering, validation and provider adapters remain because they are actively used.
- The cleanup deliberately did not refactor working algorithms merely to reduce line count.
- The repository does not currently contain a production Python file that is safe to delete based on active imports/callers/tests. `fonts/OFL.txt` remains required as the bundled font licence.

### Function 01 — Cricket Topic Fetcher

The Topic Fetcher is a direct discovery/selection pipeline for the factory's Cricket and Niche Sports desks.

Active responsibilities:
- Build the appropriate query set for the selected profile or manual keyword.
- Fetch Google News concurrently.
- Prepare and filter candidate stories for freshness, story quality and profile relevance.
- Cluster duplicate/near-duplicate events without collapsing genuinely different stories.
- Score and select the requested number of cricket story/entity groups while respecting existing/previously returned groups.
- Use GDELT only as the cricket fallback when the primary fetch does not fill the requested batch.
- Keep the initial cricket batch at **20 unique tiles/groups**.
- A tile is an entity-based grouping for diversity, not a selectable item.
- For Cricket, if multiple qualifying headlines contain the same player name in the title, they share one tile. Country names, teams, competitions and known organisations are not treated as player entities.
- A tile can contain multiple different headlines/events. Each headline remains individually selectable in the Dashboard.
- A keyword search does not replace the existing 20 tiles; all returned keyword headlines are shown together under one additional Keyword tile, with each headline individually selectable.
- A solo headline with no detected player entity remains its own tile.
- The 20-tile limit is applied after the existing event clustering/selection logic, so multiple distinct stories about the same player can occupy one tile without being discarded as the same story.
- The returned Topic object remains the existing downstream handoff contract. It carries lightweight tile metadata and the tile's retained headline members; selecting an individual headline makes that exact Topic the active handoff to Scriptwriter.
- “Find 20 more” respects existing tile/entity groups so the same player group is not repeatedly used to fill later batches.
- The entity grouping is local string processing only. It adds no API/LLM call and does not change the Google/GDELT request count or worker model.
- Niche Sports retains its existing non-tile selection behaviour.

Cleanup baseline:
- No unnecessary runtime wrappers or compatibility layers remain in the Topic Fetcher.
- Single-use dispatch/query-construction helpers were removed where inlining made the flow clearer.
- Behaviour-bearing research, scoring, clustering, filtering and provider adapters remain because they are actively used.
- The repository does not currently contain a production Python file that is safe to delete based on active imports/callers/tests.

Status: **Approved / cleaned / entity tiles implemented / keyword tile implemented.**


### Cricket Pipeline Checkpoint — 6/10

Current overall cricket-line checkpoint: **6/10**.

This is the baseline for future Cricket pipeline changes. The current factory functionality is usable, but the latest Stats Card work exposed layout problems that are intentionally deferred.

Stats Card checkpoint:
- Player resolution has been hardened around the Cricsheet people registry and name variants.
- Stats Card crop selection now uses the existing Manual QC image pool and a dedicated 9:16 card-image crop.
- The completed card still has **text-overlap issues** in the lower information panel.
- A substantial portion of the lower half of the 1080 × 1920 card remains unused.
- Future Stats Card work should redesign the information hierarchy and space allocation intelligently rather than simply shrinking fonts or adding more text.
- Do not treat the current Stats Card visual layout as final/approved.
- Preserve the existing player-resolution and renderer/subtitle handoffs when revisiting the card layout unless a concrete regression requires otherwise.

Checkpoint rule:
- Use **Cricket line = 6/10** as the starting quality baseline for future Cricket pipeline improvements.
- Do not reopen already-approved Cricket components without a concrete regression or a clearly scoped improvement.

### Function 02 — Cricket Scriptwriter

The Cricket Scriptwriter is a direct four-slide writer with bounded research, one primary generation call and one hidden recovery rewrite.

Active flow:
1. Research the selected story from the source article and up to two related current reports when available.
2. Generate the complete package with `openai/gpt-oss-120b`.
3. Validate locally.
4. If generation/provider validation fails, make exactly one hidden complete rewrite with `openai/gpt-oss-20b`, using the exact failure reason.
5. Never expose an invalid draft to Manual QC.
6. Return the complete approved handoff package for Audio/Visuals and later Upload QC.

The current local validation enforces structural/downstream requirements:
- Exactly 4 scenes.
- Slide 1 contains at most 13 words, i.e. fewer than 14.
- Estimated narration is at most 32 seconds for the Scriptwriter handoff; Audio remains the final encoded-duration check for the production's sub-30-second target.
- The main subject name is present and appears in spoken narration.
- Headline is exactly 3–4 words.
- Exactly 3 title candidates are generated.
- Description is non-empty.
- Hashtags contain 3–5 entries beginning with `#`.
- A public-upload comment is present.
- Every scene contains `primary_entity`, `visual_intent`, `specific_search_prompt` and `sport_or_topic_category`.

Cleanup applied:
- Removed the unused Cricket-side `HOOK_MAX_SECONDS` constant.
- Removed Niche-only `GENERIC_OPENERS`, `RETENTION_BAIT` and the generic `validate_script()` from the Cricket module.
- Moved the Niche-only generic validator into `niche_sports_script_writer.py`, where it belongs.
- Removed the unnecessary generic `schema` argument from `_request()`; Cricket always uses the Cricket schema.
- Removed the unused `source` parameter from `validate_cricket_script()`.
- Removed the dead `result = None` exception-path assignment.

There is no separate hook-scoring layer, retention-scoring layer, metadata stage, wrapper runtime or manual AI-rewrite layer in the Cricket Scriptwriter.

Status: **Approved / cleaned.**

### Cricket + Top-5 runtime audit checkpoint
- Startup: `app.py` now loads the project `.env` explicitly instead of performing a directory search on every Streamlit rerun.
- Test Scriptwriter widget state is scoped to the selected story; stale headline/narration widget state is cleared on regeneration.
- Topic Fetcher hot pure-string/entity normalization functions use bounded LRU caches to reduce repeated tokenization, URL canonicalization and entity parsing during ranking/clustering.
- Cricket Scriptwriter fetches its up-to-two related reports concurrently after the selected story is researched.
- Audio approval handoffs use shallow copies because they only add one top-level approval flag.
- Renderer avoids re-resizing already-normalized frames, caches subtitle geometry per cue, and pre-renders static Top-5/Quote frames once per slide instead of rebuilding them for every video frame.
- Top-5 Test image previews use a bounded cache across Streamlit reruns.
- The audit deliberately did not modify the locked `visual_fetcher.py` implementation or its approved Cricket retrieval behavior.
- Full CI is the acceptance check for cleanup changes; no runtime claim is treated as final without validating the actual production/Test path.

### Test baseline after cleanup

- Python compile check passed.
- The earlier **113-test** baseline predates the subsequent Top-5 work and is no longer an authoritative acceptance count.
- Current acceptance is the full test suite for the active branch plus the actual Test dashboard path.
- Live Cricket Option 7 · Text Cutout regression coverage includes multiple-image switching, alternate mode/font/style/headline state, per-image crop-store reuse, polygon-editor presence, polygon preview rendering, and the Live visual-option surface. AppTest bypasses the browser-only inline editor registration while exercising the same Live Text Cutout Python path.
- Top-5 Option 7 must not be treated as approved or Live-ready until its own Test work passes the full suite and is manually verified in Test. This does not apply to Live Cricket Option 7 · Text Cutout, which is a separate Live visual choice.

When changing either Function 01 or Function 02, preserve the direct architecture and check both the relevant unit tests and the actual Test/Live dashboard handoff before merging.

