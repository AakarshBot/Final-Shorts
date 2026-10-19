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
- Test and Live Scriptwriter views expose the root-level opening headline as editable dashboard-only metadata, with no word or character cap; it is never rendered into the standard Short. Quote/attribution and spoken slides remain part of the handoff. For Top-5, each slide's spoken headline and visual-only body copy remain unchanged.
- Audio consumes the Scriptwriter handoff and returns audio/timing data. Test lets the user listen and approve it.
- Visuals are a modular function. Automatic scraping starts from the selected story URL, while manual scraper/search/AI options can be run independently. Manual inputs may deliberately bypass upstream approvals when the visual function does not actually require that approval.
- Test Visuals uses the same slide-board interaction as Live: script context above each slide, per-slide visual attachment, crop/reposition, and an explicit approved visual handoff. Standard Cricket production uses four visual slides; Top-5 remains a separate six-slide workflow.
- Card Studio and other visual sub-functions are independently testable in Test. Card Studio uses the existing image pool and manual QC. On 2026-10-18, the user explicitly promoted the four sports-editorial card types to Live in addition to Text Subject Cutout; the shared card implementation is used in both modes.
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

Top-5 remains Test-only / WIP. **Card Studio is the single card entry point in Top-5 Test.** Cricket and YT Trends use the shared Card Studio in Test and Live; Live now exposes the four sports-editorial card types alongside the existing Text Subject Cutout. Top-5 Live remains retrieval-only and does not expose Card Studio.

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
  - app.py: Visual Fetcher and editorial Card Studio now have independent crop state. The crop dialog shows the complete source at its own aspect ratio, allows a free-size rectangle, previews the selected area stretched to 1080×1920, and resets to a centred 9:16 frame on request. Applied crop bytes are the final slide image; original source bytes remain available for recropping. Card Studio receives the unmodified original source, not Visual Fetcher crop values.
  - tests/test_runtime_performance.py: Regression checks cover crop settings/cache behavior, polygon layout, and forbidden refresh/polling patterns.
