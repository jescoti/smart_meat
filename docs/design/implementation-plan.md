# Smart Meat MVP — Implementation Plan

## Source Design: `docs/design/mvp-design.md` (Revised, post-review)

## Work Unit Decomposition

Each work unit is independently testable and committable. Dependencies are explicit — no work unit starts until its blockers are complete.

---

### WU-1: Project Scaffolding + Docker Compose

**Phase**: 1 (Foundation)
**Dependencies**: None
**Estimated files**: 15-20

**Scope:**
- `backend/` Python project structure with `pyproject.toml`, FastAPI app entry point
- `backend/app/main.py` — FastAPI app with CORS, lifespan events, health endpoint
- `backend/app/config.py` — pydantic-settings configuration (all env vars)
- `frontend/` Next.js 14 project with App Router, TailwindCSS, tsconfig
- `frontend/src/app/layout.tsx` — root layout with providers (TanStack Query, Zustand)
- `frontend/src/app/page.tsx` — landing page (redirect to login or dashboard)
- `docker-compose.yml` — PostgreSQL (with pgvector), Redis, backend, frontend
- `backend/Dockerfile` + `frontend/Dockerfile` — development Dockerfiles
- `.env.example` — all required environment variables documented
- Shared types stub: `frontend/src/types/index.ts`
- Common UI components: `EmptyState.tsx`, `LoadingState.tsx`, `ErrorBoundary.tsx`
- `frontend/src/stores/uiStore.ts` — UI preferences store

**DoD:**
1. `docker compose up` starts all 4 services (postgres, redis, backend, frontend)
2. `GET /api/health` returns `{"status": "ok"}` from FastAPI
3. Next.js app loads at `http://localhost:3000` with TailwindCSS working
4. PostgreSQL has pgvector extension enabled (`CREATE EXTENSION vector` succeeds)
5. Redis is reachable from backend
6. All tests pass with 100% coverage on new code
7. `.env.example` documents every required env var

---

### WU-2: Database Schema + Alembic Migrations

**Phase**: 1 (Foundation)
**Dependencies**: WU-1
**Estimated files**: 8-12

**Scope:**
- `backend/app/db/engine.py` — async SQLAlchemy engine + session factory
- `backend/app/db/models.py` — all ORM models (users, groups, messages, threads, thread_messages, message_embeddings, nuggets, audit_log)
- `backend/app/db/rls.py` — RLS policy setup, `SET LOCAL app.current_user_id` helper
- Alembic configuration + initial migration with full schema
- All indexes from design doc
- All RLS policies with USING clauses
- Audit log table

**DoD:**
1. `alembic upgrade head` creates all tables, indexes, and RLS policies
2. `alembic downgrade base` cleanly drops everything
3. RLS policies verified: query with user A context returns no user B data
4. All vector indexes (HNSW) create successfully
5. FTS indexes create successfully
6. All tests pass with 100% coverage on new code

---

### WU-3: Token Encryption Module

**Phase**: 1 (Foundation)
**Dependencies**: WU-1
**Estimated files**: 3-4

**Scope:**
- `backend/app/crypto.py` — AES-256-GCM encrypt/decrypt functions using `cryptography` library
- Key sourced from `ENCRYPTION_KEY` env var
- Encrypt/decrypt for OAuth access_token and refresh_token

**DoD:**
1. `encrypt(plaintext)` → ciphertext that `decrypt(ciphertext)` → original plaintext
2. Different ciphertexts for same plaintext (random nonce)
3. Decrypt with wrong key raises clear error
4. Empty/None input handled gracefully
5. All tests pass with 100% coverage

---

### WU-4: Security Middleware (Auth + CSRF + Rate Limiting)

**Phase**: 1 (Foundation)
**Dependencies**: WU-2, WU-3
**Estimated files**: 8-12

**Scope:**
- `backend/app/middleware/auth.py` — JWT validation from httpOnly cookie, user context injection, `SET LOCAL app.current_user_id`
- `backend/app/middleware/csrf.py` — double-submit cookie validation on mutating requests
- `backend/app/middleware/rate_limit.py` — Redis-backed per-user and per-IP rate limiting
- `frontend/src/lib/api.ts` — fetch wrapper with CSRF token injection (reads csrf_token cookie, sends X-CSRF-Token header)
- `backend/app/api/router.py` — API router aggregation
- JWT creation utilities (access token 15min TTL, refresh token 7day TTL)
- Rate limit configuration per endpoint class (from design doc table)

