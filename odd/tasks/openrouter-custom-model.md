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
- [x] T2 Frontend: accessible OpenRouter-only field directly below key, default/custom editing and save/reload through existing preference endpoint; service/types wiring and UI tests. Route delegated (multi-file writer). Verified Google hides field, correct default, custom save/reload without key reentry, blank fallback, pending/error states. Commit identity recorded after commit below.

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
- T1 work-unit commit: `5e29277` (`feat(correcciones): support per-user OpenRouter models and Gemini 3.8 defaults`). Future stacked-to-main slice 1 contains this commit; no PR created.
- T2 independent frontend writer completed tests/component while T1 ran; no overlapping source ownership.
- T2 strict TDD: safety baseline existing profile tests 3 passed; RED 5 failed/2 passed (after fixing test mock reset); GREEN + triangulation 10 targeted tests passed. No behavior refactor needed after GREEN.
- T2 `npm run test`: 31 files, 150 tests passed. `npm run build`: TypeScript + production/PWA build passed, existing stale Browserslist advisory.
- T2 scoped ESLint for new component/tests/service/types passes. Full `npm run lint`: 66 errors/4 warnings from existing code; changed PerfilPage has identical HEAD baseline (1 set-state-in-effect error/1 Moodle dependency warning). No unrelated lint fixes.
- Impeccable detector on changed UI returns [] exit 0. First bare launcher invocation was unavailable, corrected to absolute skill launcher. `git diff --check` passes. Live authenticated visual check skipped (no authenticated runtime used); jsdom tests cover labels, visibility/order, save/reload and error/loading behavior.
- T2 authored count: 219 lines across 6 frontend files; accumulated implementation 435 lines excluding task bookkeeping. User-selected stacked-to-main strategy applies: slice 1 backend commit, slice 2 frontend commit; no PRs published. RDD disabled/unmanaged.
- T2 rollback boundary: 6 frontend files in T2 commit; independent from backend migration/default behavior.
- T2 work-unit commit: `b4e198c` (`feat(ui): configure custom OpenRouter model from profile`). Future stacked-to-main slice 2 contains this commit; no PR created. Final task bookkeeping is a separate docs commit.

## TDD cycle evidence
| Task | Test file | Layer | Safety net | RED | GREEN | Triangulate | Refactor |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | backend/tests/unit/test_openrouter_model_preference.py | Unit + mocked HTTP + SQLite migration | 43 passed | 14 failed | 16 passed | Default/custom/blank/invalid, primary/fallback, DB persistence | Imports cleaned, 16 passed |
| T2 | frontend/src/features/perfil/pages/PerfilPage.model.test.tsx; frontend/src/features/perfil/services/perfil-service.test.ts | UI + service contract | 3 passed | 5 failed | 10 targeted passed | Default/custom/reset/reload/pending/error/provider visibility | No further refactor needed |
- Runtime harness: mocked provider HTTP boundary and profile UI tests; real provider requests excluded because keys/paid calls are unnecessary.
- Rollback: revert feature commits and downgrade added migration, preserving unrelated behavior.

## Next step
Local implementation and verification complete. Deployment remains user-owned: run `alembic upgrade head` in the deployment environment before starting the updated backend, and update explicit GEMINI_MODEL/OPENROUTER_MODEL environment overrides if present. No production migration, remote execution, paid model calls, push or PR performed. Existing repository lint findings and live authenticated visual verification remain outside completed checks, as disclosed above.
