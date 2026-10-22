# Gemini 3.8 defaults and custom OpenRouter model

## Objective and authorization
User explicitly requests local implementation: default to Gemini 3.8 Flash for Google AI Studio and OpenRouter; show an editable model field beneath the OpenRouter API key, persist the user's custom provider/model ID, and use it in requests. No push, PR, deployment, remote execution, or real paid provider calls authorized.

## Problem, scope and constraints
Current defaults are Gemini 3.5 Flash and OpenRouter model is global. Add a user preference with a migration, extend the existing correction-provider preference endpoint, and use the preference for validation/corrections including fallback. Google uses native `gemini-3.8-flash`; OpenRouter uses `google/gemini-3.8-flash`. Preserve key encryption and permissions. Rubric generation currently uses Google only and inherits its new default.

Governance: medium for provider routing/profile preference; requested default config changes explicitly authorized. No authentication/security policy changes. Preserve existing architecture and incumbent form styling. Existing oversized files must not receive unrelated refactors; extract a small UI component.

## Execution and delivery
- Route: delegated direct. Mapping requires 4+ files; writer requires 2+ non-trivial files. Read-only mapping completed by `map_models` before source writes.
- Strict TDD: enabled by user-provided AGENTS instructions. Backend runner `python -m pytest` (backend cwd), lint `python -m ruff`; frontend `npm run test -- <targets>`, `npm run build`, `npm run lint`. Dependencies available for Python; frontend requires `npm ci`.
- RDD: off/default, observed `gentle-ai review mode status`; delivery disabled/unmanaged, no native reviews.
- Delivery strategy: ask-on-risk; estimate approximately 390 authored changed lines across two coherent work units, possible range 350–460. User chose `stacked-to-main` (PRs encadenados hacia main) after the ODD budget question. Keep backend T1 and frontend T2 as coherent commit/slice boundaries. No PRs authorized.
- Branch: `codex/openrouter-custom-model`, based on clean `main`.
- Engram topic: `odd/openrouter-custom-model/tasks`; mirror full file plus locator and read back.

## Tasks
- [x] T1 Backend: defaults, per-user model preference/migration, existing preference API, request validation and primary/fallback routing, tests and configuration examples. Route delegated (multi-file writer). Verified default/blank/custom/malformed IDs, profile round-trip without key reentry, HTTP request and metadata, primary/fallback, and real SQLite persistence/migration backfill/new-user default/downgrade preserving users. Commit identity recorded after commit below.
- [ ] T2 Frontend: accessible OpenRouter-only field directly below key with default/custom editing and save/reload through existing preference endpoint; service/types wiring and meaningful UI tests. Route delegated (multi-file writer). Acceptance: Google hides field; OpenRouter defaults correctly; custom value saves and survives reload; model update requires no key reentry; loading/error behavior follows form conventions. Checks: baseline/RED/GREEN/triangulation, focused and full tests, build, lint and visual check if runnable. Commit evidence pending.

## Progress and verification
- Mapping complete; no source changes before task creation. Main was clean.
- Key model routing must cover both primary OpenRouter and Gemini-to-OpenRouter fallback.
- No generic profile update endpoint exists; extend existing `/correction-provider` preference endpoint rather than adding another route.
- Initial mirror saved/read back as Engram observation #21; subsequent updates mirror after each task.
- T1 strict TDD: safety baseline 43 passed; RED 14 failed/1 passed; GREEN + triangulation 16 regression tests passed; import refactor rerun 16 passed.
- T1 final check from backend: `python -m pytest tests/unit/integrations tests/unit/schemas/test_perfil_provider.py tests/unit/test_openrouter_model_preference.py tests/unit/services/test_ia002_failover.py tests/unit/routers/test_perfil_delete_api_key.py -q` -> 109 passed, 4 existing deprecation warnings (Pydantic and UTC model default).
- Migration head: `python -m alembic heads` -> f8b4d2e6c901 (single head). SQLite upgrade/backfill/custom ORM persistence/downgrade tested; production database not contacted.
- T1 scoped Ruff: new files pass; 36 findings in changed legacy files are identical before/after, zero introduced. `git diff --check -- backend` passes.
- T1 authored count: 216 lines (65 existing + 21 migration + 130 tests), excluding task bookkeeping. Rollback boundary: backend files in T1 commit, downgrade migration first. RDD disabled/unmanaged.
- T2 independent frontend writer preparing tests/component while T1 runs; no overlapping source ownership.
- Runtime harness: mocked provider HTTP boundary and profile UI tests; real provider requests excluded because keys/paid calls are unnecessary.
- Rollback: revert feature commits and downgrade added migration, preserving unrelated behavior.

## Next step
Commit verified T1, finish T2 verification, then record both work-unit commit identities and final delivery status.
