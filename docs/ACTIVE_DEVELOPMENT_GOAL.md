# Active development goal

Updated: 2026-09-24

## Completed engineering stage — prompt architecture M1–M5

- Authorization: on 2026-09-24 the user enabled goal mode for the complete stage; M1–M5 may proceed without asking for a separate authorization at each milestone.
- Mainline: request composition, rule/data separation, finite experience presets, result contracts and request budgets/Overseer handoff are implemented. M1–M5 engineering acceptance is complete; release qualification remains separate.
- M5 implementation: connection-owned context/output limits; conservative estimated preflight at transport; raw and normalized usage/cache statistics; stable Overseer system rules with user data projections; proposed state and adjudication handoff; bounded content-free request observations and truthful developer coverage.
- Ownership: profile budget options persist with the existing connection repository and invalidate cached engines when changed. Runtime diagnostics retain 32 records in memory under a lock, expose no prompt/response body or credential, and are available through the existing protected developer endpoint.
- Budget policy: existing memory/retrieval owners retain responsibility for summarization and optional retrieval selection. Transport treats the retained assembled request as required, reports oversized sources, and rejects rather than silently truncating assets or commands. Unknown models use an explicitly labeled 32768-token conservative window, 4096 default output reservation and 10% estimate margin, configurable per connection.
- Acceptance: enforce zero provider calls on overflow; preserve output reserve; distinguish unavailable cache statistics from zero; stable Overseer rules; proposed state is visible to Overseer before live commit; disabled Overseer has zero calls; connection setting persists and cache reloads; UI distinguishes integrated read-only slices; full backend/build/browser regression.
- Quality boundary: deterministic acceptance proves request/state/UI behavior. Real-model literary comparison and provider cache effectiveness remain separate release-quality evidence; no claim of measured quality or cache-hit improvement is made from fake providers.
- Evidence (2026-09-24): `tools/run_checks.ps1` passed Python 389/389, frontend behavior verification and production build (126 modules); full Playwright/Edge passed 22/22. The browser checks exercise saved budget configuration and verify that Overseer receives current settlement state in user data, not entity data in static system rules.
- Delivery boundary: no paid API requests, version bump, package build, push or release in this stage closure. The current version label remains 1.6.0-dev.16; the new work is unreleased.
- Next after completion: resume W1 general world-change capture according to feature document 18. No further M-by-M user approval is required inside this stage.

## Completed unreleased patch — prompt architecture M4

- Final goal: implement the approved prompt architecture in bounded M1–M5 slices, then resume worldbook capture.
- Phase goal: make normal turns and rerolls share one strict settlement contract, calculate state changes on an isolated copy, and restore both memory and disk-visible state when a mutation cannot be committed.
- Implementation: model output is normalized before ledger/history/state mutation; malformed bars, Buffs, deletions and required influence reports reject the turn without guessing. StateManager plans on a copy and commits explicitly. Story API mutations keep a runtime checkpoint, save through same-directory atomic replacement, and restore the checkpoint if persistence fails. A failed reroll preserves the previously completed turn.
- Compatibility: existing settlement fields and the save schema remain unchanged. Unknown and duplicate influence reports are ignored with diagnostics, while a missing required triggered influence rejects the settlement. No repair-model call, universal patch schema, or additional story request was introduced.
- Status: implementation complete. Targeted M4 tests passed 33/33; the final one-command check passed Python 380/380, frontend behavior verification and a 126-module production build; Playwright/Edge passed 22/22. Documentation and the coherent Git commit close this slice.
- Known boundary: asynchronous worldbook capture and preference scheduling still require source-turn/revision validation in their owning later slices. Overseer budgeting and handoff order remain M5 work.
- Next verifiable slice after M4: M5 adds enforceable context budgets, normalized usage evidence, minimal Overseer projection, and prompt-workbench coverage. Do not resume worldbook capture inside M4 or M5.

The completed dev.16 node remains recorded below as historical evidence.

## Completed dev.16 patch — prompt architecture M3

