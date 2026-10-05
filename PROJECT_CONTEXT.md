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
1. **Top 5 cricket stories of the day** — **Test approved; Live implemented and now in production testing**
2. **On This Day** — **Test-first / WIP**

Top-5 Live uses the approved Top-5 writer, audio, visual treatments, renderer and uploader contracts. Live-specific code is limited to production orchestration: approval-triggered stage progression and concurrent automatic visual retrieval.

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

Top-5 has seven visual options:
1. Automatic Scraper.
2. Manual Scraper.
3. Real Image Search.
4. AI Generation.
5. Stats Card.
6. Quote Card.
7. Subject Cutout.

Top-5 Visual QC is independently testable in Test. The standalone screen exposes all seven options without requiring Scriptwriter or Audio approval. The six-slide production Visual QC appears only after a real Top-5 Scriptwriter handoff exists.

Every Top-5 image pool uses the same existing factory Crop / Reposition component. Crop state is stored per asset, visibly marked when applied, and the cropped bytes become the selected image used by preview, rendering and Subject Cutout analysis.

Option 7 · Subject Cutout is optional and user-selected. It uses local ZhengPeng7/BiRefNet_lite through the existing PyTorch/Transformers dependency stack. It is not used by ordinary Top-5 cards.

Subject Cutout is a dynamic image-composition treatment:
- Segment the foreground subject field.
- Measure the actual usable negative space above, below, left and right of that field.
- Aim to use roughly 80% of the chosen negative-space dimension by dynamically changing headline size and line grouping.
- A lower subject with substantial space above uses a large horizontal headline in that upper negative space.
- An upper subject with substantial space below can use the lower negative space in the same way.
- A left/right subject uses the opposite-side negative space with a large, normally oriented vertical headline stack. The renderer groups words intelligently across lines rather than creating one-word-per-line text just to look vertical.
- A central subject with useful space on both sides uses a large horizontal headline spanning across the subject. Type begins in the left copy space, disappears behind the subject and reappears on the right.
- Multiple subjects share one foreground mask, so one headline can disappear behind both subjects and naturally remain visible through any genuine gap between them.
- The headline is scaled for legibility first. Subject overlap is a depth treatment, not the optimization target.
- Weak segmentation falls back to ordinary editorial typography rather than producing a Subject Cutout composition error.

No wrappers, duplicate pipelines, broad visual panels, universal gradients, transparent/faded type or headline motion are part of this design.

Status: Test implementation / visual refinement in progress.

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
- Use the established adaptive opaque editorial treatment.
- No broad scrim, transparent/faded type, universal gradient, permanent border, decorative dots/lines or headline motion.
- Logo remains top-right; source label remains bottom-right.

Option 7 · Subject Cutout:
- Uses local BiRefNet foreground segmentation only when selected.
- The renderer makes a composition decision from the actual photograph rather than reusing one fixed headline position or font size.
- It measures the available negative space and dynamically scales the headline to occupy roughly 80% of the selected copy dimension.
- Lower subjects favor large upper negative space; upper subjects can favor lower negative space.
- Side subjects favor the opposite-side negative space with a large balanced multi-word vertical stack.
- Central subjects favor a large horizontal headline spanning both sides of the subject.
- Multiple subjects are handled by one shared foreground mask, so the crossing headline sits behind every subject and remains visible through real gaps.
- The headline must remain large enough to read even where a foreground subject hides part of a glyph.
- Subject Cutout normally suppresses body copy so the headline can own the composition.
- The original image is composited above the opaque headline only at the actual mask/glyph intersection.
- Weak segmentation falls back to normal editorial layout instead of failing.

Crop:
- Top-5 image pools use the factory Crop / Reposition component.
- Applied crop is the exact framing passed to preview, selection, rendering and Subject Cutout.

Status: Top-5 Subject Cutout test implementation / visual refinement in progress.

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