- **No timer/polling refreshes:** Do not add st_autorefresh, run_every, intervals, time.sleep, or asyncio.sleep polling to the dashboard. Event-driven st.rerun() calls remain only where controls explicitly change stages or handoffs.
- **Strict Functional Integrity:** Subject Cutout and polygon text placement remain behaviorally unchanged; the optimizations target redundant work, not the approved rendering result. Preserve Shorts Test/Live boundaries.
- **Current verification (2026-10-18):** PR #105 GitHub Actions run #1230 on pre-merge SHA `32b295ba567a07298cf528f92a891f25045f0136` passed dependency installation (including `google-auth-oauthlib`), Python compilation, and the full test suite: 314 passed, 1 skipped, and 1 non-blocking Pillow deprecation warning in 157.13 seconds. PR #105 was squash-merged to main at `9f74be41a23e6acb128db43a2734c24232bdec7a`; main-branch run #1231 on that merge commit also passed the full suite: 314 passed, 1 skipped, and 1 warning in 93.60 seconds. Audio/runtime PR #103 was merged at `0c303887d36244e943c7bbc8605abf22ae2bd51e`. Audio optimisation PR #106 passed dependency installation, Python compilation, and the full suite in PR merge run #1242: 320 passed, 1 skipped, and 1 non-blocking Pillow deprecation warning in 160.20 seconds; it was squash-merged to main at `3b9750923898ede2965b5095b8d4930e5ccab387`. The follow-up audio-clarity correction restores the earlier temperature profile, raises the audio-cache signature version to force clean regenerated WAVs, and adds regression assertions for Shorts and Long-form temperature handling; final local listening verification is still required. CI does not load real local Chatterbox weights, renew OAuth through a browser, or generate/upload an actual Short. Before public upload, sync the local checkout, confirm the three selected local voice references, and run one supervised Live audio/render and Upload QC smoke test.

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
- Deep-Dive Cricket: three editorial angles for human selection, then 3–5 spoken slides, preferring four when the story fits naturally. English Slide 1 is at most 13 words; Hindi/Telugu Slide 1 is validated by measured first-scene audio duration (maximum 5.2 seconds). Total narration targets 50–70 words and under 30 seconds.
- YouTube Search Trends, Niche Sports, and On This Day: three editorial angles for selection, then 3–5 connected spoken slides, 50–74 words overall and under 30 seconds, with a subject-named lead and complete per-slide visual metadata. English Slide 1 stays under 14 words; Hindi/Telugu use the 5.2-second measured-audio limit.
- Top-5: six slides; Slide 1 is a package label plus visual-only roundup copy, Slides 2–6 correspond to the five selected stories in order, and the six spoken headlines target less than 30 seconds.
- The generation prompts explicitly list the content, packaging, quote, visual-handoff, and shape requirements enforced by generation validators. A hidden rewrite is only for a returned draft that fails local validation; a failed provider request must not be described as a draft rewrite. Groq HTTP diagnostics retain provider details including Retry-After and any `failed_generation` payload. A Groq HTTP 400 `json_validate_failed` generation error receives one JSON Object Mode retry with the expected output shape supplied in the prompt; the local Scriptwriter validator still gates acceptance. Follow-up multilingual reliability fix (2026-10-19): Indic name matching uses Unicode normalization that preserves native-script vowel marks and ignores invisible format characters. For Hindi/Telugu, if the generated first-slide `primary_entity` is present in that slide's spoken voiceover, the pre-validation recovery can align `subject_name` to that evidenced spelling; otherwise the name requirement still triggers the normal hidden rewrite. Cricket and Universal writers normalise malformed/duplicated title lists to exactly three distinct candidates from metadata already present in the generated response, then use a localized fallback only if needed. Hindi/Telugu total-word validation, returned word counts, and Scriptwriter flow telemetry count whitespace-separated spoken words instead of English regex fragments; the Audio stage remains authoritative for measured duration. This does not touch Top-5's six-slide rules. The shared Groq requester now honours numeric `Retry-After` for up to two bounded 429 retries (maximum 30 seconds per wait) rather than immediately switching models against the same organisation TPM limit; a persistent limit still surfaces as a provider error. CI review also found and fixes two pre-existing test issues: the generation-prompt test now matches the explicit subject-name rule, and the Top-5 transient-request mock includes the HTTP `status_code` field expected by the shared requester; this test-only correction does not change Top-5 behavior.
- Do not post-process an English lead of 14 words or more by silently trimming it. The writer must produce a compliant lead or use the existing recovery path. Hindi/Telugu first-slide length is gated by measured audio duration, not word-token count.