**DoD:**
1. Unauthenticated requests to protected endpoints return 401
2. Valid JWT cookie grants access; expired JWT returns 401
3. CSRF validation rejects POST/PUT/DELETE without matching X-CSRF-Token header
4. CSRF allows GET/HEAD/OPTIONS without token
5. Rate limiter returns 429 when limit exceeded, with Retry-After header
6. Rate limit state stored in Redis, resets correctly after window
7. All tests pass with 100% coverage

---

### WU-5: Google OAuth Flow

**Phase**: 1 (Foundation)
**Dependencies**: WU-4
**Estimated files**: 6-8

**Scope:**
- `backend/app/api/auth.py` — OAuth endpoints: `/api/auth/login`, `/api/auth/callback`, `/api/auth/refresh`, `/api/auth/logout`
- Google OAuth: authorization URL generation with state param (signed, CSRF)
- Code exchange for tokens, encrypt and store
- JWT issuance as httpOnly cookies
- Token refresh with rotation (old refresh token invalidated)
- Refresh failure → clear cookies, redirect to login
- Audit log entries for login, refresh, refresh_fail
- `frontend/src/app/login/page.tsx` — login page with "Sign in with Google" button
- `frontend/src/lib/auth.ts` — auth utilities (no raw tokens)
- `frontend/src/stores/authStore.ts` — user metadata only (id, name, email, avatar, expiry)

**DoD:**
1. "Sign in with Google" redirects to Google consent screen with correct scopes
2. Callback exchanges code, stores encrypted tokens, sets JWT cookies
3. `/api/auth/refresh` rotates refresh token and issues new access token
4. `/api/auth/logout` clears cookies and revokes stored tokens
5. `authStore` contains zero raw tokens (verified by test)
6. Audit log records login and refresh events
7. All tests pass with 100% coverage

---

### WU-6: LLM Consent Gate

**Phase**: 1 (Foundation)
**Dependencies**: WU-5
**Estimated files**: 4-5

**Scope:**
- `frontend/src/app/consent/page.tsx` — consent screen explaining email content will be sent to Claude API
- Backend endpoint: `POST /api/auth/consent` — records `llm_consent_given_at`
- Backend endpoint: `DELETE /api/auth/consent` — revokes consent
- Consent check middleware/utility for LLM endpoints
- Redirect to consent page on first login if no consent recorded

**DoD:**
1. New user without consent sees consent page after first login
2. Granting consent records timestamp and redirects to dashboard
3. Revoking consent clears timestamp and disables LLM features
4. LLM-dependent endpoints return 403 without consent
5. Non-LLM endpoints (threading, search, viewing) work without consent
6. All tests pass with 100% coverage

---

### WU-7: Gmail API Client + Sync Service

**Phase**: 2 (Gmail Sync)
**Dependencies**: WU-5
**Estimated files**: 6-8

**Scope:**
- `backend/app/services/gmail.py` — Gmail API client
  - List messages by `listid:` filter
  - Fetch full message (headers + body) in batches of 100
  - Incremental sync via `historyId`
  - Exponential backoff on rate limit (429) responses
  - Token refresh on 401 responses
- Message parsing: extract Message-ID, In-Reply-To, References, subject, sender, recipients (strip BCC), date, body_text, body_html
- Strip auth headers (DKIM, ARC, Received) from raw_headers before storage

**DoD:**
1. Can list all messages for a given Google Group from a Gmail account
2. Can fetch full message details in batches
3. Incremental sync using historyId fetches only new messages
4. Exponential backoff respects Gmail API rate limits
5. Token refresh on 401 works transparently
6. BCC stripped from recipients
7. Auth headers stripped from raw_headers
8. All tests pass with 100% coverage (Gmail API mocked)

---

### WU-8: Group Management + Sync Workers

**Phase**: 2 (Gmail Sync)
**Dependencies**: WU-7
**Estimated files**: 8-10

