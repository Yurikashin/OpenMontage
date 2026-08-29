# Polza B-roll for Kraski Content Factory

Date: 2026-08-29
Status: approved design, awaiting implementation plan

## Objective

Build a reusable advanced editing path for the Kraski Detstva weekly Reels. The
system combines approved real photo-bank media with narrowly scoped generated
B-roll, deterministic Russian captions, reviewed music, technical validation,
and an explicit human publication gate.

The first production target is one unpublished 9:16 test Reel of about 10
seconds. The permanent cadence remains one Reel per week.

## Scope

The implementation extends the existing OpenMontage `hybrid` pipeline and the
Content Factory `content-video-api` boundary. It does not add a second
orchestrator, publish automatically, or move creative rendering to the server.

Included:

- Polza Media API adapters for Flux-2 Pro images and Grok Imagine Video B-roll;
- safe API-key loading without committing secrets;
- cost estimation, per-run budget caps, and actual-cost receipts;
- 4-6-shot vertical story planning with source/B-roll roles;
- three repeatable but visibly different Kraski edit recipes;
- deterministic Russian captions with orange emphasis;
- reviewed music and final FFmpeg normalization;
- semantic, repetition, privacy, visual, audio, and technical gates;
- one local, unpublished test Reel and its evidence package.

Excluded:

- unattended publication;
- bulk generation;
- full cloud rendering;
- presenting generated scenes as documented events in a real branch;
- provider fallback after a paid failure without an explicit revised decision.

## Architecture

### Shared Polza client

Add a small provider client under `lib/providers/` that owns:

- `GET /v1/models` capability and live-pricing lookup;
- `POST /v1/media` generation requests;
- status polling and bounded timeouts;
- output download and temporary-link handling;
- response normalization and actual RUB cost extraction;
- sanitized errors that never include an API key or authorization header.

The client accepts an injected HTTP session for deterministic tests. It does not
contain creative decisions.

### Provider tools

Add first-class auto-discovered BaseTool implementations:

- `polza_flux_image`: Flux-2 Pro, 1K/2K, reference-aware image generation;
- `polza_grok_video`: Grok Imagine Video 1.5 Preview, 480p/720p, 1-15 seconds,
  text-to-video and image-to-video.

Both tools expose status, schema, supported capabilities, estimated cost,
runtime, artifacts, actual cost, provider/model identifiers, and user-visible
verification requirements. They use `POLZA_API_KEY` and remain unavailable when
the key is absent.

### Kraski production wrapper

Add a deterministic Content Factory command that:

1. reads a reviewed Reel brief and source manifest;
2. validates source existence, hashes, dimensions, and duplicate history;
3. creates a 4-6-shot plan using roles `hook`, `context`, `turn`, and `payoff`;
4. marks each shot as `real_source`, `generated_image`, or `generated_video`;
5. calculates the maximum possible charge before any paid call;
6. invokes OpenMontage only after the preflight passes;
7. composes the approved assets and records all provider receipts;
8. runs Content Factory video QA and writes `publishing_authorized=false`.

The wrapper may plan and validate without an API key. Paid generation requires a
configured key and a budget that covers the full proposed run.

## Content Rules

- Real, bright, socially positive material is the default anchor.
- Prefer children playing together, smiling, moving, using swings, creating, or
  interacting with an adult.
- Reject lonely, visually sad, floor-only, low-quality, repeated, or semantically
  mismatched scenes.
- Age, activity, clothing, season, branch claim, and accompanying text must agree.
- Generated children must not be described as a verified Kraski class, group, or
  event. When a real-event claim is needed, use only source-proof media.
- Do not render Russian words inside generated images or provider video.
- The script has one parent-useful idea and follows `hook -> turn -> payoff`.
- The ending is a concrete low-pressure action, not `Давай, присоединяйся`.

## Edit Recipes

The recurring system rotates among three recipes and records the selected recipe
in the decision log:

1. `bright-observation`: real scene, detail insert, shared activity, calm payoff;
2. `parent-question`: visual question, two contrasting details, answer, next step;
3. `small-discovery`: close detail, reveal, group reaction, useful parent takeaway.

