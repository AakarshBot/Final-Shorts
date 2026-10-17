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


## Cross-chat context rule — HARD RULE

Every ChatGPT conversation that works on this repository must read the current `PROJECT_CONTEXT.md` from the repository before proposing changes or answering a project-status question. Recent-chat summaries or saved memory are not a substitute for reading this file.

Before sending a user-facing response during ongoing factory work, update this file first when the current task has changed the implementation, decisions, validation results, blockers, or next step. Update the existing section/checkpoint in place where possible; do not append duplicate notes or leave contradictions. State the real current status and one clear next step. Ask the user to decide only when a genuine decision is required; otherwise continue the work.

This is a repository operating rule for all future chats that consult the factory context. It does not imply that a new chat can see this repository automatically without retrieving the file.

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

The Dashboard UI/UX is **Audited & Modernized (10/10 UX Overhaul)**.

Production lines:
1. **Top 5 cricket stories of the day** — **Test-only / WIP**
2. **On This Day** — **Test-first / WIP**
3. **YouTube Search Trends** — **Test + Live / search-opportunity rebuild in validation**

Top-5 is currently Test-only / WIP. **Card Studio is the single card entry point in Top-5 Test.** Text Subject Cutout is the only approved card type. Cricket and YT Trends use the same shared Card Studio; Top-5 Live remains retrieval-only and does not expose Card Studio.

### Dashboard UI & UX System (Modern Studio Design)
- **Theme & Palette:** Professional light studio theme (`--bg: #f5f7fb`, `--surface: #ffffff`, `--surface-soft: #f1f5f9`, `--ink: #0f172a`, `--muted: #64748b`, `--line: #e2e8f0`) with restrained indigo actions (`--primary: #4f46e5`), subtle borders and shadows, and high-contrast text. The dashboard chrome and form fields stay light; only the simulated Short/video preview intentionally uses a dark background.
- **Scrollable Asset Pool Trays:** Visual scrapers, Card Studio image selectors, and Top-5 playgrounds wrap asset pools in fixed-height scrollable containers (`st.container(height=480..520)`) in a 4-column grid. Users no longer need to scroll through 20+ full-page images.
- **Quick-Action Approval Bars:** In both Live and Test Visuals, the visual slide board and approval action bar are surfaced immediately at the top above scraper pools. Once slides are populated, the user can review and approve without scrolling past the scraped candidates.
- **Compact Card Studio & Preview Layouts:** Card studio previews and Top-5 rendered card reviews use compact side-by-side two-column layouts with bounded preview dimensions (~280px–300px) instead of full-viewport multi-scroll layouts.
- **Elimination of Unnecessary Dashboard Reruns:** Removed redundant `st.rerun()` calls across topic tile expand/collapse, test stage pill navigation, and Top-5 content type switching. Interactive state transitions now render smoothly in a single execution cycle without UI flickering or double-refresh overhead.
- **Factory Runtime Optimizations:**
  - card_studio.py: Cached TrueType font loaders avoid repeated disk I/O and TTF table parsing.
  - renderer.py: Zero-copy frame-byte handling avoids redundant RGB conversions during video preview encoding; polygon text layout reuses cached geometry and skips line-break combinations that cannot fit the available polygon height.
  - visual_search.py: Persistent requests.Session with HTTP Keep-Alive pooling reduces repeated connection setup.
  - app.py: Crop canvas is bounded to 1600 pixels wide, cropper updates are committed on confirmation instead of recomputed on every pointer movement, image-validity checks and JPEG previews are cached, and unchanged source images are not decoded again on every crop-widget rerun.
  - tests/test_runtime_performance.py: Regression checks cover crop settings/cache behavior, polygon layout, and forbidden refresh/polling patterns.
- **No timer/polling refreshes:** Do not add st_autorefresh, run_every, intervals, time.sleep, or asyncio.sleep polling to the dashboard. Event-driven st.rerun() calls remain only where controls explicitly change stages or handoffs.
- **Strict Functional Integrity:** Subject Cutout and polygon text placement remain behaviorally unchanged; the optimizations target redundant work, not the approved rendering result. Preserve Shorts Test/Live boundaries.
- **Current verification:** GitHub Actions run #1210 on commit 675dad13dba177b83ec25fc25d131677c7881106 passed dependency installation, Python compilation, and the full test suite: 310 passed, 1 skipped, with 1 non-blocking Pillow deprecation warning in 156.30 seconds. Tests cover Chatterbox default routing, stack imports, reference-conditioning errors, language guards, and runtime optimizations. CI does not load the real model weights or generate actual speech. PR #103 was merged into main as commit 0c303887d36244e943c7bbc8605abf22ae2bd51e. The code is ready for a supervised Live-generation run once the local checkout is synced and the active Streamlit Python interpreter is confirmed to have the Chatterbox stack. Perform one real local audio/render smoke test before any public upload.

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

