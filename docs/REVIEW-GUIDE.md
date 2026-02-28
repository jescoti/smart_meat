# Smart Meat PR Review Guide

## Overview

This PR implements the full Smart Meat MVP — a mailing list archive and knowledge manager — across 16 work units in 6 phases. It adds a FastAPI backend, Next.js 14 frontend, and Docker production configuration.

**Stats**: 176 files changed, ~38,000 lines added, 1,122 tests (772 backend + 350 frontend), 100% coverage.

---

## How to Review

This is a large PR. Rather than reviewing every line, focus on these high-impact areas in order of priority.

### 1. Security (Start Here)

These files handle authentication, encryption, and access control. Security bugs here are the highest-risk issues.

| File | What to Check |
|---|---|
| `backend/app/auth/jwt.py` | Token creation/verification, HS256 signing, expiry handling |
| `backend/app/middleware/auth.py` | JWT extraction from cookies, user context propagation |
| `backend/app/middleware/csrf.py` | Double-submit cookie pattern, header validation |
| `backend/app/middleware/rate_limit.py` | Sliding window logic, per-path config, Redis key structure |
| `backend/app/crypto.py` | AES-256-GCM encrypt/decrypt, key derivation, nonce handling |
| `backend/app/services/google_auth.py` | OAuth token exchange, refresh flow, token storage |
| `backend/app/db/rls.py` | Row-Level Security — `SET LOCAL app.current_user_id` |
| `backend/app/api/auth.py` | Login/logout endpoints, cookie settings (httpOnly, SameSite, Secure) |

**Questions to ask yourself:**
- Are tokens validated server-side on every request?
- Can a user access another user's data?
- Are OAuth tokens encrypted at rest?
- Is CSRF protection on all state-changing endpoints?

### 2. Database Schema & Migrations

| File | What to Check |
|---|---|
| `backend/app/db/models.py` | ORM models — relationships, indexes, constraints |
| `backend/alembic/versions/001_initial_schema.py` | Migration — does it match the models? Are indexes correct? |
| `backend/app/db/engine.py` | Connection pooling, async session factory |

**Questions to ask yourself:**
- Are foreign keys correct?
- Are there indexes on frequently queried columns?
- Is the pgvector HNSW index configured reasonably?
- Do the RLS policies match the access patterns?

### 3. Core Business Logic

These files contain the main application logic.

| File | What to Check |
|---|---|
| `backend/app/services/threading.py` | JWZ 5-phase algorithm — ID table, references, root set, pruning, subject grouping |
| `backend/app/services/gmail.py` | Gmail API client — pagination, error handling, message fetching |
| `backend/app/services/sync.py` | Sync worker — incremental sync, progress tracking, error recovery |
| `backend/app/services/search.py` | FTS + semantic search — query building, combined scoring |
| `backend/app/services/knowledge.py` | Nugget extraction — 2-20 message guard, accept/reject workflow |
| `backend/app/services/llm.py` | Claude API client — prompt construction, response parsing |
| `backend/app/services/embeddings.py` | Embedding generation — batching, dimension handling |

**Questions to ask yourself:**
- Does the threading algorithm handle edge cases (missing references, orphan messages)?
- Does sync handle interruptions gracefully?
- Is the search scoring formula reasonable?
- Are LLM prompts well-structured?

### 4. API Endpoints

| File | Endpoints |
|---|---|
| `backend/app/api/groups.py` | CRUD for mailing list groups, OAuth token management |
| `backend/app/api/messages.py` | Message listing, thread fetching |
| `backend/app/api/search.py` | FTS and semantic search |
| `backend/app/api/knowledge.py` | Nugget CRUD, extraction trigger |
| `backend/app/api/reply.py` | Reply composition, RFC 5322 headers |
| `backend/app/api/dashboard.py` | Summary stats endpoint |
| `backend/app/api/consent.py` | LLM consent grant/revoke |
| `backend/app/api/router.py` | Router aggregation — all sub-routers wired here |

**Questions to ask yourself:**
- Are all endpoints behind auth middleware?
- Do mutations have CSRF protection?
- Are responses properly typed?
- Is error handling consistent?

### 5. Frontend

| Area | Files |
|---|---|
| Auth & state | `frontend/src/lib/auth.ts`, `frontend/src/stores/authStore.ts` |
| API client | `frontend/src/lib/api.ts` (CSRF token handling) |
| Hooks | `frontend/src/lib/hooks/use*.ts` (data fetching pattern) |
| Components | `frontend/src/components/` (thread, search, knowledge, dashboard) |
| Pages | `frontend/src/app/` (routing, layouts) |