**Scope:**
- `backend/app/api/groups.py` — endpoints: add group, list groups, trigger sync, get sync status
- `backend/app/workers/celery_app.py` — Celery configuration
- `backend/app/workers/tasks.py` — `sync_group` task: fetch messages, store, update progress
- Sync progress tracking: update `sync_progress_current`/`sync_progress_total` as messages are fetched
- Error handling: set `sync_status='error'` + `sync_error_message` on failure
- `frontend/src/app/groups/page.tsx` — group list UI
- `frontend/src/components/sync/SyncProgress.tsx` — progress bar with status messages
- `frontend/src/components/sync/SyncError.tsx` — error display with retry button
- `frontend/src/lib/hooks/useSync.ts` — poll sync status every 5 seconds

**DoD:**
1. User can add a Google Group and trigger initial sync
2. Sync progress visible in real-time (polling, progress bar)
3. Sync errors displayed with retry action
4. Duplicate messages deduplicated by gmail_id
5. Sync stores gmail_history_id for future incremental sync
6. Celery worker processes sync tasks in background
7. Sync trigger events recorded in audit_log with action='sync_trigger' and group_id in metadata
8. All tests pass with 100% coverage

---

### WU-9: JWZ Threading Engine

**Phase**: 2 (Gmail Sync)
**Dependencies**: WU-8
**Estimated files**: 4-6

**Scope:**
- `backend/app/services/threading.py` — full JWZ algorithm implementation
  - Build ID table from Message-ID headers
  - Build references graph from References + In-Reply-To
  - Find root set
  - Prune empty containers
  - Subject-based grouping fallback (72-hour window)
  - Ghost message marking (`is_ghost = TRUE` in thread_messages)
- Thread counter updates: compute and SET message_count, participant_count after reconstruction
- Integration with Celery: `thread_group` task runs after sync completes
- Processing status transitions: `pending → threaded`

**DoD:**
1. Correctly threads messages with proper References/In-Reply-To headers
2. Subject-based fallback groups messages within 72-hour window
3. Ghost nodes created for missing parent messages with `is_ghost = TRUE`
4. Thread message_count and participant_count accurately computed
5. Processing status updated to 'threaded' after successful threading
6. Handles edge cases: single-message threads, deep threads (>50 levels), circular references
7. All tests pass with 100% coverage

---

### WU-10: Thread Viewer UI

**Phase**: 3 (Thread Viewer)
**Dependencies**: WU-9
**Estimated files**: 10-14

**Scope:**
- `backend/app/api/messages.py` — endpoints: list threads (paginated, sorted by last_message_at), get thread detail (full hierarchy)
- `frontend/src/app/groups/[groupId]/page.tsx` — thread list for group
- `frontend/src/app/groups/[groupId]/threads/[threadId]/page.tsx` — thread viewer
- `frontend/src/components/thread/ThreadViewer.tsx` — hierarchical display, collapse/expand, read/unread
- `frontend/src/components/thread/MessageCard.tsx` — individual message: sender, date, body, reply button
- `frontend/src/components/thread/MissingMessageGhost.tsx` — dashed-border placeholder for ghost nodes
- `frontend/src/lib/hooks/useThreads.ts` — TanStack Query hooks for thread list + detail
- Empty states for: no threads in group, thread loading

**DoD:**
1. Thread list shows threads sorted by last activity, paginated
2. Thread detail renders full message hierarchy with correct nesting
3. Ghost messages render as MissingMessageGhost with dashed border and explanation
4. Collapse/expand works for thread branches
5. Read/unread visual indicators work
6. Empty states shown when no threads exist
7. All tests pass with 100% coverage

---

### WU-11: Reply Flow

**Phase**: 3 (Thread Viewer)
**Dependencies**: WU-10
**Estimated files**: 6-8

**Scope:**
- `backend/app/api/reply.py` — compose + send reply endpoint with rate limiting
- Construct proper headers: In-Reply-To, References chain, Message-ID (RFC 5322)
- Gmail API send integration
- `frontend/src/components/thread/ReplyContext.tsx` — shows parent message quote (first 3 lines, sender, date)
- `frontend/src/components/thread/ReplyComposer.tsx` — TipTap editor with ReplyContext above
- Send confirmation dialog: "Send reply to [group] in response to [sender]'s message?"
- Audit log: 'reply_send' event
- Store sent message locally, link to thread