Unified Scriptwriter (`script_writer.py`):
- One shared module serves Deep-Dive Cricket, Top-5, YouTube Search Trends, Niche Sports, and On This Day; do not add parallel writers or wrapper layers.
- Research starts with the selected article and adds related reports when available to ground facts and clarify current status.
- Deep-Dive Cricket: three editorial angles for human selection, then exactly four spoken slides. Slide 1 is at most 13 words; total narration targets 50–70 words and under 30 seconds.
- YouTube Search Trends, Niche Sports, and On This Day: three editorial angles for selection, then 3–5 connected spoken slides, 50–74 words overall and under 30 seconds, with a subject-named lead and complete per-slide visual metadata.
- Top-5: six slides; Slide 1 is a package label plus visual-only roundup copy, Slides 2–6 correspond to the five selected stories in order, and the six spoken headlines target less than 30 seconds.
- The generation prompts explicitly list the content, packaging, quote, visual-handoff, and shape requirements enforced by generation validators. Generation may use one hidden recovery/rewrite for a failed draft; failed generated output is not sent to Manual QC.
- Do not post-process a generated 14-word lead by silently trimming it. The writer must produce a compliant lead or use the existing generation recovery path.

Generated publish metadata:
- `headline`: concise opening hook (3–4 words for Deep Dive/YT Trends; Top-5 package label for Top-5).
- `titles`: exactly 3 distinct title candidates (SEO/Search, Consequence/Significance, Curiosity).
- `seo_description`: concise story-specific description.
- `hashtags`: story-specific, valid hashtag values.
- `comment`: one concise discussion-oriented public-upload comment.

Human Scriptwriter QC:
- Human approval is not blocked by editorial/script validators. All editable narration and opening headlines can be approved as entered; Top-5 headline/body edits and metadata are also handed off without re-validating the human-edited content.
- The generation validators remain active before Manual QC and continue to trigger a hidden rewrite/recovery for malformed AI drafts. They must never be reused as post-edit approval gates.
- The single-script handoff retains only a structural integrity check that the edited narration count matches the generated scene count. No editorial word-count, headline, subject-name, filler, hashtag, quote, or metadata rule rejects human approval.

Status: **Unified architecture retained; generation checks moved fully upstream of human approval.**

## Audio — Function 03

Contract:
- Default automated engine: Chatterbox Turbo for standard Shorts Test, standard Shorts Live, Top-5 Test, Top-5 Live, and Long-form audio. The shared Shorts generators default to Chatterbox even when callers omit an engine.
- Edge-TTS is explicit-only: Test and Live expose an engine selector that defaults to Chatterbox. Edge-TTS is used only when the user selects it; never silently fall back from a failed Chatterbox model or reference.
- Chatterbox Turbo is English-only. The UI blocks Turbo generation for Hindi/Telugu selections and directs the user to choose Edge-TTS instead. Long-form is validated against the same Turbo language limit.
- The optional audio_reference.wav is read from the repository root or the AUDIO_REFERENCE environment path. If it is absent, Chatterbox uses its built-in voice. If a present reference fails conditioning, report the error rather than silently switching voices. The root file is gitignored and must remain local-only.
- Chatterbox writes WAV files; audio previews choose the MIME type from the actual file extension. Edge-TTS writes MP3 with validated WordBoundary timings. Both handoffs must satisfy the 30-second approval ceiling.
- Edge-TTS voice roster supports English, Hindi, and Telugu:
  - English: Female (en-IN-NeerjaNeural), Male (en-IN-PrabhatNeural).
  - Hindi: Female (hi-IN-SwaraNeural), Male (hi-IN-MadhurNeural).
  - Telugu: Female (te-IN-ShrutiNeural), Male (te-IN-MohanNeural).
- The Edge-TTS dependency floor is edge-tts>=7.3.1,<8 to include the October 2026 upstream fix for Microsoft speech-service token-format changes that caused WebSocket 403 failures.
- Human Audio upload & microphone recording remain available as intentional manual overrides, with linear word timing synthesis for subtitle synchronization.

Status: Chatterbox-default routing implemented; CI and a local generated-audio smoke test are required before treating the current commit as fully verified.

