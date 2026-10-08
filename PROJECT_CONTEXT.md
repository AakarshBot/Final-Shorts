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
- Card Studio and other visual sub-functions are independently testable in Test. They must not be blocked merely because an earlier pipeline stage is unapproved. Card Studio receives the existing image pool or a manually supplied test image and leaves final approval entirely to Manual QC.
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
3. **YouTube Search Trends** — **Test + Live / search-opportunity rebuild in validation**

Top-5 is currently Test-only / WIP. **Card Studio is the single card entry point in Top-5 Test.** Text Subject Cutout is the only approved card type. Cricket and YT Trends use the same shared Card Studio; Top-5 Live remains retrieval-only and does not expose Card Studio.

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

Visual retrieval and card composition share one Visuals stage.

The standard single-story Visuals desk has five entry points:
1. Automatic Scraper.
2. Manual Scraper.
3. Real Image Search.
4. AI Generation.
5. Card Studio.

Top-5 Test uses the same four retrieval options plus **Option 5 · Card Studio**. Top-5 Live remains retrieval-only and uses Options 1–4.

Card Studio is one manual-QC entry point. It does not search for images itself; it reuses the existing image pool or a manually supplied test image. In Test it currently exposes:
1. **Text Subject Cutout** — approved.
2. **Stat Highlight** — WIP.
3. **Quote / Reaction** — WIP.
4. **Head-to-Head** — WIP.
5. **Key Fact / Milestone** — WIP.

Only Text Subject Cutout is approved for Live. New card types stay Test-only until the user approves their actual 1080 × 1920 output. No automatic approval gate is added.

The approved Text Subject Cutout / Manual Subject Cutout editor remains the shared implementation. Its polygon editor, crop/reposition flow, negative-space and behind-subject modes, Text Size control, line-break preview, renderer behavior and handoff remain shared across surfaces. Deep-Dive Cricket now opts into a dedicated polygon-flow layout inside that shared renderer; other Card Studio surfaces keep the existing layout behaviour.

Card Studio WIP behavior:
- Every WIP card type opens with concrete default test content in every editable field, so the card can be rendered immediately for visual evaluation.
- The image picker shows the full available image pool as actual image previews, not title-only choices.
- Every displayed image has the existing **Crop / reposition** control. Cropping is applied before the image is selected for the Card Studio composition, and the cropped bytes are reused for the card render.
- WIP cards use the factory's existing subject-aware foreground mask only to choose better negative-space placement for text. There is no text-behind-subject restoration, subject cutout, or hidden-text treatment in these WIP cards.
- The subject-aware placement is intentionally basic: it scores a small set of safe text positions and prefers the one with less detected foreground coverage while keeping the original card hierarchy.
- Quote / Reaction has been rewritten as a stronger sports-editorial quote treatment using the factory's condensed typography, accent rule and image-first composition. It is still WIP and requires manual approval.
- Head-to-Head supports both **One image** and **Two images**. Two-image mode lets the user manually choose which pool image is Image 1 and Image 2, then choose **Vertical** or **Horizontal** split. Each side keeps its own name and corresponding metric values.
- Single-image Head-to-Head keeps the editorial split-stat treatment but now participates in the same basic subject-aware headline placement.
- Card Studio continues to create static 1080 × 1920 frames; the production Renderer does not animate normal headline/subtitle layers over a completed Card Studio frame.
- No new package or external graphics framework is introduced. The existing Pillow + renderer stack remains the implementation.

**Global publisher discovery:** The Automatic Scraper and Manual Scraper search publisher results without a regional search lock. DuckDuckGo text/news discovery uses the no-region `wt-wt` setting, and the Google News RSS lane no longer requests the India-specific `gl=IN`, `ceid=IN:en` feed.

Relevant results from established international publishers are ranked ahead of other matching publisher pages, including Reuters, AP, BBC, ESPN, Sky Sports, The Guardian, Eurosport and major international sports governing bodies. This is a priority, not a whitelist: relevant Indian, regional and other local publishers remain eligible and can still fill the pool. The original selected article remains the first automatic page.

Both Automatic and Manual Scraper therefore use the same global-aware publisher discovery path without a second scraping architecture or new dependency. Manual Real-Image Search remains a separate provider pool and is already not region-locked.

Crop / Reposition remains the existing shared crop path. Cropped bytes are the exact bytes passed to previews, selection and Text Subject Cutout analysis.

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
Renderer v2 is the single shared Test/Live renderer on main.