- Final goal: implement the approved prompt architecture in bounded M1–M5 slices, then resume worldbook capture.
- Phase goal: M3 separates mandatory engine permissions from optional story-experience guidance, removes scenario-specific examples from always-on prompts, and exposes one finite advanced preset choice without creating an arbitrary prompt-import ecosystem.
- Implementation: player agency, causal continuity and the JSON/state contract remain mandatory. `AliveWorld default` adds only generic diversity and natural-progression guidance; `engine only` removes that experience slice from both future and settlement requests. Old saves and unknown values safely normalize to the default, and world-package recommendations can select the same setting.
- Prompt cleanup: police, guards, walkie-talkies, automatic alarms, ball lightning and prison-van examples no longer occupy the permanent engine prompt. Their underlying constraints are expressed as general permissions and causal rules and the concrete cases remain regression concepts.
- Status: complete. Targeted M3/world-package tests passed 67/67 before final versioning; full Python regression passed 366/366, the one-command frontend behavior/build check passed with 126 modules, and Playwright/Edge passed 22/22. Final versioned verification is recorded in the dev.16 changelog.
- Quality boundary: deterministic composition, settings, compatibility and UI behavior are verified. The paid 48-request real-model literary comparison was not run; it remains a pre-release quality check and this patch does not claim model-quality equivalence.
- Next verifiable slice: M4 centralizes result validation and transactional state application for normal and reroll paths. Do not resume worldbook capture or begin M5 budget/Overseer work inside M4.

The completed dev.15 node remains recorded below as historical evidence.

## Completed dev.15 patch — prompt architecture M2

- Final goal: implement the approved prompt architecture in bounded M1–M5 slices, then resume worldbook capture.
- Phase goal: M2 separates reusable instructions from request data in both future and settlement requests, registers explicit runtime projections, and keeps older developer templates that embed legacy variables usable without duplicate data.
- Implementation: default core prompts now contain rules only. Character/style/preferences/history are ordered before turn-scoped world retrieval, state, action and adjudication in the user message. Runtime prompt parts report their truthful feature/configuration/turn provenance, while normal and reroll settlement share one layout and retain their distinct trace labels and output limits.
- Compatibility: an active legacy core that still contains `{world_info}`, `{character_info}` or `{style_info}` renders those values in its original system location; the builder omits the corresponding user projection. No player save schema or model-call count changed.
- Status: complete. Targeted prompt/game tests passed 26/26; full Python regression passed 362/362; the one-command regression and 126-module frontend build passed; Playwright/Edge passed 22/22 after its asset-injection assertions were updated to inspect the new user data layer.
- Next verifiable slice: M3 removes duplicated experience rules behind a limited preset/on-off contract and proves disabled features contribute no rules, fields or data. Do not begin M4 result validation or resume worldbook capture inside M3.

The completed dev.14 node remains recorded below as historical evidence.

## Completed dev.14 patch — prompt architecture M1

- Final goal: implement the approved prompt architecture in bounded M1–M5 slices, then resume worldbook capture.
- Phase goal: M1 creates one pure settlement request builder and an observable request plan for normal turns and rerolls, without changing either path's wire text, generation settings or call count.
- Implementation: `core/story_prompt_builder.py` receives an explicit read-only snapshot; `core/prompt_studio.py` adds the system/user request plan and content-free user-segment manifest. Both callers keep their existing orchestration and error handling.
- Compatibility: normal settlement retains its length-sensitive output limit and runtime-slice order; reroll retains its fixed 3000-token limit and legacy order. The two known differences are now explicit rather than silently normalized.
- Status: complete. Targeted prompt/game tests passed 31/31; full Python regression passed 356/356; production frontend build passed with 126 modules; Playwright/Edge passed 22/22, including full asset-to-story injection, retry/undo, cross-story concurrency and developer prompt override/restore.
- Next verifiable slice after M1: M2 separates fixed rules from task data and registers explicit runtime projections while preserving legacy developer overrides. Do not begin M2 or worldbook capture inside the M1 commit.

The completed dev.13 node remains recorded below as historical evidence.

## Current dev.13 patch