## Visuals — Function 04

Universal 2-Stage Visual Architecture across all desks (Deep-Dive Cricket, YT Trends, Top-5):

1. **Stage 1: Visual Collection (Fetcher & Curation)**
   - **Automatic Scraper:** Multi-URL crawler scraping the primary article and related publisher pages.
   - **Manual Scraper:** Real-time web/publisher query scraper.
   - **Real Image Search:** Searches parallel free, no-key image sources (Wikimedia Commons, DuckDuckGo, Wikidata, Wikipedia, Openverse, Flickr, Internet Archive) plus configured API sources (Bing & Google Images via SerpApi, Pixabay, Pexels, Unsplash).
   - **AI Generation:** Parallel AI image generators: keyless Pollinations.ai (Flux) plus configured Hugging Face and Cloudflare Workers AI.
   - **Curated Asset Pool:** Unified pool of all collected images with thumbnail preview, source badge, crop indicator, and a direct `🗑️ Delete` button to discard unneeded assets. Extra manual queries can be run anytime to add more images to the pool.

2. **Stage 2: Visual Builder (Layout & Assembly)**
   - **Crop & Reposition:** Interactive polygon and rectangular crop tool. (Hard locked, untouched).
   - **Text Subject Cutout:** Rembg foreground cutout with text placed behind or around subjects. (Hard locked, untouched).
   - **Card Studio:** Stat Highlight Card, Quote / Reaction Card, Head-to-Head Split Card, Key Fact / Milestone Card with negative-space subject awareness.
   - **Slide Attachment:** Attach any cropped image or generated card to any slide (1 to N).
   - **Visual Board:** Review all assigned slide visuals before approving the final handoff for Renderer.

Status: **Approved / 2-stage universal visual flow across all desks.**

## Subtitles — Function 05

Contract:
- Input is approved Scriptwriter narration plus approved Audio native word timings. No second transcription pass.
- Output schema: `final-shorts.subtitles.v1`.
- Words grouped into compact 2–4 word cues with punctuation and pause awareness.
- **Typographic baseline alignment:** Subtitle words are drawn using uniform line-level baselines (`anchor="ls"` with font ascent metrics), eliminating vertical word jumping/indentation caused by varying character bounding boxes.
- **Indic font glyph integrity:** Bundled Google Noto fonts (`NotoSansDevanagari-Bold.ttf`, `NotoSansTelugu-Bold.ttf`) prevent missing character box glyphs (`[ ]`) for Hindi and Telugu.

Status: **Approved / Typographic baseline & Indic fonts verified.**

## Renderer — Function 06

Renderer v2 is the single shared Test/Live renderer:
- Composes frames with Pillow and encodes 1080 × 1920 @ 30fps vertical video with FFmpeg.
- H.264 High Profile, BT.709, CRF 18, Fast Start.
- Stereo AAC audio at 192 kbps normalized to -14 LUFS / -1.5 dBTP.
- Photo motion uses deterministic push/pan; Card Studio and Top-5 cards render as static frames.
- Suppresses subtitle overlay automatically for Card Studio and Text Subject Cutout frames.

Status: **Active / Shared Test + Live renderer.**

## YouTube Upload — Function 07

Authentication & Upload QC:
- OAuth 2.0 with local `token.json` and `client_secret.json`.
- Editable video title, description, hashtags, and pinned discussion comment.
- **Synthetic Media Compliance:** Injects `"containsSyntheticMedia": True` into video status metadata per YouTube Inauthentic / Mass-Produced Content policy requirements (effective July 15, 2025).
- Two upload paths: **Upload Public** (uploads public + pins discussion comment) and **Upload Private** (uploads private without comment).

Status: **Approved / Synthetic media transparency flag active.**

## Dashboard state

The dashboard uses a **professional light studio theme** across Test and Live: porcelain `#f5f7fb` canvas, white work surfaces, slate `#0f172a` typography, subtle neutral borders/shadows, and restrained indigo action/selection accents. Streamlit's existing light theme is kept; `app.py` CSS must not override it with a dark application shell or dark form fields.