Each recipe still requires at least four genuinely different shots. The recent
visual ledger blocks reuse of the same opening composition, image hash, or shot
sequence inside the configured lookback window.

## Composition

The approved default runtime is Remotion because the weekly format needs exact
Russian captions, stable timing, reusable QA, and predictable 9:16 output.
HyperFrames remains an available explicitly selected alternative for a more
expressive one-off piece. FFmpeg performs final audio mixing, normalization, and
delivery encoding.

The approved authoring mode is templated with controlled variation. It reuses
mechanics while rotating the three recipes, transitions, crop behavior, caption
placement, and orange emphasis. Atelier mode is reserved for separately approved
hero campaigns.

## Audio and Captions

- Music must come from an approved licensed track or a reviewed generated sample.
- Dialogue and narration are optional; no voice is generated for the first test.
- Final audio is AAC stereo with audible but non-dominant music.
- Captions are rendered locally from deterministic Russian text.
- Orange emphasis is limited to one key phrase per beat.
- Caption safe areas account for Instagram, YouTube Shorts, and VK overlays.

## Budget Governance

The default first-pass target is 25-35 RUB for a 10-second Reel. The hard run cap
is 60 RUB.

- Flux-2 Pro: use 1K unless 2K is justified by a full-frame still.
- Grok video: default to 720p and generate only the planned B-roll duration.
- No automatic paid retry.
- No silent model or provider fallback.
- A failed paid call is logged with its charged amount when present.
- Any revised provider/model choice is appended to the decision log and requires
  user approval before another paid call.

Live catalog pricing is fetched during preflight. If the maximum possible cost
cannot be calculated, generation stops.

## Secret Handling

Create a Content Factory-specific Polza key in the existing account when account
access permits it. Do not reuse or modify the Handy configuration.

Store the key in macOS Keychain and expose it to OpenMontage only for the child
process. Never write it to Git, project artifacts, logs, command receipts, test
fixtures, or rendered metadata. Tests use placeholder keys and injected fake HTTP
responses.

## Artifacts and Evidence

The OpenMontage project directory contains:

- approved brief and decision log;
- source manifest with hashes and source-proof references;
- scene plan and per-shot generation prompts;
- provider request IDs, model IDs, duration, resolution, and actual cost;
- generated assets and final vertical MP4;
- preview frame/contact sheet;
- semantic review, repetition report, and technical QA report;
- final manifest with `publishing_authorized=false`.

Content Factory receives the reviewed MP4 package only after all local gates pass.

## Failure Handling

- Authentication failure: stop and report auth; do not modify another application's key.
- Insufficient balance: stop before generation and report the calculated deficit.
- Provider failure: preserve receipt and stop; do not switch provider automatically.
- Semantic mismatch: reject the asset without publishing and require a revised prompt.
- Technical failure: do not copy the MP4 into the weekly package.
- Missing source proof: do not replace it with a generated imitation.

## Tests

OpenMontage tests cover:

- request payloads for both models;
- cost calculation from live-shaped catalog fixtures;
- status polling, timeout, failure, and output download;
- secret redaction;
- auto-discovery and selector routing;
- unavailable status without a key;
- actual-cost and artifact metadata.

Content Factory tests cover:

- source and duplicate validation;
- 4-6-shot and role requirements;
- generated/real source labeling;
- recipe rotation and repetition blocking;
- 60 RUB hard budget stop;
- publication authorization remaining false;
- final 1080x1920 H.264/AAC video QA.

## Acceptance Criteria

1. Polza image and video tools are discovered by OpenMontage when the key is exposed.
2. Preflight reports exact model, resolution, duration, and maximum RUB cost.
3. A dry run creates a complete plan without making a paid request.
4. One approved paid test creates a roughly 10-second, four-or-more-shot 9:16 Reel.
5. The final file passes Content Factory semantic and technical video gates.
6. The package records actual cost and retains `publishing_authorized=false`.
7. No secret appears in Git, logs, artifacts, subprocess arguments, or test output.
