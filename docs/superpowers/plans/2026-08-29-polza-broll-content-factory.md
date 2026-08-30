# Polza B-roll Content Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a governed Polza image/video provider path and a repeatable Kraski vertical-Reel builder that produces one unpublished 10-second QA-checked pilot.

**Architecture:** OpenMontage gains a shared Polza Media API client plus first-class Flux-2 Pro and Grok Imagine Video tools. Content Factory consumes an approved manifest, enforces source/repetition/budget rules, stages media for a Kraski-specific Remotion composition, and delegates final encoding and QA to existing local tools.

**Tech Stack:** Python 3.11, `requests`, OpenMontage BaseTool registry, Remotion/React/TypeScript, FFmpeg/ffprobe, unittest/pytest, JSON manifests, macOS Keychain.

**Spec:** `docs/superpowers/specs/2026-08-29-polza-broll-content-factory-design.md`

## Global Constraints

- Keep the permanent cadence at exactly one Reel per week.
- Keep `publishing_authorized=false`; no publication is part of this plan.
- Use real bright, socially positive source media as the anchor.
- Never present a generated scene as a documented real Kraski class or event.
- Require 4-6 genuinely different shots and a 9:16 final master around 10 seconds.
- Render Russian text locally with restrained orange emphasis.
- Use Remotion as the approved default, HyperFrames only after a revised decision, and FFmpeg for final audio/encoding.
- Target 25-35 RUB and stop before paid generation when the maximum run cost exceeds 60 RUB.
- Do not retry a paid request or switch provider/model automatically.
- Never expose a key in Git, logs, artifacts, subprocess arguments, exceptions, or tests.

---

## File Map

OpenMontage:

- `lib/providers/polza.py`: authenticated Media API transport, pricing, polling, download, redaction.
- `tools/graphics/polza_flux_image.py`: Flux-2 Pro BaseTool adapter.
- `tools/video/polza_grok_video.py`: Grok Imagine Video BaseTool adapter.
- `tests/lib/test_polza_client.py`: transport, pricing, polling, download, and redaction tests.
- `tests/tools/test_polza_media_tools.py`: BaseTool contracts and registry discovery.
- `remotion-composer/src/KraskiVertical.tsx`: full-bleed multi-shot 9:16 composition.
- `remotion-composer/src/Root.tsx`: registers `KraskiVertical`.

Content Factory:

- `skills/content-video-api/tools/build_polza_reel.py`: approved-manifest validation, budget preflight, provider calls, staging, render, and evidence.
- `skills/content-video-api/tools/test_build_polza_reel.py`: source, role, repetition, cost, and authorization tests.
- `skills/content-video-api/tools/kraski-reel-example.json`: executable manifest example without secrets.
- `skills/content-video-api/SKILL.md`: production command, limits, and failure behavior.

## Task 1: Shared Polza Media API Client

**Files:**
- Create: `lib/providers/polza.py`
- Create: `tests/lib/test_polza_client.py`

**Interfaces:**
- Produces: `PolzaClient(api_key: str, session: requests.Session | None = None)`.
- Produces: `PolzaModelPrice`, `PolzaGeneration`, `PolzaError` dataclasses/classes.
- Produces: `get_model(model_id)`, `estimate_rub(model_id, parameters)`, `generate(model_id, input_payload)`, `wait(generation_id)`, and `download(url, output_path)`.

- [ ] **Step 1: Write failing transport and redaction tests**

Cover Bearer authentication, `/v1/models?include_providers=true`, `/v1/media`, `/v1/media/{id}`, output download, timeout, failed generation, and exceptions that replace the literal API key with `<redacted>`.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `.venv/bin/pytest tests/lib/test_polza_client.py -q`

Expected: collection/import failure because `lib.providers.polza` does not exist.

- [ ] **Step 3: Implement the minimal typed client**