- **Navigation:** Existing three-column workspace bar, TEST/LIVE switch, direct stage navigation, and pipeline progress remain behaviorally unchanged.
- **Editorial review:** Story-angle cards, Scriptwriter editor, teleprompter, packaging cards, comments, and status panels use readable light surfaces and slate text. The phone/video mock-up intentionally stays dark because it represents the actual Short preview, not the dashboard chrome.
- **Audio Studio:** Existing multilingual voice roster, Edge-TTS controls, track preview, timing validation, cache, and manual audio options remain intact; the dependency floor fix is documented in Audio — Function 03.
- **Visual Board and Renderer:** Existing visual selection, crop/reposition, polygon subject cutout, Card Studio, frame generation, and renderer contracts are out of scope and must remain unchanged.
- **Quality gate:** The latest main-branch CI was successful on 12 October 2026. The branch implementing these changes must pass the full compile and pytest workflow before merge; do not claim an old test count as the current result.
- **Hard locks:** Keep the shared Manual Subject Cutout editor/renderer and crop paths untouched. No unrelated stage, visual-generation option, upload route, or Long-form behavior is included in this patch.

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

Fragment and runtime-performance audit (2026-10-18):
- Manual Subject Cutout remains the only `@st.fragment` in `app.py`; no `run_every` timer is configured. Fragment reruns are caused by direct widget interaction, not a timed refresh.
- The dashboard has no `st_autorefresh`, interval timer, or polling loop. `.streamlit/config.toml` keeps `fileWatcherType = "none"` and `runOnSave = false`. Explicit `st.rerun()` calls are reserved for user-triggered navigation, approval, attachment, and stage transitions; do not remove them indiscriminately.
- Crop/reposition uses a canvas capped at 1600 px wide and `st_cropper(realtime_update=False)`. Double-click confirms the crop so dragging does not continually send a new crop value and rebuild a full-resolution blurred canvas.
- Visual-pool image validation and resized JPEG thumbnail bytes use bounded Streamlit data caches. This avoids decoding and resizing every source image on every ordinary rerun.
- The selected cutout image is decoded to build the polygon editor payload only when its source digest changes. The source image remains unchanged; the crop and final renderer continue to use the established 9:16 handoff.
- Manual Subject Cutout layout geometry is cached for repeated, ordinary headlines (10 words or fewer). Long headlines are left uncached to avoid retaining large combinatorial layout results in memory. Layout search now enumerates only line-break combinations within the polygon's vertical capacity, instead of iterating every bitmask that could never fit.
- Keep Render Now and Preview all valid line-break options explicit. Do not re-render the final frame merely because the headline, polygon, font, style, or size widget changed.

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
card_studio.py
subtitles.py
renderer.py
uploader.py
tests/test_topic_fetcher.py
tests/test_script_writer.py
tests/test_top5_script_writer.py
tests/test_universal_script_writer.py
tests/test_audio.py
tests/test_card_studio.py
tests/test_top5_card.py
tests/test_subtitles.py
tests/test_visual_fetcher.py
tests/test_visual_search.py
tests/test_visual_generator.py
tests/test_renderer.py
tests/test_uploader.py
tests/test_app_visual_smoke.py
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
- **Scriptwriter handoff:** every YT Trends story uses the unified Scriptwriter (`script_writer.py`), including cricket stories.
- The unified Scriptwriter receives the preserved search query as packaging context. It uses that query to shape the SEO/Search title and story-specific description naturally, without a new hard validator or keyword stuffing.
- The generated script retains the `search_query` field for downstream handoff/audit.
- The YT Trends Visuals stage uses the shared single-story Card Studio and exposes the approved Text Subject Cutout card in both Test and Live.
- After selection, Live moves into the existing single-story Script stage and then uses the existing Audio + Subtitles → Visuals + Render → Upload flow.
- Test uses the same unified Scriptwriter handoff for YT Trends and then its existing downstream Test stages.
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

### Function 02 — Unified Scriptwriter (`script_writer.py`)

All previous scriptwriters (`universal_script_writer.py`, `top5_script_writer.py`, and the legacy cricket writer) have been consolidated into **one unified scriptwriter** (`script_writer.py`) with zero compatibility wrappers.

Scope & Stream Dispatch:
- **Deep-Dive Cricket:** Generates 3 research-backed editorial angles for human selection, producing a 4-slide spoken script. Slide 1 capped at 13 words; narration under 30 seconds.
- **YouTube Search Trends & Niche Sports:** Generates 3 research-backed editorial angles honoring search intent, producing 3–5 spoken slides. Slide 1 capped at 13 words; total narration 18–30 seconds (50–74 words). Preserves the raw search query context for SEO/Search packaging.
- **Top-5 Stories:** Generates a 6-slide package (Slide 1: hook headline ≤8 words with visual body copy; Slides 2–6: spoken headline + visual card body). Total spoken headline duration strictly under 30 seconds.