- Final goal: extract the settlement state guidance and output contract into independently observable prompt slices without adding a model request or changing the rendered settlement prompt, then make the verified Windows package/release workflow reproducible.
- Phase 1: split `story.settlement.core`, `story.state.guidance`, and `story.state.contract` at stable contiguous boundaries; migrate any legacy full-core developer override atomically; lock composition equivalence and state-field coverage in tests.
- Phase 2: add an explicit release orchestrator that verifies version/changelog/worktree/tooling, runs automated checks, builds the portable ZIP, extracts only the matching changelog section, and creates a GitHub prerelease only when `-Publish` is supplied.
- Non-goals: no content-preset product UI, no prompt rewording/reordering, no additional LLM call, no real GitHub release in this development turn, and no state-data schema migration.
- Recovery: prompt overrides remain versioned in `UserData`; legacy full-core overrides are split before the first dev.13 read and the original text is represented by the three resulting records. Release failures leave local package artifacts for diagnosis and never modify `UserData`.
- Acceptance: exact rendered-prompt equivalence, required state-field regression, legacy override migration, release-script dry-run/preflight tests, Python suite, frontend build, complete Playwright suite, documentation, and a clean Git commit.
- Status: complete. Prompt/release targeted tests passed 23/23, Python regression passed 351/351, the production frontend build passed with 126 modules, and Playwright/Edge passed 22/22. The release preflight passed against a clean dev.13 commit, generated the exact version notes, and classified the channel as pre-release; no package or online Release was created.
- Historical next-slice proposal: return to worldbook capture. Superseded on 2026-09-15 by the prompt architecture design gate above.

The completed dev.12 node remains recorded below as historical evidence.

## Completed dev.12 patch

- Final goal: remove the remaining copy-button clutter, restore one reliable expanded editor for every ordinary multiline editing surface, and design—but do not yet implement—the next prompt architecture migration.
- Phase goal: ship the UI corrections with browser evidence; record the v1.5—v1.6 backlog and identify the next verifiable slice.
- Completion evidence: production frontend build, targeted Playwright assertions for special bubbles and expanded editing, documentation review, and a Git commit.
- Next verifiable slice after this patch: a read-only `PromptVariableRegistry` with searchable hover/click help, legacy aliases and composition-equivalence tests; then add layer/cache metadata before splitting the state-bar contract from `story.settlement.core`.
- Design record: [`features/20_prompt_layers_variable_registry_and_backlog_audit.md`](features/20_prompt_layers_variable_registry_and_backlog_audit.md).
- Status: complete. Canonical variables, legacy aliases, safe metadata API, searchable explanations, cursor insertion and prefix hashes are implemented without changing runtime prompt text or model-call count. Python regression passed 342/342, the production frontend build passed with 126 modules, and the complete Playwright/Edge suite passed 22/22.
- Next verifiable slice: design and lock byte-level equivalence fixtures for extracting `story.state.contract` and `story.state.guidance` from the settlement core; do not implement content presets or rearrange prompt order in the same slice.

The completed dev.11 release node remains recorded below as historical evidence.

## Mainline

Continue improving AliveWorld as a focused AI story game. Do not refactor it into an “everything is a plugin” agent platform. Preserve the existing domain-oriented architecture and repair the concrete ownership, persistence, concurrency, and interaction gaps exposed below.

## Final goal

Deliver one coherent, testable development node in which:

1. developers can inspect and safely override named prompt slices;
2. card assets return to the in-game right sidebar while world packages remain in the low-frequency resource library;
3. requests belonging to different stories or workshops can continue independently when the player switches views;
4. story, workshop, and log views open at their newest content without a visible top-to-bottom scroll;
5. story text is selectable without per-bubble copy clutter, while logs support selection, per-entry copy/export, and multi-entry export;
6. published workshop conversations remain available after restart without reopening an old published draft as editable state;
7. implementation notes and release notes are categorized by feature area;
8. another AI session can resume from repository evidence rather than the prior chat transcript.

The integrated node is versioned `1.6.0-dev.11`. On 2026-09-13 the user explicitly authorized a Windows portable build, GitHub push, and prerelease so it can be updated and tested.

## Architecture finding

The codebase is moderately well modularized, not “completely independent by file.” That phrase is neither true nor desirable: features must collaborate through stable contracts.