- One direct renderer implementation is used by Test and Live; there is no separate encoder path.
- Frames are composed with Python/Pillow and encoded with FFmpeg. MoviePy is not used.
- Final output is 1080 × 1920 progressive H.264 High Profile, 4:2:0, two B-frames, closed GOP, GOP of half the frame rate, constant frame rate, BT.709, Fast Start and CRF 18.
- Final audio is AAC-LC, stereo, 48 kHz at 192 kbps. Approved audio scenes are concatenated and loudness-normalized inside the same FFmpeg complex audio filtergraph to approximately -14 LUFS / -1.5 dBTP; -af is not applied to the already-filtered audio output.
- Normal photographic visuals use deterministic story/asset-seeded push and pan motion. Completed Card Studio frames and Top-5 editorial cards are static.
- Card Studio rendered frames are treated as final 1080 × 1920 visual inputs. Production rendering adds the existing logo/source overlays according to the normal flags.
- Text Subject Cutout remains intentionally overlay-free and hands its already-rendered frame directly to the renderer.
- Existing headline, subtitle, Top-5, Card Studio and Text Subject Cutout behavior remains direct renderer functionality with no wrappers or duplicate implementations.
- The renderer requires the approved Scriptwriter, Audio and Visuals handoffs, plus valid subtitles for non-Top-5 production.
- Card Studio and Text Subject Cutout suppress the normal headline/subtitle drawing path by handing the renderer a completed static frame.
- The renderer contains no detector-evasion, metadata-fingerprinting, pixel-perturbation or similar mechanism intended to bypass platform systems.

Status: Active / shared Test + Live renderer. Audio filter conflict is fixed; full CI validation is part of the current Card Studio change.
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

- Top-5 Visuals Test remains independently runnable with exactly five dashboard choices.
- Top-5 Option 1 is **Automatic Scraper**.
- Top-5 Option 2 is **Manual Scraper**.
- Top-5 Option 3 is **Manual Fetcher**: manual query → real-image provider results → existing image pool. It does not render card typography.
- Top-5 Option 4 is **AI Generation**.
- Top-5 Option 5 is **Card Studio**, the single card entry point.
- Card Studio Test exposes five card types: **Text Subject Cutout** (approved), **Stat Highlight** (WIP), **Quote / Reaction** (WIP), **Head-to-Head** (WIP), and **Key Fact / Milestone** (WIP).
- Text Subject Cutout is implemented by the existing shared Manual Subject Cutout editor/renderer. Cricket Test + Live, YT Trends Test + Live, and Top-5 Test use that same implementation; it is not reimplemented inside Card Studio.
- The other four Card Studio types are static 1080 × 1920 Pillow frames, manually entered and manually QC'd in Test. They are not Live-approved.
- Card Studio reuses the existing visual pool or the standalone Top-5 test image. It does not perform its own image retrieval.
- The renderer treats a completed Card Studio frame as a static visual input and does not add normal headline/subtitle animation on top of it. Normal production logo/source overlays remain controlled by the existing renderer flags.
- Top-5 Live remains retrieval-only and exposes Options 1–4. Card Studio is not exposed there until a Test card type is approved.
- The superseded standalone card implementations are deleted; no compatibility aliases or duplicate factories remain.
- Top-5 Test remains WIP and is not being promoted to Live by this change.

### Production Line 03 — On This Day

Purpose:
- Produce a daily sports-focused historical package based on events associated with the current calendar date.
- It uses the same seven factory stages as every other production line.
- Historical stories must be grounded in verifiable source material and clearly separated from current-day news.
- The date matching, story selection, script structure, visual treatment and publishing details will be designed in Test first.

Status: **Planned / Test framework WIP.**

### Shared Text Subject Cutout · Card Studio

**Text Subject Cutout** is the approved card type backed by the existing manual subject-cutout implementation. It is exposed through Card Studio in Cricket Test/Live, YT Trends Test/Live, and Top-5 Test. Top-5 Live does not expose Card Studio yet.

There is exactly one implementation:
- One shared editor in `app.py`.
- One shared renderer in `renderer.py`.
- Card Studio routes the approved Text Subject Cutout type directly into that implementation.
- No separate subject-cutout visual option or duplicate pipeline remains.