**DoD:**
1. Clicking "Reply" on a message shows ReplyContext with parent quote
2. ReplyComposer allows composing rich text reply
3. Confirmation step before send shows recipient and parent context
4. Sent reply has correct In-Reply-To and References headers
5. Rate limiting enforced (10 sends/min per user)
6. Sent message stored locally and appears in thread
7. Audit log records send event
8. All tests pass with 100% coverage

---

### WU-12: Full-Text Search

**Phase**: 4 (Search)
**Dependencies**: WU-10
**Estimated files**: 6-8

**Scope:**
- `backend/app/services/search.py` — FTS service using `websearch_to_tsquery` (parameterized)
- `backend/app/api/search.py` — search endpoint with filters (date range, sender, group, has_attachments, tags)
- FTS on messages (subject + body_text) and nuggets (title + content)
- `ts_rank_cd` scoring with sigmoid normalization
- Pagination and result count
- `frontend/src/app/search/page.tsx` — search interface
- `frontend/src/components/search/SearchBar.tsx` — search input
- `frontend/src/components/search/SearchResults.tsx` — results with highlighting
- `frontend/src/components/search/SearchFilters.tsx` — date, sender, tags filters
- `frontend/src/lib/hooks/useSearch.ts` — TanStack Query hooks

**DoD:**
1. Search returns relevant results for keyword queries
2. Filters (date range, sender, group, tags) narrow results correctly
3. Results paginated with total count
4. Search input is sanitized (parameterized queries, no SQL injection)
5. Empty search results show EmptyState
6. All tests pass with 100% coverage

---

### WU-13: Semantic Search + Embedding Pipeline

**Phase**: 4 (Search)
**Dependencies**: WU-12
**Estimated files**: 5-7

**Scope:**
- `backend/app/services/embeddings.py` — sentence-transformers embedding generation (run in Celery workers, not in async handlers)
- `backend/app/workers/tasks.py` — `generate_embeddings` task for new messages
- pgvector HNSW similarity search
- Combined scoring: sigmoid-normalized FTS + cosine similarity (0.7/0.3 weights)
- Search within specific thread (filter by thread_id)

**DoD:**
1. Embeddings generated for messages via Celery task
2. Semantic search returns conceptually related results even without keyword match
3. A test corpus query using a synonym not present in message text returns the target message via semantic search but not via FTS-only search
4. Search within thread works
5. Embedding generation does not block API requests (runs in Celery worker)
6. All tests pass with 100% coverage

---

### WU-14: Knowledge Base — LLM Extraction + Manual Creation

**Phase**: 5 (Knowledge Base)
**Dependencies**: WU-13, WU-6
**Estimated files**: 8-12

**Scope:**
- `backend/app/services/llm.py` — Claude API client: thread summarization, nugget extraction
- `backend/app/services/knowledge.py` — nugget CRUD, suggestion accept/reject
- `backend/app/api/knowledge.py` — endpoints: list nuggets, get nugget, create manual nugget, accept/reject suggestion, list pending suggestions
- `backend/app/workers/tasks.py` — `process_thread_llm` task (consent-gated, thread-size guards)
- `frontend/src/app/knowledge/page.tsx` — knowledge base browser
- `frontend/src/app/knowledge/suggestions/page.tsx` — pending suggestions (accept/reject)
- `frontend/src/app/knowledge/[nuggetId]/page.tsx` — nugget detail with source thread context
- `frontend/src/components/knowledge/NuggetCard.tsx` — nugget display
- `frontend/src/components/knowledge/NuggetExtractor.tsx` — manual extraction from message
- `frontend/src/components/knowledge/NuggetSuggestionCard.tsx` — accept/reject UI
- `frontend/src/lib/hooks/useKnowledge.ts` — TanStack Query hooks