Generated publish metadata:
- Standard non-Top-5 `headline`: crisp, story-specific dashboard display metadata with no word-count/character limit. It is not spoken and must never be included in the rendered Short. Top-5 retains its independent six-slide package/card headline rules.
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
- Default automated engine: Chatterbox is the default engine for standard Shorts Test/Live, Top-5 Test/Live, and Long-form. The dashboard defaults to **Turbo** but exposes **Full** as a sibling model choice in every applicable Test and Live Audio stage; Edge-TTS remains an explicit alternative. Shared generator callers that omit an engine or model continue to default to Chatterbox Turbo.
- Edge-TTS is explicit-only: Test and Live expose an engine selector that defaults to Chatterbox. Edge-TTS is used only when the user selects it; never silently fall back from a failed Chatterbox model or reference.
- Chatterbox Full and Turbo are English-only. The UI blocks either Chatterbox model for Hindi/Telugu and directs the user to Edge-TTS. Long-form is validated against the same language limit. For standard Hindi/Telugu Shorts using Edge-TTS, measured first-scene audio must be no longer than 5.2 seconds during generation and Audio approval; this replaces only the Scriptwriter word-count gate for that lead. English retains the existing ≤13-word rule.
- Three local Chatterbox reference choices are available before audio generation in standard Shorts Test/Live, Top-5 Test/Live, and Long-form Test/Live: Voice 1 uses `audio_reference.wav` (or the configured `AUDIO_REFERENCE` path), Voice 2 uses `audio_reference_2.wav`, and Voice 3 uses `audio_reference_3.wav`. The two extra files must be dropped into the factory root locally. All three reference paths are gitignored and must never be committed. The UI shows missing-file status and blocks generation until the chosen reference exists. Calls without an explicitly selected voice retain the existing optional built-in-voice fallback. A present but invalid reference must report an error rather than silently switching voices.
- Chatterbox writes WAV files; audio previews choose the MIME type from the actual file extension. Edge-TTS writes MP3 with validated WordBoundary timings. Both handoffs must satisfy the 30-second approval ceiling.
- Edge-TTS voice roster supports English, Hindi, and Telugu:
  - English: Female (en-IN-NeerjaNeural), Male (en-IN-PrabhatNeural).
  - Hindi: Female (hi-IN-SwaraNeural), Male (hi-IN-MadhurNeural).
  - Telugu: Female (te-IN-ShrutiNeural), Male (te-IN-MohanNeural).
- The Edge-TTS dependency floor is edge-tts>=7.3.1,<8 to include the October 2026 upstream fix for Microsoft speech-service token-format changes that caused WebSocket 403 failures.
- Human Audio upload & microphone recording remain available as intentional manual overrides, with linear word timing synthesis for subtitle synchronization.
- Runtime behaviour: one Chatterbox model family (Full or Turbo) is kept resident per Python process and reused across Shorts and Long-form; switching families clears the previous model/conditioning cache to limit memory use. A process restart requires one cold model load. Each selected reference is conditioned once per loaded model and cached, so switching back to an already prepared reference avoids repeating conditioning.
- Audio caching is signature-keyed by complete narration, run seed, Full/Turbo model family and its settings, selected reference file content, and pipeline/chunk layout. Matching inputs reuse their master WAV and scene previews without loading PyTorch/Chatterbox; other models, voices or scripts get separate outputs. Long-form caches its continuous master plus scene preview slices; a cache hit skips model loading.
- **Continuous Chatterbox narration (implementation branch `chatterbox-continuous-full-turbo-20261020`):** Shorts and Top-5 send all approved spoken text to one TTS generation call, use a fixed sampling temperature (Turbo 0.80; Full 0.75), and no longer insert keyword-driven `[gasp]` cues or scene-dependent temperature changes. Scene WAVs are preview/subtitle slices cut from the master take using text/punctuation-weighted estimated boundaries; the Renderer muxes the single uninterrupted `full.wav` when the approved scenes still share that master. Edge-TTS, and any pipeline where a per-scene human override replaces one slice, retains the existing per-scene mux route. Boundaries are estimates rather than forced-alignment timestamps and must be listened to/visually checked in a real render.
- **Chatterbox Full/Turbo selection:** The standard Shorts, Top-5, and Long-form Audio dashboards in Test and Live expose Turbo or Full under Chatterbox; Turbo is the default. Full uses the original `ChatterboxTTS` loader with fixed CFG/exaggeration and sampling settings; Turbo uses `ChatterboxTurboTTS` and its supported temperature setting only. Only one family is kept resident to reduce memory pressure. Both models remain English-only; no silent model fallback occurs.
- **Long-form grouping:** Rather than synthesize every scene separately, Long-form groups multiple scene narrations within each act into paragraph-sized generation requests (target ≤100 words/900 characters per chunk), cuts scene-preview WAVs from each grouped take, then builds one master narration track. The full master is passed to Long-form Renderer. Pauses remain at actual chunk boundaries (0.08s) and act transitions (0.80s), not every scene. Scene start times and subtitles use weighted estimated scene boundaries; these are not true forced-alignment timestamps. The Long-form Renderer scene cursor advances at the next scene's actual `start_seconds`, holding the previous scene visual during deliberate audio gaps instead of prematurely showing a future scene.
- Runtime trade-off: brand-new scripts/voices still require synthesis; the best speed gains are repeat renders and voice switching, and the first run in a fresh process remains a cold start.

