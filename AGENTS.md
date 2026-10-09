# AliveWorld development handoff

Before changing code, read these sources in order:

1. `docs/ACTIVE_DEVELOPMENT_GOAL.md` — the one active mainline and next slice.
2. `docs/MASTER_DESIGN.md` — product boundaries and canonical architecture.
3. The feature documents linked by the active goal.
4. `docs/VERSION_ROADMAP.md` — completed and planned version slices.
5. `docs/DECISIONS_AND_IDEAS.md` — confirmed decisions and parked ideas.
6. `docs/CHANGELOG.md` — implementation history and current unreleased work.
7. `docs/TESTING.md` — verification layers and commands.

Then inspect `git status`, the current branch, recent commits, `VERSION`, the actual implementation, and relevant tests. Documents express intent; only code and verification establish current behavior.

Keep one active mainline. Record incoming issues P0-P3 without silently replacing it. Large features require a design gate covering user goal, non-goals, data lifecycle, permissions/privacy, recovery, model-versus-code responsibility, shortest UI path, migration, concurrency, and acceptance.

Product design and engineering contracts are different gates. Before claiming a major mode is designed, explain and discuss its core player loop, value hypothesis, required subfeatures and scope with the user. Record confirmed requirements separately from proposed mechanisms, with core/play-upgrade/UX categories and P0-P3 priority. A technically consistent API/schema document is not user approval of the product vision.

Implement one independently verifiable slice at a time. Keep domain logic, API mapping, client state, and UI presentation in their own boundaries; composition roots may coordinate but must not absorb whole features. Update the active goal, feature document, categorized changelog, and test evidence with each slice.

## Delivery speed and validation scope (user instruction, 2026-10-09)

Design the smallest complete player workflow and its module ownership, then implement it directly. Do not add speculative compatibility, generic frameworks, layers of internal type checks, or exhaustive defensive handling for hypothetical states. Validate external API/model/file inputs once at their owning boundary; internal functions rely on that contract. Keep necessary business rules for concurrency, save integrity, privacy and duplicate-charge prevention. Existing isolated validators/parsers/storage guards may remain; do not expand or relocate them into story orchestration merely to satisfy an audit.

Run focused tests during implementation and one risk-appropriate integration gate at delivery, not every broad suite after every helper. Record concise current evidence and categorized changes, not another copy of the historical progress ledger in every document. New standalone foundations are not a finished player feature. If a design choice really needs the user, explain it in plain language; otherwise make reversible choices and continue without micro-approvals.

Do not commit player data, API keys, logs, generated packages, or unrelated worktree changes. Do not push, tag, publish a release, delete remote state, or bump the public version unless the user explicitly authorizes it.