Unified Generation & Validation Architecture:
1. Gathers the primary source article and searches for up to two related current reports for factual grounding.
2. For Deep-Dive and YT Trends, generates 3 distinct editorial angles first. The chosen angle guides script generation.
3. Generates complete script draft with `openai/gpt-oss-120b`.
4. Performs strict local validation (scene count, word limits, duration bounds, filler/bait prohibition).
5. If validation fails, performs exactly one hidden complete rewrite with `openai/gpt-oss-20b` targeting the exact validation error.
6. Never exposes an invalid draft to Manual QC.

Publish Metadata Handoff:
- `headline`: concise opening hook (3–4 words for Deep-Dive/YT Trends; package headline for Top-5).
- `titles`: exactly 3 distinct title candidates (SEO/Search, Consequence/Significance, Curiosity).
- `seo_description`: concise story-specific description.
- `hashtags`: 3–5 relevant hashtags.
- `comment`: one concise discussion-oriented public-upload comment.
- Retains scene-level metadata (`primary_entity`, `visual_intent`, `specific_search_prompt`, `sport_or_topic_category`, `search_query`).

Status: **Consolidated / Fully operational / Verified by test suite.**

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

- The merged `main` commit `2b313ba` passed GitHub Actions run `39069420313`: Python compilation succeeded and the full suite reported **299 passed, 1 skipped**. One Pillow deprecation warning was non-blocking.
- Edge-TTS `7.3.1` is confirmed installed in the user's standard Python 3.11 environment; do not ask for a repeat installation.
- Remote CI is not a substitute for the first Windows runtime smoke test. Confirm the local checkout matches `main`, enter a low-risk Live Scriptwriter → Audio path, approve a reviewed test script, and verify the downstream handoff before any upload/publication.
- Manual Subject Cutout regression coverage now covers the shared renderer API, both composition modes, nine fonts/styles, polygon-only rendering, overlay-free production handoff, exact left-edge anchoring, vertical polygon-flow indentation for Deep-Dive Cricket and YT Trends, Top-5 Test Card Studio standalone and per-slide Test paths, Cricket Test + Live Card Studio, and YT Trends Test/Live Card Studio. AppTest bypasses the browser-only inline polygon editor registration through Streamlit's global.appTest flag while exercising the same Python state/render path.
- Text Subject Cutout must remain a single shared implementation across Card Studio surfaces. Top-5 Live remains deferred until Top-5 Test is approved.

When changing either Function 01 or Function 02, preserve the direct architecture and check both the relevant unit tests and the actual Test/Live dashboard handoff before merging.



## LONG-FORM — Live in Production

**Status: Approved & Live in Production. Shorts production is 100% protected.**

### Scope and verified behavior
- Top-level content-format choice: **Shorts** or **Long-form**. After format selection, **Test** and **Live** workspace choices are active for both formats.
- The established Shorts Test and Live paths, stage contracts, approved functions, UI and outputs remain completely unchanged and protected.
- Long-form Live graduated from Test following user approval ("check if all tests are good for long form and turn it live"). It executes the complete 7-stage 8-minute documentary production line:
  01. Topic Fetcher (`longform_topic_fetcher.py`)
  02. Scriptwriter (`longform_script_writer.py`)
  03. Visuals (`longform_cards.py`, `longform_visuals.py`)
  04. Audio (`longform_audio.py`)
  05. Subtitles (`longform_subtitles.py`)
  06. Renderer (`longform_renderer.py`)
  07. Upload QC (`longform_uploader.py`)
- Live enforces the approved sequential pipeline order (`01 · Topic Fetcher` → `02 · Scriptwriter` → `03 · Visuals` → `04 · Audio` → `05 · Subtitles` → `06 · Renderer` → `07 · Upload QC`), while Test retains direct stage navigation.
- Preserves all human review gates at Topic selection, Script review, and Upload review (with private/unlisted default). Visual sourcing runs 100% automated with zero manual QC needed.
- Audio synthesizes full ~8-minute documentary narration using `ChatterboxTurboTTS` (voice conditioned or built-in neural voice).
- Renderer outputs 1920×1080 30FPS 16:9 widescreen broadcast master documentary with dynamic audio muxing and sidechain ducking.
- Upload packages full YouTube metadata including structured chapter timestamps, research bibliography citations, and pinned discussion prompts.
- Full factory CI is the acceptance check across all modules, formats, and desks; confirm the current passing count from the workflow run rather than relying on a historical hard-coded total. Zero regressions are required on established Shorts lines.
- Next step: Run end-to-end documentary production in Live or Test mode.