Status: PR #119 (`Generate continuous Chatterbox narration with Full/Turbo selection`) merged to `main` on 2026-10-20 at `34958c868035e92fde00b9901f9b47d429e831e9`. GitHub Actions PR run #1389 passed compilation and the full suite: **409 passed, 1 skipped, 1 warning** in 158.49 seconds. The implementation covers one-call Shorts/Top-5 narration with stable delivery, grouped Long-form synthesis, Full/Turbo dashboard choices in Test and Live, engine/model approval guards, single-master muxing, human-audio override fallback, and Long-form act-gap timing. For Windows Hindi/Telugu, the renderer now automatically calls the repository's checksum-verified no-pip PowerShell FriBiDi installer if RAQM is unavailable, then registers the DLL folder and rechecks Pillow. This integration has only mocked CI coverage; actual Windows DLL download/extraction/loading, local Chatterbox weights/audio quality, voice-reference fidelity, exact subtitle alignment, and a real Test/Live render remain unverified. Before public upload, pull `main`, then run one supervised Hindi/Telugu render and one English Test/Live render; inspect continuous audio and approximate slide/subtitle boundaries before upload. Voice 2 and Voice 3 references remain optional local setup files; a selected missing reference blocks generation.

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
   - **Card Studio:** Stat Highlight, Quote / Reaction, Head-to-Head and Key Fact / Milestone use a photo-led sports-editorial system in Test and Live: restrained ink/white/signal-accent palette, expressive display type, clear type hierarchy, thin rules instead of decorative glass panels/3D effects, and composition-specific layouts. Existing BiRefNet subject masks are generated for selected images and passed to the card renderer; image and mask receive the same crop/resize transform. If segmentation is unavailable, image texture supplies a fallback layout without blocking rendering. No new dependencies. All four editorial card types expose manual `Text / gradient position` controls (Auto, Left half, Right half, Bottom half) and contrast treatments (Soft gradient, Deep gradient, Editorial panel) in both Test and Live. Quote / Reaction uses an oversized opening quotation mark, more deliberate typography hierarchy, a compact accent rule, and clearer attribution/context. Changing card type or composition options clears the stale rendered preview so the user must render again before attaching a card. Text Subject Cutout is unaffected. The non-cutout Card Selector follows crop drags live over a cached bounded canvas; applying a crop invalidates any stale card render that used that image (including either side of Head-to-Head), so re-render and reattach the card. General crop and Text Subject Cutout confirmation paths remain unchanged.
   - **Hindi/Telugu Live production:** The Live Scriptwriter exposes an English/Hindi/Telugu selector before story-angle and script generation; changing languages clears stale unselected angles. The Live Audio stage must use Edge-TTS Neural for Hindi/Telugu because the factory's Chatterbox Turbo path is English-only. Audio and subtitle handoff enforce matching script/audio languages.
   - **Multilingual card copy (Test and Live):** PR #113 now requires RAQM for Hindi/Telugu text across the four editorial Card Studio types and replaces the silent basic-layout fallback with a clear failure. Bundled Noto Sans Devanagari/Telugu Bold is the only selected Indic font. Text Subject Cutout now chooses the appropriate Noto font from the actual text even when an English display font is selected in the UI, and Top-5 uses the existing bundled Noto files instead of missing CondensedBlack/Black variants. The implementation has dedicated shaping/font-selection tests; GitHub Actions is the current validation gate. Windows Pillow requires FriBiDi to make RAQM available; the patch stops Indic rendering with an actionable error if RAQM is absent rather than risking incorrect letters. Local Windows RAQM availability and visual review remain unverified.
   - **Slide Attachment:** Attach any cropped image or generated card to any slide (1 to N).
   - **Visual Board:** Review all assigned slide visuals before approving the final handoff for Renderer.