Use `https://polza.ai/api/v1` by default, injected session methods for tests, bounded request timeouts, `time.monotonic()` deadlines, and binary streaming for downloads. Parse tiered prices with exact `Decimal` arithmetic and return RUB values without converting them to USD.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/lib/test_polza_client.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add lib/providers/polza.py tests/lib/test_polza_client.py
git commit -m "Add governed Polza media client"
```

## Task 2: First-Class Polza Image and Video Tools

**Files:**
- Create: `tools/graphics/polza_flux_image.py`
- Create: `tools/video/polza_grok_video.py`
- Create: `tests/tools/test_polza_media_tools.py`

**Interfaces:**
- Consumes: `PolzaClient` from Task 1.
- Produces: tool name `polza_flux_image`, provider `polza`, capability `image_generation`.
- Produces: tool name `polza_grok_video`, provider `polza`, capability `video_generation`.
- Produces: `data.cost_rub`, `data.estimated_cost_rub`, `data.request_id`, model, resolution, duration, output path, and artifacts.

- [ ] **Step 1: Write failing BaseTool contract tests**

Assert unavailable status without `POLZA_API_KEY`, available status with a placeholder key, correct model IDs, 5/7 RUB Flux estimates, 1.62/3.0375 RUB-per-second Grok estimates, payload shape, no retry policy, registry discovery, and redacted error text.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `.venv/bin/pytest tests/tools/test_polza_media_tools.py -q`

Expected: import failures for both new tools.

- [ ] **Step 3: Implement the Flux adapter**

Support 1K/2K, 9:16 and standard aspect ratios, zero to eight reference images, explicit output path, live price lookup with documented fallback estimates, and image content download.

- [ ] **Step 4: Implement the Grok adapter**

Support 480p/720p, 1-15 seconds, 9:16, text-to-video and image-to-video, explicit output path, live price lookup with documented fallback estimates, and MP4 probing after download.

- [ ] **Step 5: Run provider and registry tests**

Run: `.venv/bin/pytest tests/tools/test_polza_media_tools.py tests/tools/test_provider_model_defaults.py -q`

Expected: all tests pass and no existing provider default drifts.

- [ ] **Step 6: Commit**

```bash
git add tools/graphics/polza_flux_image.py tools/video/polza_grok_video.py tests/tools/test_polza_media_tools.py
git commit -m "Add Polza Flux and Grok media tools"
```

## Task 3: Kraski Vertical Remotion Composition

**Files:**
- Create: `remotion-composer/src/KraskiVertical.tsx`
- Modify: `remotion-composer/src/Root.tsx`

**Interfaces:**
- Produces: composition ID `KraskiVertical`.
- Consumes props: `{shots, captions, musicSrc, recipe, accentColor, backgroundColor}`.
- Each shot: `{src, mediaType, startFrame, durationFrames, cropMode, transition}`.
- Each caption: `{text, accent, startFrame, durationFrames, position}`.

- [ ] **Step 1: Add the typed props and composition implementation**

Implement full-bleed `Img`/`OffthreadVideo` scenes, stable absolute dimensions, bounded zoom/pan, short crossfades, three recipe-specific motion treatments, safe-area captions, orange emphasis, subtle dark readability backing, and optional music.

- [ ] **Step 2: Register the composition**

Register `KraskiVertical` as 1080x1920 at 30 fps with metadata duration calculated from the latest shot/caption frame.

- [ ] **Step 3: Run TypeScript verification**

Run: `npm run typecheck`

If the repository has no `typecheck` script, run: `npx tsc --noEmit`

Expected: zero TypeScript errors.

- [ ] **Step 4: Render a zero-cost local fixture**

Use four local color/image fixtures and render five seconds through Remotion. Verify ffprobe reports 1080x1920, H.264, 30 fps, and nonblank sampled frames.

- [ ] **Step 5: Commit**

```bash
git add remotion-composer/src/KraskiVertical.tsx remotion-composer/src/Root.tsx
git commit -m "Add Kraski vertical Remotion composition"
```

## Task 4: Deterministic Content Factory Reel Builder

**Files:**
- Create: `../Content Factory/skills/content-video-api/tools/build_polza_reel.py`
- Create: `../Content Factory/skills/content-video-api/tools/test_build_polza_reel.py`
- Create: `../Content Factory/skills/content-video-api/tools/kraski-reel-example.json`

**Interfaces:**
- Consumes: approved JSON manifest and OpenMontage project root.
- Produces: `preflight.json`, `source-manifest.json`, `decision-log.json`, `provider-receipts.json`, `remotion-props.json`, `qa-technical.json`, `manifest.json`, and final MP4.
- CLI: `build_polza_reel.py --manifest PATH --output-dir PATH [--execute-paid]`.

- [ ] **Step 1: Write failing manifest and budget tests**

Cover exact shot count, required roles, at least two real anchors, unique source hashes, recipe enum, total duration, positive social scene flags, generated-event claim rejection, 60 RUB stop, missing music, dry-run no network, and `publishing_authorized=false`.

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv/bin/python -m unittest skills/content-video-api/tools/test_build_polza_reel.py -v`

Expected: import failure for `build_polza_reel`.

- [ ] **Step 3: Implement validation and dry-run preflight**

Use dataclasses and structured JSON parsing. Hash every real source, reject duplicates, calculate scene frames, resolve the selected recipe, obtain catalog prices through a no-cost OpenMontage subprocess, and write preflight artifacts only after validation.

- [ ] **Step 4: Implement paid execution and rendering**

Load `POLZA_API_KEY` from the process environment only. Invoke the exact approved Polza tools, stop on first failure, stage local and generated media under the OpenMontage project directory, render `KraskiVertical`, mix reviewed music, and call existing `validate_vertical_video.py` with audible-audio enforcement.

- [ ] **Step 5: Run tests**

Run: `.venv/bin/python -m unittest skills/content-video-api/tools/test_build_polza_reel.py -v`

Expected: all tests pass without a live API call.

- [ ] **Step 6: Commit in Content Factory**