Feature contract:
- English-only.
- No subtitles.
- One editable headline, defaulted from the approved/script headline as appropriate.
- Two modes: Negative Space and Behind Subject.
- Existing approved fonts and styles remain shared everywhere.
- 1080 × 1920 output.
- Editable polygon text area with eight default points including four edge midpoints.
- Individual vertices can be dragged.
- The whole polygon can be dragged rigidly inside the frame.
- Clicking an edge adds a point.
- The polygon is the complete text box. For the requested font size, the renderer finds every valid word line-break combination that fits the polygon and previews them all. The user can choose a valid layout for the slide.
- Deep-Dive Cricket and YT Trends use polygon-flow mode: the text block starts 2px inside the polygon's top boundary; each line uses the polygon's left/right span at that line's vertical position, starts 2px inside the available left edge, and stays inside the available right edge. As more lines are required, the text indentation follows the polygon vertically rather than centering the text block.
- Top-5 keeps the existing shared Text Subject Cutout layout behaviour; polygon-flow is not enabled there.
- Deep-Dive Cricket and YT Trends polygon-flow text is never horizontally or vertically re-centered.
- Negative Space never runs BiRefNet.
- Behind Subject uses the existing BiRefNet model and restores detected foreground subjects, including multiple subjects and genuine gaps.

State/render behavior:
- Polygon, headline, font, style and Text Size edits do not regenerate the rendered frame until Render Now.
- Preview-all-line-breaks is explicit and does not silently shrink the requested font size.
- Render Now stores the current cutout configuration and completed static frame for Manual QC.
- The production handoff consumes the completed frame together with the cutout configuration.
- The cutout frame itself has no logo, source label, permanent headline overlay or subtitles.

Status: **Approved card type. Keep this implementation shared between Test and Live.**

Fragment audit: Manual Subject Cutout remains the only `@st.fragment` in `app.py`. Its rendered-state-dependent handoff controls live inside the fragment. The crop editors remain self-contained dialogs.

### Production-line development rule
### Production-line development rule

- The **production-line menu is the first menu in Test**.
- The four production-line choices are **Deep-Dive**, **Top-5**, **OTD**, and **YouTube Search Trends**.
- **Deep-Dive** carries the current approved Cricket and Niche Sports framework.
- **OTD** is **WIP**.
- **YouTube Search Trends** is **Test + Live / rebuilt and awaiting validation**. It is a sports-focused Topic Fetcher source. Selecting **YT Trends** fetches current YouTube search signals, removes generic query-intent and sports-only terms, validates the remaining signals against relevant news in the last 24 hours in Asia/Kolkata, and returns one mixed pool of up to 20 news-backed story opportunities. The UI does not segregate the trends by sport, country or market. Selecting one story uses the cleaned story keyword and the existing downstream Scriptwriter path; the raw YouTube query is not handed downstream. Any downstream Cricket/Niche classification is internal to the selected trend and is not a dashboard choice.
- All four production lines use the same seven-stage factory framework.
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



### Function 01B — YouTube Search Trends

Status: **Test + Live / search-opportunity rebuild in validation.**

- YT Trends remains a shared Topic Fetcher source, not a separate downstream production architecture.
- The collector uses Google Trends with the YouTube property and YouTube autocomplete with the existing sports seed set. Primary sports seeds use India (geo=IN, en-IN) for Indian-audience weighting; the international-cricket seed remains global.
- The trend board remains one unsegregated pool; it does not expose sport, country or market categories.
- Each result keeps two distinct values: the **exact YouTube search query** that generated the signal and the cleaned **story subject** used to find current news.
- Generic query-intent terms are removed only from the cleaned story subject. The original search query is preserved as the search-intent target.
- Sports-only queries are rejected; ordinal forms such as t20th are normalized before filtering.
- Google Trends `Top` / `Rising` signals and YouTube autocomplete are treated as discovery evidence, not absolute search-volume counts.
- If the first requested batch does not produce enough news-backed opportunities, the fetcher validates additional candidates up to the larger of twice the requested limit or 40 candidates. Lower-priority YouTube autocomplete suggestions can also backfill the candidate pool.
- Validation remains an exact rolling 24 hours in Asia/Kolkata. Only candidates with at least one relevant current article enter the board.
- Each trend caches its validated Topic articles. Selecting a trend uses those cached Topics directly; it does not perform a second keyword-only search.
- “Find up to 20 more” uses the same retrieval path and can append additional current Topics while excluding already returned events.
- The board is explicitly ranked. It displays the rank, search target, signal type, news count and an **Opportunity** score. The score is a relative board-ranking number, not search-volume data.
- Selecting a trend preserves the exact search query separately from the selected real news Topic.
- **Scriptwriter handoff:** every YT Trends story uses the Universal Niche Sports + YT Trends Scriptwriter, including cricket stories. The protected Cricket Scriptwriter is never used for YT Trends.
- The Universal Scriptwriter receives the preserved search query as packaging context. It uses that query to shape the SEO/Search title and story-specific description naturally, without a new hard validator or keyword stuffing.
- The generated universal script retains the `search_query` field for downstream handoff/audit.
- The YT Trends Visuals stage uses the shared single-story Card Studio and exposes the approved Text Subject Cutout card in both Test and Live.
- After selection, Live moves into the existing single-story Script stage and then uses the existing Audio + Subtitles → Visuals + Render → Upload flow.
- Test uses the same Universal Scriptwriter handoff for YT Trends and then its existing downstream Test stages.
- No second YT Trends Scriptwriter, metadata stage, renderer path or upload path is introduced.
- No new Python dependency is introduced.
### Cricket Pipeline Checkpoint — 6/10