- Strong boundaries: backend domain modules under `core/`, route modules under `api/v1/`, frontend API modules, stores, and most components are separated by responsibility.
- Appropriate composition roots: `core/game_session.py`, `api/v1/game_routes.py`, and `aliveworld-ui/src/App.vue` coordinate cross-feature behavior.
- Current hotspots: `AssetPanel.vue` combines four asset domains and several workflows; prompt text is split between YAML and Python; `gameStore.js` and `workshopStore.js` each model only one foreground context; workshop publish/reopen semantics couple editable draft state to conversation visibility.
- Rule: split a hotspot only when the new boundary owns distinct state or behavior. Do not create one-file wrappers merely to claim independence.

## Prioritized slices

### Slice 0 — continuity and design gate (P0)

- Add this active-goal document and root handoff protocol.
- Create a reusable long-running software development Skill.
- Record ownership, lifecycle, concurrency, migration, and acceptance before code changes.
- Completion evidence: skill validation, documentation review, clean diff, Git commit.

### Slice 1 — navigation, scroll, and copy/export corrections (P1)

- Right sidebar exposes the four high-frequency card asset categories; resource library retains images and world packages.
- Story, workshop, and log containers set their initial scroll position to the bottom before presentation; subsequent auto-scroll occurs only when appropriate and never animates from the top on view entry.
- Remove copy buttons from ordinary player/AI story bubbles; keep selectable text.
- Logs are selectable and provide per-entry copy/export plus selection and batch export.
- Acceptance: frontend unit or component assertions where available, production build, Playwright flows for the restored navigation and each scroll/copy/export behavior.

### Slice 2 — workshop conversation history (P1)

- Editable workshop drafts and immutable published conversation history are separate concepts.
- Publish persists a history snapshot keyed by workshop ID, asset identity, type, scope/story ID, timestamps, and resulting revision. It contains conversation and safe operation summaries, never API keys or raw hidden credentials.
- Reopening an asset shows its latest history read-only and offers an explicit new/resumable draft path. Deleting the owning story follows existing story deletion; global asset history follows explicit asset lifecycle rules and is not silently discarded on publish.
- Existing resumable drafts migrate without data loss; old published files, if present, are indexed lazily.
- Acceptance: publish, restart, read history, start new draft, rename/delete lifecycle, and local/global scope tests.

### Slice 3 — prompt slice registry and protected editor (P1, prerequisite design already exists)

- Implement stable prompt IDs, default sources, ordered composition, override versions, token estimates, and a request-source manifest without increasing model calls.
- Developer mode requires a locally stored salted password hash and an expiring in-memory unlock token. It prevents accidental editing; it is not DRM or system-level encryption.
- Built-in prompts remain immutable. Edits create versioned user overrides with diff, restore, and validation. Ordinary players do not see developer controls.
- Initial migration covers the story/future/player-agency/continuity/world-change path before other prompt families; the UI must label unmigrated hard-coded prompts rather than imply full coverage.
- Acceptance: auth boundary, baseline/override/restore, composition equivalence, token/source manifest, restart persistence, and no-secret-log tests.

### Slice 4 — keyed background task concurrency (P1, highest implementation risk)

- Backend permits concurrent work across different story/workshop keys while serializing mutations of the same key.
- Frontend stores task state by stable story/workshop identity instead of one foreground `isProcessing`/`busy` flag. Results are committed to their origin context even after the player switches views.
- Story cards and workshop navigation show queued/running/completed/failed state. Returning to a context displays its current data without cancelling another context.
- Same-story turn submissions are queued or rejected deterministically; they never race writes. Closing/restarting the app leaves already committed data valid and reports interrupted ephemeral work honestly.
- No promise of parallel model throughput beyond the configured provider limits. Concurrency is bounded and respects task routing/rate limits.
- Acceptance: two-story overlap, story plus workshop overlap, same-story serialization, mid-request switching, failure isolation, reload recovery, and save integrity under fake-model and browser tests.

### Slice 5 — release integration (P1)

- Run the full Python suite, production frontend build, complete fake-service Playwright acceptance, and targeted Windows packaged smoke test if packaging is authorized.
- Update feature documents, roadmap, and both human-facing and technical categorized changelogs.
- Review version bump, package, GitHub push, and Release separately with the user.

## Non-goals