Status (2026-10-19): **The sports-editorial card designs are promoted to Live at the user’s direction. The shared Card Studio selects TEST_CARD_TYPES in Test and LIVE_CARD_TYPES in Live; both allow Text Subject Cutout, Stat Highlight, Quote / Reaction, Head-to-Head, and Key Fact / Milestone in the Cricket and YT Trends live routes where Card Studio is exposed. Text Subject Cutout rendering, crop/reposition, and polygon placement remain hard locked and unchanged for English. Top-5 Live remains retrieval-only and does not expose Card Studio.** PR #113's Indic font fixes for subtitles, the four editorial card types, Top-5 renderer and Text Subject Cutout are merged to main at `9d3baff96121757059ac59c99207f0d08f9ec924`. The code requests RAQM explicitly, uses the bundled Noto Sans files, and refuses to render Hindi/Telugu via basic fallback. The latest full pytest run is still in progress; local Windows RAQM availability and visual review are also unverified.

## Subtitles — Function 05

Contract:
- Input is approved Scriptwriter narration plus approved Audio native word timings. No second transcription pass.
- Output schema: `final-shorts.subtitles.v1`.
- Words grouped into compact 2–4 word cues with punctuation and pause awareness.
- **Typographic baseline alignment:** Subtitle words are drawn using uniform line-level baselines (`anchor="ls"` with font ascent metrics), eliminating vertical word jumping/indentation caused by varying character bounding boxes.
- **Indic font rendering:** PR #113 explicitly requires Pillow RAQM for Hindi/Telugu subtitle shaping and uses only the bundled Noto Sans Devanagari/Telugu Bold fonts. New tests cover representative conjuncts/vowel signs, selected font paths, and safe failure when RAQM is unavailable. GitHub Actions and the real Windows environment must still be verified before claiming end-to-end glyph correctness.

Status: **Subtitle baseline alignment approved; RAQM-backed Indic font selection and regression tests are merged to main at `9d3baff96121757059ac59c99207f0d08f9ec924`; full-suite CI and Windows verification remain outstanding.**

## Renderer — Function 06