**DoD:**
1. Claude API summarizes threads (consent-gated)
2. Claude API extracts nuggets from informational posts (opt-in per group, 2-20 message threads)
3. Suggested nuggets appear in /knowledge/suggestions with accept/reject
4. Manual nugget creation from any message works
5. Knowledge base browser shows all accepted + manual nuggets
6. Nugget detail shows source thread context
7. Flat tagging works
8. LLM endpoints return 403 without user consent
9. Claude API key never appears in logs or error responses
10. All tests pass with 100% coverage

---

### WU-15: Dashboard

**Phase**: 5 (Knowledge Base)
**Dependencies**: WU-14
**Estimated files**: 4-6

**Scope:**
- `frontend/src/app/dashboard/page.tsx` — dashboard overview
- `frontend/src/components/layout/Sidebar.tsx` — navigation sidebar
- `frontend/src/components/layout/Header.tsx` — top bar with search
- Dashboard widgets: unread count, recent threads, recent nuggets, group stats
- Backend endpoints: `GET /api/dashboard/summary` (unread counts, group stats), `GET /api/dashboard/recent-threads` (10 most recent by last_message_at), `GET /api/dashboard/recent-nuggets` (10 most recent by created_at)

**DoD:**
1. Dashboard shows unread message count per group
2. Recent threads section shows 10 latest threads sorted by last_message_at DESC
3. Recent nuggets section shows 10 latest saved/accepted nuggets sorted by created_at DESC
4. Group statistics (message count, thread count) displayed
5. Sidebar navigation works across all routes
6. All tests pass with 100% coverage

---

### WU-16: Docker Production Build + Environment Config

**Phase**: 6 (Deployment)
**Dependencies**: WU-15
**Estimated files**: 6-8

**Scope:**
- `backend/Dockerfile` — multi-stage production build
- `frontend/Dockerfile` — multi-stage production build with Next.js standalone
- `docker-compose.yml` — update for production mode
- `docker-compose.override.yml` — development overrides
- `.env.example` — final comprehensive env var documentation
- Responsive design pass across all pages
- Final production readiness checks

**DoD:**
1. `docker compose up` in production mode serves the full application
2. Multi-stage builds minimize image sizes
3. All environment variables documented in .env.example
4. Application works on mobile viewport widths (responsive)
5. No development dependencies in production images
6. All tests pass with 100% coverage

---

## Dependency Graph

```
WU-1 (Scaffolding)
├── WU-2 (Schema) ──┐
├── WU-3 (Crypto) ──┼── WU-4 (Security MW) ── WU-5 (OAuth) ── WU-6 (Consent)
│                    │                                │               │
│                    │                          WU-7 (Gmail) ── WU-8 (Sync) ── WU-9 (Threading)
│                    │                                                              │
│                    │                                                    WU-10 (Thread UI) ──┬── WU-11 (Reply)
│                    │                                                              │         │
│                    │                                                    WU-12 (FTS Search) ─┴── WU-13 (Semantic)
│                    │                                                                              │
│                    │                                                              WU-14 (Knowledge) ── WU-15 (Dashboard)
│                    │                                                                                        │
│                    │                                                                              WU-16 (Production)
```

## Parallelization Opportunities

- **WU-2 and WU-3** can run in parallel (both depend only on WU-1)
- **WU-11 and WU-12** can run in parallel (both depend on WU-10)
- **WU-15** can start as soon as WU-14 is complete

## Human Checkpoints

| After | Review |
|---|---|
| WU-5 (OAuth) | Review DB schema, auth flow, security middleware |
| WU-9 (Threading) | Verify threading correctness with real Gmail data |
| WU-11 (Reply) | Review thread viewer UX and reply flow |
| WU-13 (Semantic) | Test search quality with real data |
| WU-15 (Dashboard) | Full MVP review |
| WU-16 (Production) | Deployment readiness review |

## Risk Mitigation

| Risk | Mitigation |
|---|---|
| JWZ algorithm complexity | WU-9 has generous scope; human checkpoint before UI work |
| Gmail API rate limits | Exponential backoff built into WU-7; sync progress UX in WU-8 |
| Claude API costs | Opt-in per group, thread size guards, consent gate |
| First-time sync duration | SyncProgress component, incremental thread display |
| Token security | Encryption module (WU-3) built early, tested independently |
