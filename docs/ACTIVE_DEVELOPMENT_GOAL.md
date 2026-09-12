# Active development goal

Updated: 2026-09-12

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

The version remains `1.6.0-dev.10` until these slices are integrated and release readiness is reviewed. No GitHub push or Release is part of this goal unless separately authorized.

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
| 0 | In progress | Active goal and handoff protocol drafted | Validate Skill, document architecture, run doc checks, commit |
| 1 | Not started | — | Inspect resource-library/right-sidebar routing and view containers |
| 2 | Not started | — | Trace publish persistence and lifecycle files |
| 3 | Not started | `features/19_prompt_studio_and_plugin_kernel.md` contains prior design | Narrow design to prompt studio only and map existing prompt sources |
| 4 | Not started | Single foreground stores observed | Map API locks, request ownership, and UI task keys |
| 5 | Not started | — | Integrate only after slices 1-4 pass |