Renderer v2 is the single shared Test/Live renderer:
- Composes frames with Pillow and encodes 1080 × 1920 @ 30fps vertical video with FFmpeg.
- H.264 High Profile, BT.709, CRF 18, Fast Start. The Shorts encoder uses FFmpeg's `veryfast` preset to reduce encode time while retaining the existing frame size, FPS and CRF; output files may be somewhat larger.
- Stereo AAC audio at 192 kbps normalized to -14 LUFS / -1.5 dBTP.
- Photo motion uses deterministic push/pan; Card Studio and Top-5 cards render as static frames.
- Suppresses subtitle overlay automatically for Card Studio and Text Subject Cutout frames.
- **Windows Indic rendering root cause and fix (merged 2026-10-20):** Pillow's Windows wheels support RAQM but still need a separate FriBiDi DLL; searching/registering folders cannot fix a machine where the DLL is absent. The shared Renderer now automatically invokes the repository's existing `setup_windows_indic_rendering.ps1` through PowerShell when a Hindi/Telugu render finds RAQM unavailable. That script retries the official MSYS2 repository and Tier 1 mirrors, verifies the published SHA-256 for FriBiDi 1.0.17-1 before extraction, and installs only `libfribidi-0.dll` plus its LGPL licence into the locally ignored `dlls/` directory. The renderer validates the output, registers the directory, then re-checks Pillow RAQM in the same process; the user no longer needs to run the setup batch file manually. No new Python dependency or runtime `pip` installation is required, avoiding the known broken global pip path. If setup fails, the renderer surfaces the PowerShell error output instead of hiding it behind the generic RAQM error. CI run #1389 covers the integration using mocked PowerShell/downloads; actual Windows downloads/loading and a real Hindi/Telugu render remain unverified until a Windows smoke test. PR #118 (`Retry trusted MSYS2 mirrors for FriBiDi setup`) remains merged to `main` at `ab144ecc6c47f1cd77e2c4955b1701070c92dd39`; PR #119 wires that trusted setup into the actual render failure path.
- Does not render the standard root-level Scriptwriter headline. That field is dashboard-only metadata; editorial card text and Top-5's six-slide card/headline flow remain separate.

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
- **Visual Board and Renderer:** Existing visual selection, crop/reposition, polygon subject cutout, Card Studio, and Top-5 card rendering remain unchanged. Standard Shorts Renderer no longer accepts or draws the root-level dashboard headline. Both Shorts and Long-form renderers use unique silent intermediates with best-effort cleanup; Long-form cleanup covers frame-generation and mux failures as well. PR #117 also precomputes Shorts motion seeds, caches the deterministic motion profile, uses forward-only timeline cursors for Long-form scenes/subtitles/act billboards, and renders images from bounded four-candidate download batches per article page.
- **Quality gate (2026-10-19):** PR #112 (`Make Scriptwriter headline dashboard-only`) is merged to `main` at `7b032223fd5f4219458640324824393644d78934`; its CI passed (351 passed, 1 skipped). PR #113 (`Fix Hindi/Telugu text shaping and Groq Scriptwriter recovery`) is merged at `9d3baff96121757059ac59c99207f0d08f9ec924`; PR #114 (`Recover Scriptwriter from Groq JSON generation failures`) is merged at `5e9678420b7eabcf66cddaffdfe7344d47dc0e55`. PR #115 (`Fix Hindi/Telugu Scriptwriter and Windows rendering failures`) is merged to `main` at `826f0faa6d2f6d92bf9386b87d1f0f53042996ed`. Latest corrected PR CI run #1333 passed Python compilation and the full suite: 377 passed, 1 skipped, 1 warning. The initial Windows locked-temp regression test run failed only because its fixture omitted the required subtitle handoff; the fixture was corrected to use `TEST_SUBTITLE_DATA` before run #1333. Post-merge main-branch CI runs #1335 and #1336 are in progress. The test-only Top-5 fixture corrections do not alter Top-5 runtime behavior. Windows RAQM + actual Hindi/Telugu render smoke testing still must be performed locally after running `setup_windows_indic_rendering.bat` and restarting Streamlit. High-level runtime/factuality cleanup PR #117 is merged into `main` at `ef96a41f5782b91f0a2be1b1b1846ae9a70643c3` (2026-10-19). Its PR-head GitHub Actions run #1359 passed Python dependency installation, `py_compile`, and the full test suite: **395 passed, 1 skipped, 1 warning** in 196.84 seconds. It precomputes/caches Shorts motion state and uses FFmpeg's `veryfast` preset at the existing CRF 18 and 30 FPS; removes the retired dashboard-only root-headline drawing subsystem; replaces per-frame Long-form scene/subtitle/billboard scans with timeline cursors; gives Long-form each render its own temporary silent MP4 and cleans up on frame-generation/mux failures; downloads candidate images in bounded four-item parallel batches; deduplicates repeated Long-form fallback image prompts and parallelizes research retrieval; normalizes act/scene IDs, rejects malformed acts or empty narration early, and avoids retrying deterministic Groq 4xx errors (except 429) while allowing alternate-model fallback on HTTP 400; removes unsupported B-roll requests and fabricated Long-form card defaults/source claims. Human approval gates, Shorts Test/Live contracts, and Top-5's six-scene pipeline remain in place. This CI result is Linux/Python 3.12 coverage; local Windows Hindi/Telugu RAQM smoke testing and an actual Test/Live render have not been performed and must not be reported as verified.
- **Hard locks:** Keep the shared Manual Subject Cutout editor/renderer and crop paths untouched. No unrelated stage, visual-generation option, upload route, or Long-form behavior is included in this patch.