Current overall cricket-line checkpoint: **6/10**.

This is the baseline for future Cricket pipeline changes. The established Cricket functionality remains usable. New card work now lives under Card Studio so Test can prove each visual type before any Live promotion.

Card Studio checkpoint:
- Text Subject Cutout remains the only approved card type. The shared Subject Cutout implementation is preserved, with polygon-flow enabled only for Deep-Dive Cricket and YT Trends.
- Stat Highlight, Quote / Reaction, Head-to-Head and Key Fact / Milestone remain Test-only WIP Card Studio types.
- All WIP card fields open with usable default test values.
- WIP Card Studio shows the full image pool with real image previews and the existing crop/reposition control before image selection.
- WIP cards use the existing subject-aware foreground mask only for simple negative-space text placement. They do not hide text behind subjects.
- Head-to-Head supports one-image and two-image modes. Two-image mode has manual Image 1/Image 2 assignment plus manual Vertical/Horizontal split selection.
- Quote / Reaction is an editorial redesign and remains unapproved until the user manually reviews its output.
- No WIP card type is promoted to Live until the user approves the actual rendered frame.

Checkpoint rule:
- Use **Cricket line = 6/10** as the starting quality baseline for future Cricket pipeline improvements.
- Do not reopen already-approved Cricket components without a concrete regression or a clearly scoped improvement.

### Function 02 — Scriptwriters

#### Cricket Scriptwriter — protected / read-only

The existing Cricket Scriptwriter remains untouched by the Niche/YT Trends rewrite.

- Normal Cricket production continues to use the existing Cricket writer exactly as it does today.
- Its prompt, schema, validation, research flow, metadata package, quote handling, manual-edit handoff and downstream behavior are outside this change.
- Do not modify this writer as part of Universal Niche Sports or YT Trends work.

Status: **Protected / unchanged.**

#### Universal Niche Sports + YouTube Search Trends Scriptwriter

The old Niche Sports writer was deleted and replaced from scratch with one direct universal sports writer.

Scope:
- Normal Niche Sports production uses this writer.
- YouTube Search Trends uses this writer regardless of whether the selected story happens to be cricket.
- The normal Cricket production line never uses this writer.
- Top-5 never uses this writer.

Core flow:
1. Read the selected article and build a full research packet with the primary article plus up to two related reports when available.
2. Generate the complete package with `openai/gpt-oss-120b`.
3. Validate the generated package locally before Manual QC.
4. If the first draft fails, make exactly one hidden complete rewrite with `openai/gpt-oss-20b` using the exact failure.
5. Never expose an invalid generated draft to Manual QC.

Universal narration contract:
- 3–5 spoken slides are allowed.
- Two-slide scripts are forbidden.
- Four slides are preferred when they are the cleanest complete story.
- For Universal Niche Sports and YouTube Search Trends, Generate Script first produces exactly three research-backed story angles. The user selects one of those angles or writes a Custom Angle before the actual script is generated. The selected angle is authoritative and remains attached to the script as story_angle; the writer must build the Short around that lens instead of reverting to the most obvious event/result summary.
- Slide 1 contains fewer than 14 words.
- Total narration is at least 18 seconds and strictly under 30 seconds.
- The writer targets a 50–74 word narration envelope as the generation proxy for the 18–<30 second window.
- The minimum duration must come from useful story information, context, evidence or consequence, never padding.
- Every slide must add genuinely new information.