**Questions to ask yourself:**
- Does the API client attach CSRF tokens to all mutations?
- Are loading/error states handled consistently?
- Is the component hierarchy reasonable?

### 6. Docker & Infrastructure

| File | What to Check |
|---|---|
| `backend/Dockerfile` | Multi-stage build, non-root user, health check |
| `frontend/Dockerfile` | 3-stage build, standalone output, telemetry disabled |
| `docker-compose.yml` | Service dependencies, health checks, volume persistence |
| `docker-compose.dev.yml` | Volume mounts for live reload, debug ports |

**Questions to ask yourself:**
- Are secrets passed via environment, not baked into images?
- Do health checks hit the right endpoints?
- Is the dependency ordering correct (db -> backend -> frontend)?

---

## Quick Feedback Checklist

Use this checklist to structure your feedback:

- [ ] **Security**: Any auth bypass, data leak, or injection risk?
- [ ] **Data model**: Schema looks correct for the domain?
- [ ] **Business logic**: Threading, search, and sync logic make sense?
- [ ] **API design**: Endpoints are RESTful, consistent, well-named?
- [ ] **Frontend UX**: Component structure and state management reasonable?
- [ ] **Error handling**: Failures degrade gracefully?
- [ ] **Docker**: Production config is secure and efficient?
- [ ] **Tests**: Coverage is meaningful (not just line-hitting)?
- [ ] **Missing features**: Anything expected but not implemented?
- [ ] **Naming/structure**: File organization follows conventions?

---

## Running Locally

```bash
# Backend tests (772 tests, 100% coverage)
cd backend
.venv/bin/python -m pytest --cov=app --cov-report=term-missing --cov-fail-under=100

# Frontend tests (350 tests, 100% coverage)
cd frontend
npx vitest run --coverage

# Docker (build only, no external services needed)
docker compose build
```

---

## Architecture at a Glance

```
Client (Next.js 14)
  |
  | HTTPS + CSRF token
  v
FastAPI Backend
  |-- JWT Auth Middleware
  |-- CSRF Middleware
  |-- Rate Limiter (Redis)
  |-- RLS (PostgreSQL SET LOCAL)
  |
  |-- /api/auth/*        (OAuth, login, logout)
  |-- /api/groups/*       (mailing list groups)
  |-- /api/messages/*     (messages, threads)
  |-- /api/search/*       (FTS + semantic)
  |-- /api/knowledge/*    (nuggets, extraction)
  |-- /api/reply/*        (compose, send)
  |-- /api/dashboard/*    (summary stats)
  |-- /api/consent/*      (LLM consent)
  |
  v
PostgreSQL 16 + pgvector     Redis 7
  |-- Users, Groups           |-- Rate limit counters
  |-- Messages, Threads       |-- Session cache
  |-- Nuggets, Embeddings
  |-- RLS policies
```

---

## Commit History

Each work unit is a separate commit for easy bisection:

| Commit | WU | Description |
|---|---|---|
| `91faa4d` | WU-1 | Project scaffolding |
| `e6cbe53` | WU-2 | Database schema + ORM + RLS |
| `c44f9d4` | WU-3 | AES-256-GCM encryption |
| `21ab15b` | WU-4 | Security middleware |
| `e900f35` | WU-5 | Google OAuth flow |
| `93eb09a` | WU-6 | LLM consent gate |
| `b979fd9` | WU-7 | Gmail API client |
| `967ce2a` | WU-8 | Group management + sync |
| `f9384a5` | WU-9 | JWZ threading engine |
| `a190412` | WU-10 | Thread viewer UI |
| `928a60d` | WU-11 | Reply flow |
| `e6efcbf` | WU-12 | Full-text search |
| `b6ce284` | WU-13 | Semantic search + embeddings |
| `3921f56` | WU-14 | Knowledge base |
| `f165033` | WU-15 | Dashboard |
| `f47131c` | WU-16 | Docker production build |

To review a specific WU: `git show <commit-hash>` or `git diff <commit-hash>^..<commit-hash>`

---

## Feedback Format

When providing feedback, it's helpful to reference:
- **File + line**: e.g., "In `backend/app/crypto.py:45`, the nonce should be..."
- **Severity**: blocking (must fix) vs. suggestion (nice to have)
- **Category**: security, logic, style, naming, missing feature