- Top-5 Visuals Test remains independently runnable with exactly seven visual options: Automatic Scraper, Manual Scraper, Real Image Search, AI Generation, Stats Card, Quote Card and Subject Cutout.
- The existing Crop / Reposition component remains the only crop path. Its cropped result is handed directly to the selected card renderer.
- **Option 3 · Real Image Search is a fresh card implementation.** It is a static full-bleed 9:16 editorial card with no subject detection.
- Option 3 scans the actual frame for quiet/negative regions instead of using the old fixed safe band or a generic composition score. Candidate regions cover the frame, including genuine top, upper, middle, lower and side spaces.
- Option 3 first measures local visual busyness, converts that into an allowable headline-size ceiling, then chooses the **largest headline that physically fits** that region. Quiet space therefore directly permits materially larger type; busy imagery naturally restricts type size.
- Option 3 uses **Oswald** for the headline. Headline line breaking is solved from the actual measured text widths rather than inherited fixed-size wrapping.
- Option 3 body copy remains readable and visible beneath the headline when it fits. Body text uses the same editorial language as Option 7—opaque type, controlled outline and strong soft shadow/fade—while remaining sized for comfortable reading.
- **Option 7 · Subject Cutout is a fresh card implementation and is headline-only.** The Test UI hides the body field and the renderer ignores any upstream body data for this option.
- Option 7 runs the existing local **ZhengPeng7/BiRefNet** inference path only when Option 7 is selected. No new Python dependency or runtime layer is introduced. The current general BiRefNet model is retained rather than adding another segmentation model.
- Option 7 identifies separate connected foreground components from the returned matte before deciding whether a composition is centered. The renderer no longer treats a multi-player image as one undifferentiated subject box for composition decisions.
- For a centered subject or centered group of players with real space on both sides, Option 7 constructs a **cross-subject headline** that starts outside the leftmost subject, passes behind the foreground subject(s), and exits outside the rightmost subject.
- The headline is rendered into a real pixel mask for composition analysis. Candidate positions are accepted only when the actual headline pixels are visible outside both sides and a controlled portion intersects the foreground matte.
- With multiple players, the union of the real foreground components is used for occlusion. Headline pixels naturally remain visible through genuine gaps between players. The headline is never intentionally positioned so that it starts inside a gap.
- For non-centered subjects, Option 7 uses the strongest actual negative space around the foreground. Side compositions are allowed to become tall editorial stacks with **one or two large words per line**, rather than being forced into the normal two-line headline limit.
- Foreground restoration happens after text rendering, so the player visibly sits above the headline. The occlusion pass targets the headline pixels and their shadow/stroke only.
- Option 7 never silently falls back to the normal Option 3 card. Extraction/layout failure is surfaced in Test.
- The old Top-5 card architecture—fixed 620px headline-safe start, indirect size scoring, global subject bounding-box overlap scoring, repeated subject-layout helpers and silent normal-card fallback—is deleted.
- Regression tests now target user-visible contracts: Option 3 must choose the largest fitting headline in genuinely quiet space and a smaller one on busy imagery; Option 7 must cross centered subjects, preserve multi-player gaps, restore foreground pixels over the headline and remain headline-only.
- Test and Live continue to consume the same card renderer/asset contract. Option 7 remains an explicit visual-option choice and is never automatically applied to normal Top-5 cards.

Status: **Option 3 and Option 7 card renderers have been rewritten from scratch on isolated branch rewrite-top5-option3-option7; validation is still required before any promotion to main.**
### Production Line 03 — On This Day

Purpose:
- Produce a daily sports-focused historical package based on events associated with the current calendar date.
- It uses the same seven factory stages as every other production line.
- Historical stories must be grounded in verifiable source material and clearly separated from current-day news.
- The date matching, story selection, script structure, visual treatment and publishing details will be designed in Test first.

Status: **Planned / Test framework WIP.**

### Test / Live architecture audit

The factory must have one shared implementation of each production stage. Test and Live may differ in presentation and in whether an already-approved stage is triggered manually or automatically, but they must not drift into different stage logic, handoff contracts or asset contracts.