- No general plugin runtime or arbitrary generated Python/JavaScript execution.
- No conversion of AliveWorld into a general agent tool.
- No mobile redesign, community backend, Steam integration, or new model provider in this node.
- No simultaneous mutation of one story by multiple turns.
- No claim that a password-protected local editor is strong security.

## Progress ledger

| Slice | State | Evidence | Next action |
| --- | --- | --- | --- |
| 0 | Complete | Skill validator passed; repository protocol and goal committed as `64a0e4c` | Keep this ledger current after every slice |
| 1 | Complete | Frontend production build: 124 modules; Playwright/Edge: 17/17 passed | Commit navigation, scrolling, selection, copy and export changes |
| 2 | Complete | 327/327 Python tests; frontend build 124 modules; targeted Edge publish/reopen flow 2/2 passed; commit `458b1bc` | Preserve immutable workshop history contract |
| 3 | Complete | Prompt/auth/API/composition/trace 15/15; frontend build 126 modules; Edge override/restore 1/1 | Commit prompt studio slice |
| 4 | Complete | Keyed lock/session tests 3/3; frontend build 126 modules; deterministic concurrency Edge flows 6/6 | Commit keyed concurrency slice |
| 5 | Complete / release ready | Python 338/338; frontend build 126 modules; Playwright/Edge 22/22; portable verification passed; packaged health reports `1.6.0-dev.11` and `packaged=true` | Push development branch and main, tag and publish the authorized prerelease |

## Slice 1 implementation notes

- The resource library now owns images and world packages only. The right sidebar owns stories, worldbooks, characters, styles, entities, and local story settings.
- `useBottomAnchoredScroll` supplies immediate initial positioning and follow-only-when-near-bottom behavior. Story content additionally observes late image sizing so loaded images cannot leave the viewport above the newest message.
- Ordinary player/AI bubbles remain selectable and no longer display copy controls. Special diagnostic/future bubbles retain explicit copy affordances where their structured content is otherwise harder to select coherently.
- Logs remain local and already redacted by the backend. Per-entry and batch export serialize the currently returned safe log records in the browser; no export request uploads content.
- Playwright now prefers the repository virtual environment automatically, falling back to system Python only when it is absent.

## Slice 2 implementation notes

- Existing per-workshop JSON files are the durable source of both drafts and completed records. Published records are projected through `core/workshop_history.py`; no second copy of the same transcript is created.
- A published workshop is now terminal and read-only at both domain and API boundaries. “Continue” creates a distinct session against the latest formal asset, preventing an old published draft from silently becoming editable again.
- Reopening any supported asset returns all matching published conversations newest-first. The central workspace displays them as collapsible read-only rounds while keeping the current draft separate.
- History projection whitelists only role and content from player/assistant conversation messages. Internal/system records, drafts, model credentials, and request prompts are not exposed as chat history.

## Slice 3 implementation notes

- Built-in prompt sources remain in their owning YAML/Python modules. `PromptSlice` is a registry and composition boundary, not a second copy of every prompt.
- Only the six story future/settlement core, agency, and continuity slices are editable in the first migration. Dynamic length/preferences/suggestions and unmigrated world/workshop families are visible but read-only.
- Overrides are atomically saved under the portable user-data tree and selected at composition time. The old unprotected bulk YAML endpoint returns 410.
- Developer passwords use salted PBKDF2-SHA256 hashes. Unlock tokens are ephemeral and protect against accidental access, not users with filesystem/process control.
- Request traces record the ordered slice manifest and hashes so a defect can be tied to the actual composition without duplicating prompt bodies into metadata.

## Slice 4 implementation notes

- `core/session_manager.py` owns active-session identity and aggregate mutation guards. API route modules translate conflicts to HTTP 409; domain objects remain unaware of HTTP and frontend state.
- The frontend game store is a keyed context collection rather than a single foreground record. Story responses, failures, status bars, suggestions, last actions and draft input are committed by origin session.
- The workshop store uses the same keyed-context idea across all five workshop types while keeping domain-specific API adapters separate. Selecting another asset changes only the active key and does not discard the pending Promise or its context.
- Story settings autosave captures the originating session and an immutable payload snapshot. Save lifecycle operations share the story lock and retarget the session index after rename.
- Provider request limits remain governed by connection configuration. This slice guarantees application ownership and write integrity, not unlimited external throughput.
