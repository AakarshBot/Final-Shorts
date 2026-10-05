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

The Visuals desk contains four independent options:
1. Automatic scraper/crawler.
2. Manual scraper using real-image sources.
3. Manual real-image search.
4. Manual AI image generation.

Key rules:
- Visual retrieval remains manual-review driven.
- No automatic visual-generation loop.
- No AI visual-verification gate is required in the completed Visuals phases.
- Option 1 is the automatic story-page/publisher-image crawler.
- Option 2 performs manual-query retrieval, image download and basic image validation/deduplication, then displays the pool.
- Option 3 is manual real-image search across configured sources.
- Option 4 is manual AI image generation across configured providers.
- Option 2 sources include Commons, DuckDuckGo, Wikipedia, Openverse and configured Pixabay/Pexels/Unsplash APIs.
- Current AI providers include Hugging Face Inference Providers with FLUX.1-schnell and Cloudflare Workers AI with FLUX.1-schnell.

Status: **Approved.**

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

Canonical style:
- **Editorial Highlight**.
- Large Oswald Bold headline.
- Headline dynamically fits and wraps to **one, two or three lines**.
- Headline layout uses an explicit screen-safe margin and stroke-aware bounding boxes.
- Long 3–6 word headings are supported through wrapping and dynamic font fitting.
- A word that cannot fit within the safe width is rejected instead of being allowed to clip.
- Moving blue/yellow brand marker remains part of the opening treatment.
- Subtitles use a large bold sans-serif, dark outline, white inactive words and yellow active word.
- Subtitle layout uses stroke-aware measurements and a dedicated screen-safe margin.
- No caption background capsule.
- Logo is the real local `logo.png`, top-right.
- Source label is plain text, bottom-right.
- No permanent border, glass panel, decorative dots/lines or universal Ken-Burns effect.
- When the opening headline is enabled, subtitles remain hidden until the 1.15-second headline window ends.

Renderer test:
- Uses filler content only for the isolated preview desk.
- The test reads the approved Scriptwriter heading when that handoff is available.
- The Renderer still supports a fallback test headline when no approved Scriptwriter handoff exists.

Status: **Approved.**

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

### Top-5 visual design — current Test state

- Top-5 uses a static 9:16 full-bleed editorial photograph.
- English headlines use bundled **Barlow Condensed Black**, rendered **ALL CAPS**. Normal cards use dynamic horizontal editorial wrapping. Body copy uses **Barlow Regular**.
- Normal Top-5 composition evaluates the actual photograph for copy space, local contrast and vertical placement inside the editorial safe area **y=620–1650**. It does not force every photograph into a fixed bottom-third position.
- Text remains opaque. Readability uses a restrained directional shadow and thin contrast-aware outline; there is no transparent/faded type, broad scrim, universal panel, permanent border, decorative dots or headline motion.
- Body copy can vary in length but must fit the readable card area.
- Every Top-5 image-selection pool uses the factory's existing **9:16 Crop / Reposition** control. A crop is stored per selected asset, shown as **CROP APPLIED**, used for the image preview and passed into the final renderer. Subject Cutout analyzes the cropped framing, not the discarded original framing.

### Top-5 standalone Visuals Test mode

- Stage 04 · Visuals is independently testable without Scriptwriter or Audio approval.
- It exposes exactly **seven options**: Automatic Scraper, Manual Scraper, Real Image Search, AI Generation, Stats Card, Quote Card and Subject Cutout.
- The standalone page stays independent when there is no approved Scriptwriter handoff; it must not fall through into the six-slide QC branch or reference an undefined script.
- Options 1–4 retrieve image pools. The user selects an image. Options 5–6 reuse an image pool for card treatments. Option 7 reuses the current image pool and renders the Subject Cutout treatment locally.
- The standalone image pool uses the same crop/reposition control as the normal factory image pools, and Option 7 previews the **actual composed card** rather than displaying only the raw source image.
- A selected cropped image becomes the current working image, so the rendered preview and the Subject Cutout mask both use exactly the framing the user approved.

### Top-5 Subject Cutout — active Test experiment

- **Option 7 is optional and user-selected.** Normal Top-5 rendering never runs subject extraction.
- Subject Cutout continues to use **ZhengPeng7/BiRefNet_lite** locally through the existing PyTorch/Transformers dependency stack. Model weights and per-image masks are cached locally; there is no hosted inference call.
- The composition is **image-driven**, not a fixed style. The extracted foreground mask is converted into a subject bounding geometry and the renderer searches headline size, wrapping, direction, position and overlap against that geometry.
- **Subject on one side:** the headline uses the opposite-side copy space as the primary text area. It becomes a large, normally oriented **vertical stacked headline**, with dynamic word grouping across roughly 2–4 lines. It does not use the crude “one word per line” treatment. A small controlled intrusion toward the player is allowed so the foreground can naturally occlude a small portion of the type.
- **Subject in the middle:** the renderer actively searches for a **large horizontal headline crossing the player**. It prefers one line when the complete headline can remain readable at a large size. The text begins in left copy space, travels behind the player for a controlled portion of the headline, and exits into right copy space. A second line is used only when the complete headline cannot remain readable as one strong horizontal unit.
- The crossing composition is selected by searching actual image geometry rather than pinning text to the bottom. The renderer scores how much readable type remains on both sides of the subject and how much of the headline intersects the subject.
- The foreground player is composited **above the actual headline glyphs**, not above the entire text rectangle. Only the intersection of the BiRefNet foreground mask and the headline glyph mask is composited back over the type.
- The system deliberately avoids forcing the effect onto images where the subject geometry does not support it. It searches multiple thresholds of the soft BiRefNet mask for a usable foreground geometry instead of rejecting an image because one threshold is too broad or too narrow.
- Subject-aware candidates are evaluated in descending headline scale and then for readable wrapping, controlled overlap and body-copy fit. If a particular candidate cannot accommodate the body, the renderer tries other candidate layouts rather than immediately failing.
- This remains **Test-only** until explicit visual approval.

### Top-5 status

- Test pipeline/framework: approved.
- Seven-option standalone Visual QC: implemented.
- Normal dynamic editorial typography: implemented.
- Factory crop/reposition behavior: restored across Top-5 image-selection steps.
- Optional Subject Cutout: **under active visual refinement in Test**.
- Live promotion of the Subject Cutout treatment remains blocked until explicit Test approval.

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
- The Top-5 renderer uses the full-bleed photograph as the primary visual field. Normal cards use dynamic copy-space scoring; Subject Cutout uses the local foreground mask to reason about subject position before choosing the headline composition.
- Subject Cutout uses two image-driven compositions: a large vertical headline stack in the strongest opposite-side copy space for side-positioned subjects, or a large horizontal headline crossing a centered subject with controlled overlap.
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
- **Top-5 production framework is approved; the dynamic Barlow editorial typography and optional local Subject Cutout remain in Test until the user approves them**.
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