### Top-5 current implementation checkpoint

- Top-5 Visuals Test remains independently runnable with exactly five dashboard choices.
- Top-5 Option 1 is **Automatic Scraper**.
- Top-5 Option 2 is **Manual Scraper**.
- Top-5 Option 3 is **Manual Fetcher**: manual query → real-image provider results → existing image pool. It does not render card typography.
- Top-5 Option 4 is **AI Generation**.
- Top-5 Option 5 is **Card Studio**, the single card entry point.
- Card Studio exposes five card types in Cricket and YT Trends Test + Live: **Text Subject Cutout**, **Stat Highlight**, **Quote / Reaction**, **Head-to-Head**, and **Key Fact / Milestone**. The four sports-editorial types use the same shared renderer in Test and Live.
- Text Subject Cutout is implemented by the existing shared Manual Subject Cutout editor/renderer. Cricket Test + Live, YT Trends Test + Live, and Top-5 Test use that same implementation; it is not reimplemented inside Card Studio.
- The four sports-editorial Card Studio types are static 1080 × 1920 Pillow frames with editable content and explicit manual visual QC in Test and Live.
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

**Text Subject Cutout** remains backed by the existing manual subject-cutout implementation. It is exposed through Card Studio in Cricket Test/Live, YT Trends Test/Live, and Top-5 Test. The four editorial card types are now available in Cricket and YT Trends Live as well; Top-5 Live remains retrieval-only.

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

Fragment, crop, and visual-card behaviour audit (2026-10-20):
- Manual Subject Cutout remains the only `@st.fragment` in `app.py`; its polygon editor and renderer remain unchanged by the editorial-card redesign. No timed refresh or polling is configured; `.streamlit/config.toml` keeps `fileWatcherType = "none"` and `runOnSave = false`.
- The crop dialog displays the full original image in its native aspect ratio. The crop rectangle is free-size, with an explicit reset to a centred 9:16 selection. Apply crop previews and stores the selected area stretched to 1080×1920, so the pool preview and slide attachment use the same image bytes. “Use original image” clears the active crop; future crop sessions always start from original source bytes.
- Visual Fetcher and Card Studio use independent crop stores. Selecting a fetcher image for Card Studio transfers uncropped original bytes. The cropper receives original-resolution pixels, scales only its on-screen control, allows free-size selection, and stretches the selected source region to the exact 1080×1920 output. Card Studio crop/reset synchronises only `card-studio-photo` direct attachments; Visual Fetcher crop/reset synchronises only its own assignments. Test, Live and Top-5 crop stores remain isolated, approved visual renders are invalidated when relevant crop bytes change, and cached Card Studio cards are invalidated on recrop.
- The four editorial cards share explicit “Auto-fill this card from story” and manual-prompt generation controls backed by the existing Scriptwriter/Groq request function. Generation is on demand, never triggered by normal Streamlit reruns. Generated copy supports English, Hindi and Telugu, normalises numerals to ASCII digits, remains editable and must pass the existing human QC before rendering.
- Editorial-card Auto layout evaluates subject-mask occupancy when available and image texture/edge density otherwise. Side gradients span the height of the safe text column; bottom treatments begin lower to avoid covering the centre portrait; Quote / Reaction anchors attribution/context lower within the safe zone. This applies only to the four editorial cards; Text Subject Cutout remains untouched.
- Manual Subject Cutout layout geometry remains cached for repeated, ordinary headlines. Keep Render Now and Preview all valid line-break options explicit; never re-render the final cutout frame merely because the headline, polygon, font, style or size widget changed.
- **Live render-to-Upload QC path repair (2026-10-18):** Standard Live and Top-5 render outputs are anchored to the repository root; the session stores resolved absolute paths; Upload QC resolves older relative session paths against the repository root and reports the missing/empty file path if the handoff fails. CI previously checked repository-root output paths, resolved session paths and Upload QC diagnostics.
- **Validation checkpoint (2026-10-20):** PR #120 (`fix/crop-card-autofill-layout`) contains the current crop/Card Studio changes. GitHub Actions previously passed the suite with 418 and then 419 tests passed (1 skipped); those successful commits predate the final original-resolution crop canvas and bidirectional crop-store isolation refinements. At the time of this checkpoint, the final-code workflow is still in `pip install -r requirements.txt`, before compilation or pytest. Do not call this factory Live-ready until CI passes for the final code tree and the crop modal has been manually smoke-tested on Windows (free rectangle, reset, apply, reopen/recrop, use original, and direct slide attachment in Test and Live).
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
- The root-level Scriptwriter headline is crisp dashboard-only metadata with no word-count limit; it is disconnected from standard Shorts rendering.
- Scriptwriter now generates hashtags and the public-upload comment in the same generation call.
- YouTube Upload QC was added with editable publish metadata and Public/Private upload lanes.
- Renderer text layout was corrected to use stroke-aware, screen-safe measurements so headline and subtitle characters do not clip at the canvas edges.
- Historical root-headline overlay/wrapping is no longer used by the standard Shorts renderer, and the root dashboard field is never copied into Text Subject Cutout. That card's independently editable text defaults from the source story title, then first-scene narration as fallback; editorial-card text and Top-5's six slide headlines remain separate.

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