```bash
git add skills/content-video-api/tools/build_polza_reel.py skills/content-video-api/tools/test_build_polza_reel.py skills/content-video-api/tools/kraski-reel-example.json
git commit -m "Add governed Polza Reel builder"
```

## Task 5: Skill and Secret Integration

**Files:**
- Modify: `../Content Factory/skills/content-video-api/SKILL.md`
- Modify: `../Content Factory/skills/content-video-api/tools/check_openmontage_local.py`
- Modify: `../Content Factory/skills/content-video-api/tools/test_check_openmontage_local.py`

**Interfaces:**
- Produces: preflight visibility for Polza without displaying the key.
- Produces: documented Keychain load command and dry-run/paid-run commands.

- [ ] **Step 1: Add failing preflight tests**

Assert the report exposes `polza.account_api`, `polza.image_model`, and `polza.video_model` booleans, never a key value, and remains READY when Polza is absent because existing providers still work.

- [ ] **Step 2: Implement secret-aware preflight**

Read only the environment exposed to the child process. Report model availability through the OpenMontage registry and no-cost catalog lookup; never read or alter Handy settings.

- [ ] **Step 3: Document production use**

Add the exact dry-run command, Keychain setup/load pattern, paid execution command, 60 RUB cap, no-retry rule, and publication prohibition to the skill.

- [ ] **Step 4: Run the Content Factory tool suite**

Run: `.venv/bin/python -m unittest discover -s skills/content-video-api/tools -p 'test_*.py' -v`

Expected: all tests pass.

- [ ] **Step 5: Commit in Content Factory**

```bash
git add skills/content-video-api/SKILL.md skills/content-video-api/tools/check_openmontage_local.py skills/content-video-api/tools/test_check_openmontage_local.py
git commit -m "Document Polza Reel production workflow"
```

## Task 6: Separate Key and Unpublished Pilot

**Files:**
- Create outside Git: macOS Keychain item `content-factory-polza-api-key`.
- Create: OpenMontage `projects/kraski-polza-pilot-2026-08-29/` runtime artifacts.
- Create: Content Factory `output/reels/2026-08-29-polza-pilot/` reviewed package.

**Interfaces:**
- Consumes: confirmed Polza account, approved real photo-bank media, and one reviewed music track.
- Produces: final roughly 10-second 1080x1920 H.264/AAC MP4 and complete evidence package with `publishing_authorized=false`.

- [ ] **Step 1: Create a separate API key**

Use the logged-in Polza dashboard when available. Name it `Kraski Content Factory`, store it directly in macOS Keychain, and do not display it in terminal output. If dashboard authentication is unavailable, stop this task rather than silently reusing the Handy key.

- [ ] **Step 2: Select and audit source media**

Choose at least two bright, socially positive real sources from the current Telegram photo bank. Record hashes, source proof, age/activity match, and duplicate-history result.

- [ ] **Step 3: Prepare the pilot manifest and dry run**

Create a parent-useful `small-discovery` or `parent-question` script with 4-6 shots and no first-class offer. Run without `--execute-paid`; require PASS and estimated maximum cost at or below 60 RUB.

- [ ] **Step 4: Announce and execute the paid sample**

State the exact tool/provider/model, resolution, duration, and estimated cost. Generate only the approved B-roll assets; do not retry failures.

- [ ] **Step 5: Render and validate**

Render with Remotion, finish with FFmpeg, validate 1080x1920 H.264/yuv420p/AAC/30 fps/audible audio/nonblank frames, inspect a contact sheet, and confirm semantic match and no repeated visual.

- [ ] **Step 6: Package without publishing**

Copy only the approved result and evidence to Content Factory output. Keep `publishing_authorized=false` and do not modify daily markers or publication queues.

## Task 7: Final Verification, Commits, and Push

**Files:**
- Verify all files changed by Tasks 1-6.

**Interfaces:**
- Produces: clean scoped diffs, passing tests, pushed commits, and exact artifact paths/costs.

- [ ] **Step 1: Run OpenMontage verification**

Run: `.venv/bin/pytest tests/lib/test_polza_client.py tests/tools/test_polza_media_tools.py tests/tools/test_provider_model_defaults.py -q`

Run: `cd remotion-composer && npx tsc --noEmit`

- [ ] **Step 2: Run Content Factory verification**

Run: `.venv/bin/python -m unittest discover -s skills/content-video-api/tools -p 'test_*.py' -v`

Run the final vertical-video validator against the pilot MP4.

- [ ] **Step 3: Audit secrets and diffs**

Search staged diffs for `pza_`, `Authorization: Bearer`, API key literals, and Handy settings paths. Verify the unrelated `output/reports/growth-action-state.md` change remains untouched and unstaged.

- [ ] **Step 4: Commit remaining scoped changes**

Commit only new production code, tests, skill documentation, and non-sensitive evidence. Do not commit generated video or runtime project directories when ignored by repository policy.

- [ ] **Step 5: Push both repositories**

Push the current OpenMontage branch and Content Factory `main` only after verifying each upstream relationship and clean scoped status.