Editorial behavior:
- The writer reads the full research packet and creates its own editorial version rather than mechanically paraphrasing the source.
- The actual sport/topic is identified from the evidence; there is no cricket-default framing.
- Exact named subjects are resolved from descriptors. When a story/headline says a "legend", "champion", "star", "defending champion", "world number one" or similar label, the writer identifies the actual person/team from the research and names them naturally in narration.
- The main subject is a required field and must appear in spoken narration.
- Editorial value comes from selecting the strongest development, explaining concrete significance and closing with the latest confirmed status, without inventing opinion or facts.
- No generic intros, viewer-directed retention bait or disposable filler. Phrases such as "wait till the end", "stay tuned", "don't scroll", "you won't believe this", "here is the latest" and similar bait are explicitly prohibited and locally rejected.
- The writer must respect each sport's actual event structure and terminology.

Publish metadata and downstream handoff:
- `headline`: exactly 3–4 words.
- `titles`: exactly 3 candidates using the existing SEO/Search, Consequence/Why It Matters and Curiosity angles.
- `seo_description`: concise story-specific description.
- `hashtags`: 3–5 relevant hashtags.
- `comment`: concise story-specific discussion question.
- `quote`, `quote_attribution`, `quote_slide`: faithful optional quote treatment attached to an existing narration slide.
- Every scene retains `primary_entity`, `visual_intent`, `specific_search_prompt` and `sport_or_topic_category` for the existing Visuals handoff.
- The existing Audio, Visuals, Renderer and Upload functions consume the same Scriptwriter handoff shape; no new downstream dependency or stage is introduced.
- Quote-slide handoff now follows the actual generated scene count, including a possible fifth slide.

YT Trends handoff:
- Selecting a YT Trends headline enters the normal Live Script stage.
- YT Trends does not return to its Topic Fetcher after selection.
- The selected real news Topic and the preserved raw YouTube search query are handed separately to the universal Scriptwriter.
- The search query is packaging context; the real news Topic remains the factual source.
- The rest of the Live pipeline remains the existing single-story flow.

No new Python dependency is introduced. The universal writer is self-contained and no longer imports implementation helpers from the protected Cricket writer.

Status: **Rewritten from scratch / ready for Test validation.**

### Cricket + Top-5 runtime audit checkpoint
- Dashboard execution is prompt-driven: no story, script, audio, subtitle, render or upload function may start merely because Streamlit reran.
- The only intentional automatic production action is the approved automatic visual scraper after its upstream manual approval; it runs once for that handoff and must not use polling reruns.
- Test and Live manual controls are state-driven. A widget interaction may redraw its owning fragment, but must not refresh the full dashboard unless an explicit stage/action transition requires it.
- Text Subject Cutout uses exactly one shared fragment and one shared renderer across Top-5 Test Card Studio, Cricket Test + Live Card Studio, and YT Trends Test + Live Card Studio.
- The shared renderer exposes one direct polygon-flow option, enabled only by the Deep-Dive Cricket and YT Trends Test + Live Card Studio routes. Top-5 does not enable it.
- The cutout Text Size control must feed the actual Render Now frame; regression coverage compares rendered pixels across different size settings rather than checking only stored configuration.
- Top-5 Live automatic visual fetching remains concurrent, but completion is collected when the Visuals stage is entered instead of using `sleep` + `st.rerun()` polling.
- Startup remains free of project-wide file-watcher overhead; `.streamlit/config.toml` keeps `fileWatcherType = "none"` and `runOnSave = false`.
- Full CI is the acceptance check for cleanup changes; no runtime claim is treated as final without validating the actual production/Test path.

### Test baseline after cleanup

- Python compile check passed.
- The earlier **113-test** baseline predates the subsequent Top-5 work and is no longer an authoritative acceptance count.
- Current acceptance is the full test suite for the active branch plus the actual Test dashboard path.
- Manual Subject Cutout regression coverage now covers the shared renderer API, both composition modes, nine fonts/styles, polygon-only rendering, overlay-free production handoff, exact left-edge anchoring, vertical polygon-flow indentation for Deep-Dive Cricket and YT Trends, Top-5 Test Card Studio standalone and per-slide Test paths, Cricket Test + Live Card Studio, and YT Trends Test/Live Card Studio. AppTest bypasses the browser-only inline polygon editor registration through Streamlit's global.appTest flag while exercising the same Python state/render path.
- Text Subject Cutout must remain a single shared implementation across Card Studio surfaces. Top-5 Live remains deferred until Top-5 Test is approved.

When changing either Function 01 or Function 02, preserve the direct architecture and check both the relevant unit tests and the actual Test/Live dashboard handoff before merging.