This is the baseline for future Cricket pipeline changes. The established Cricket functionality remains usable. Card Studio’s four sports-editorial card types have now been promoted to Cricket and YT Trends Live at the user’s direction.

Card Studio checkpoint:
- Text Subject Cutout remains on its preserved shared Subject Cutout implementation, with polygon-flow enabled only for Deep-Dive Cricket and YT Trends. The four editorial cards are separately rendered by Card Studio and are now enabled in Cricket and YT Trends Live.
- Stat Highlight, Quote / Reaction, Head-to-Head and Key Fact / Milestone use the shared sports-editorial Card Studio in Test and in Cricket/YT Trends Live.
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
- **Deep-Dive Cricket:** Generates 3 research-backed editorial angles for human selection, producing 3–5 spoken slides, preferring four only when the story fits naturally. English Slide 1 capped at 13 words; Hindi/Telugu first-scene audio must measure ≤5.2 seconds. Narration remains 50–70 words and under 30 seconds.
- **YouTube Search Trends & Niche Sports:** Generates 3 research-backed editorial angles honoring search intent, producing 3–5 spoken slides. English Slide 1 capped at 13 words; Hindi/Telugu first-scene audio must measure ≤5.2 seconds; total narration 18–30 seconds (50–74 words). Preserves the raw search query context for SEO/Search packaging.
- **Top-5 Stories:** Generates a 6-slide package (Slide 1: hook headline ≤8 words with visual body copy; Slides 2–6: spoken headline + visual card body). Total spoken headline duration strictly under 30 seconds.

Unified Generation & Validation Architecture:
1. Gathers the primary source article and searches for up to two related current reports for factual grounding.
2. For Deep-Dive and YT Trends, generates 3 distinct editorial angles first. The chosen angle guides script generation.
3. Generates complete script draft with `openai/gpt-oss-120b`.
4. Performs strict local validation (scene count, word limits, duration bounds, filler/bait prohibition).
5. If validation fails, performs exactly one hidden complete rewrite with `openai/gpt-oss-20b` targeting the exact validation error.
6. Never exposes an invalid draft to Manual QC.

Publish Metadata Handoff:
- Standard non-Top-5 `headline`: crisp dashboard-only metadata with no word-count limit; never attached to the Short. Top-5's six-slide package headlines and cards remain unchanged.
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