Current audit state:
- Topic Fetcher, Scriptwriter, Audio, Visuals, Subtitles, Renderer and YouTube Upload remain separate modules with shared underlying contracts.
- Test and Live still have distinct orchestration because Test is the proving ground and Live is the automated production lane.
- Test and Live Top-5 visuals consume the same approved image and assignment contracts.
- Top-5 visual attachments use one direct assignment path for Automatic Scraper, Manual Scraper, Real Image Search, AI Generation, Stats Card, Quote Card and the Test-only Subject Cutout treatment.
- The Top-5 renderer uses the full-bleed photograph as the primary visual field. Normal cards use adaptive copy-space placement; Subject Cutout uses the local foreground mask to choose a bottom/top, side/vertical, center/cross-subject or negative-space fallback composition.
- Subject Cutout targets roughly 80% use of the available negative space and dynamically changes headline size and line grouping from the actual photograph.
- Text treatment remains opaque editorial type chosen from the image luminance, with a restrained directional shadow and thin contrasting outline. There is no broad photo wash, full-frame panel or transparent text.
- Optional Subject Cutout uses ZhengPeng7/BiRefNet_lite locally through the existing PyTorch/Transformers dependencies. The model runs only when the user selects Option 7; normal Top-5 rendering does not invoke it. Foreground extraction is cached per source image, and the normal factory crop is applied before analysis.
- Body copy is rejected when it cannot fit at the minimum readable size. Renderer exposes the strict maximum word count; Visual QC shows the rejected body as editable copy and offers deterministic local compression to that cap.
- Test and Live continue to consume the same shared Top-5 renderer implementation.
- No wrapper, compatibility layer or duplicate Subject Cutout pipeline was introduced.
- Existing Deep-Dive/Cricket/Niche Sports behavior is not changed by the Top-5 typography work.
- Live Top-5 starts automatic visual crawling at Stage 1 approval and streams page results into its existing Visual QC state.
- Test remains manually stageable; Live remains approval-triggered.

Cleanup rules:
- Do not add wrappers, compatibility layers, duplicate pipelines, parallel metadata systems or abstraction layers that make the code harder to follow.
- Prefer one direct stage implementation with small explicit mode/presentation differences over two copies of the same logic.
- Preserve the existing seven-stage order and all approved production requirements.
- Do not change retrieval algorithms, story scoring, Scriptwriter generation requirements, audio behavior, subtitle behavior, renderer design or upload behavior unless required to remove a concrete Test/Live mismatch.
- Test must remain the place where new behavior is designed and manually approved before Live uses it.
- Live may automate already-approved transitions, but it must consume the same approved handoffs as Test.
- Each cleanup step must be checked against the relevant tests and the actual Test/Live handoff path before merge.

Status: **Architecture cleanup in progress.**

### Production-line development rule

- The **production-line menu is the first menu in Test**.
- The three production-line choices are **Deep-Dive**, **Top-5**, and **OTD**.
- **Deep-Dive** carries the current approved Cricket and Niche Sports framework.
- **Top-5 production framework is approved; the dynamic Oswald editorial typography and optional local Subject Cutout remain in Test until the user approves them**.
- **OTD** is **WIP**.
- All three production lines use the same seven-stage factory framework.
- The seven existing factory stages remain the stages for every production line; only the stage behaviour, inputs, outputs and presentation may differ by line.
- Build new production lines in **Test** first; Top-5 has completed that gate and is now being tested in Live. OTD remains Test-first.
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
- Full test suite passed: **113 tests**.
- Main branch CI passed after the cleanup merge.
- The cleanup was intentionally limited to dead-code removal/simplification; generation rules and downstream handoffs were not redesigned as part of this cleanup.

When changing either Function 01 or Function 02, preserve the direct architecture and check both the relevant unit tests and the actual Test/Live dashboard handoff before merging.

