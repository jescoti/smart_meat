# Smart Meat MVP Design Document

## Status: REVISED — Addressing Design Review Feedback (Round 1)

## Overview

Smart Meat is a multi-tenant web application that ingests Google Groups messages via the Gmail API, reconstructs proper email threading using the JWZ algorithm, provides a clean thread viewer with full-text and semantic search, extracts knowledge nuggets using Anthropic Claude, and enables replies with proper thread placement.

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Data access | Gmail API only | Reliable, preserves headers, incremental sync, no extra auth |
| Authentication | Google OAuth 2.0 only | Users already need Google auth for Gmail access |
| LLM provider | Anthropic Claude API | Strong reasoning for summarization and extraction |
| Search | PostgreSQL FTS + pgvector | No extra infrastructure, covers full-text + semantic |
| Replies | Gmail API send | Proper threading headers, stays in Google ecosystem |
| Deployment | Docker Compose | Simple local dev, portable to any host |
| MVP scope | Full vertical slice | Ingest + threading + viewer + search + knowledge nuggets |
| Multi-tenancy model | Per-user message copy | Simplest isolation for MVP; shared-message model is a post-MVP migration. Each user's group subscription stores its own copy of messages. This is intentionally wasteful of storage to guarantee complete data isolation via RLS without complex join-based policies. Accepted tradeoff. |
| Session tokens | httpOnly cookies | JWTs stored in httpOnly/Secure/SameSite=Strict cookies, never in localStorage or Zustand |
| Token encryption | AES-256-GCM | OAuth tokens encrypted at app layer using AES-256-GCM with key from `ENCRYPTION_KEY` env var |
| LLM auto-extraction | Opt-in per group | Auto nugget extraction is off by default; users enable per group to control Claude API costs |
| Claude model | Config-driven | Model ID stored in `CLAUDE_MODEL` env var (default: current Sonnet), not hardcoded |

## Architecture

### System Diagram

```
                    +-----------------+
                    |   Next.js 14    |
                    |   (App Router)  |
                    |   Port 3000     |
                    +--------+--------+
                             |
                    +--------v--------+
                    |    FastAPI       |
                    |    (async)       |
                    |    Port 8000     |
                    +--+-----+-----+--+
                       |     |     |
              +--------+  +--+--+  +--------+
              |           |     |           |
        +-----v----+ +---v---+ +----v------+
        |PostgreSQL | | Redis | |  Claude   |
        |+ pgvector | |       | |  API      |
        |  Port 5432| | 6379  | |           |
        +----------+ +-------+ +-----------+
```

### Backend (FastAPI + Python)

**Directory structure:**
```
backend/
  app/
    main.py                    # FastAPI app, CORS, lifespan
    config.py                  # Settings via pydantic-settings
    crypto.py                  # AES-256-GCM encrypt/decrypt for tokens
    middleware/
      auth.py                  # JWT cookie validation middleware
      csrf.py                  # CSRF double-submit cookie middleware
      rate_limit.py            # Per-endpoint rate limiting (Redis-backed)
    db/
      engine.py                # Async SQLAlchemy engine
      models.py                # ORM models
      rls.py                   # RLS policy setup + session context
      migrations/              # Alembic migrations
    api/
      router.py                # API router aggregation
      auth.py                  # Google OAuth endpoints
      groups.py                # Group management endpoints
      messages.py              # Message/thread endpoints
      search.py                # Search endpoints
      knowledge.py             # Knowledge nugget endpoints
      reply.py                 # Reply composition + send
    services/
      gmail.py                 # Gmail API client (sync, fetch, rate-limited)
      threading.py             # JWZ algorithm implementation
      llm.py                   # Claude API client (summarize, extract)
      embeddings.py            # Embedding generation for pgvector
      search.py                # Full-text + semantic search service
      knowledge.py             # Nugget extraction + management
    workers/
      celery_app.py            # Celery configuration
      tasks.py                 # Background tasks (sync, process, embed)
  tests/
    conftest.py
    test_threading.py
    test_gmail.py
    test_search.py
    test_knowledge.py
    test_crypto.py
    test_middleware/
      test_auth.py
      test_csrf.py
      test_rate_limit.py
    test_api/
      test_auth.py
      test_messages.py
      test_search.py
      test_knowledge.py
  pyproject.toml
  Dockerfile
```

**Key dependencies:**
- fastapi, uvicorn, pydantic-settings
- sqlalchemy[asyncio], asyncpg, alembic
- celery, redis
- anthropic (Claude SDK)
- google-api-python-client, google-auth-oauthlib
- pgvector, sentence-transformers (for local embeddings)
- cryptography (for AES-256-GCM token encryption)

### Frontend (Next.js 14 + TypeScript)

**Directory structure:**
```
frontend/
  src/
    app/
      layout.tsx               # Root layout, providers
      page.tsx                 # Landing / redirect to dashboard
      login/page.tsx           # Google OAuth login
      consent/page.tsx         # LLM data processing consent screen
      dashboard/page.tsx       # Dashboard overview
      groups/
        page.tsx               # Group list
        [groupId]/
          page.tsx             # Thread list for group
          threads/
            [threadId]/page.tsx # Thread viewer
      search/page.tsx          # Search interface
      knowledge/
        page.tsx               # Knowledge base browser
        suggestions/page.tsx   # Pending nugget suggestions (accept/reject)
        [nuggetId]/page.tsx    # Nugget detail
    components/
      thread/
        ThreadViewer.tsx       # Hierarchical thread display
        MessageCard.tsx        # Individual message in thread
        MissingMessageGhost.tsx # Placeholder for missing parent messages
        ReplyComposer.tsx      # Inline reply with context preview
        ReplyContext.tsx        # Shows which message you're replying to
      search/
        SearchBar.tsx          # Search input with suggestions
        SearchResults.tsx      # Results with facets
        SearchFilters.tsx      # Date, sender, tags filters
      knowledge/
        NuggetCard.tsx         # Knowledge nugget display
        NuggetExtractor.tsx    # Extract nugget from message selection
        NuggetSuggestionCard.tsx # Accept/reject LLM-suggested nugget
      sync/
        SyncProgress.tsx       # Sync progress bar with status messages
        SyncError.tsx          # Sync error display with retry action
      common/
        EmptyState.tsx         # Reusable empty state component
        LoadingState.tsx       # Loading skeleton component
        ErrorBoundary.tsx      # Error boundary with fallback UI
      layout/
        Sidebar.tsx            # Navigation sidebar
        Header.tsx             # Top bar with search
    lib/
      api.ts                   # API client (fetch wrapper, CSRF token)
      auth.ts                  # Auth utilities (no raw tokens)
      hooks/
        useThreads.ts          # TanStack Query hooks
        useSearch.ts
        useKnowledge.ts
        useSync.ts             # Sync progress polling
    stores/
      authStore.ts             # Zustand: user metadata only (id, name, email, expiry) — NO raw tokens
      uiStore.ts               # UI preferences
    types/
      index.ts                 # Shared TypeScript types
  tailwind.config.ts
  next.config.ts
  tsconfig.json
  Dockerfile
```

**Key dependencies:**
- next, react, react-dom
- tailwindcss, @tailwindcss/typography
- zustand
- @tanstack/react-query
- tiptap (for rich text replies)

**IMPORTANT: `authStore.ts` must NEVER contain raw JWT tokens, access tokens, or refresh tokens. It stores only non-sensitive session metadata: user ID, display name, email, avatar URL, and token expiry timestamp. All authentication is handled via httpOnly cookies.**

### Data Model (PostgreSQL)

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_id TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    avatar_url TEXT,
    access_token TEXT,          -- AES-256-GCM encrypted, key from ENCRYPTION_KEY env var
    refresh_token TEXT,         -- AES-256-GCM encrypted, key from ENCRYPTION_KEY env var
    token_expires_at TIMESTAMPTZ,
    llm_consent_given_at TIMESTAMPTZ,  -- NULL = no consent, timestamp = consented
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Groups table
CREATE TABLE groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    google_group_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    description TEXT,
    last_sync_at TIMESTAMPTZ,
    gmail_history_id TEXT,         -- Gmail historyId for incremental sync (more reliable than timestamp)
    sync_status TEXT DEFAULT 'pending',  -- pending, syncing, completed, error
    sync_error_message TEXT,       -- Human-readable error when sync_status = 'error'
    sync_progress_total INTEGER,   -- Total messages to sync (for progress display)
    sync_progress_current INTEGER, -- Messages synced so far
    message_count INTEGER DEFAULT 0,
    auto_extract_nuggets BOOLEAN DEFAULT FALSE,  -- Opt-in per group for LLM nugget extraction
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, google_group_id)
);

CREATE INDEX idx_groups_user_id ON groups(user_id);

-- Messages table
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
    gmail_id TEXT NOT NULL,
    message_id TEXT NOT NULL,        -- RFC 5322 Message-ID header
    in_reply_to TEXT,                -- In-Reply-To header
    references_header TEXT[],        -- References header (array)
    subject TEXT NOT NULL,
    sender_email TEXT NOT NULL,
    sender_name TEXT,
    recipients JSONB,                -- {to: [], cc: []} — BCC stripped, never stored or displayed
    date TIMESTAMPTZ NOT NULL,
    body_text TEXT,
    body_html TEXT,
    has_attachments BOOLEAN DEFAULT FALSE,
    attachments JSONB,               -- [{name, mime_type, size}]
    labels TEXT[],
    is_read BOOLEAN DEFAULT FALSE,
    raw_headers JSONB,               -- Stripped of auth headers (DKIM, ARC, Received) before storage
    processing_status TEXT DEFAULT 'pending',  -- pending, threaded, analyzed, indexed, error
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(group_id, gmail_id)
);

CREATE INDEX idx_messages_group_id ON messages(group_id);
CREATE INDEX idx_messages_date ON messages(date);
CREATE INDEX idx_messages_message_id ON messages(message_id);

-- Full-text search index
CREATE INDEX idx_messages_fts ON messages
    USING GIN (to_tsvector('english', coalesce(subject, '') || ' ' || coalesce(body_text, '')));

-- Threads table (reconstructed by JWZ)
-- message_count and participant_count are updated by the threading service
-- via explicit UPDATE after thread reconstruction, not triggers (simpler, testable)
CREATE TABLE threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
    root_message_id UUID REFERENCES messages(id),
    subject TEXT NOT NULL,
    participant_count INTEGER DEFAULT 0,  -- Updated by threading service after reconstruction
    message_count INTEGER DEFAULT 0,      -- Updated by threading service after reconstruction
    first_message_at TIMESTAMPTZ,
    last_message_at TIMESTAMPTZ,
    summary TEXT,                     -- LLM-generated
    tags TEXT[],                      -- auto + manual tags
    is_starred BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_threads_group_id ON threads(group_id);
CREATE INDEX idx_threads_last_message_at ON threads(group_id, last_message_at DESC);

-- Thread-message relationship (preserves hierarchy)
CREATE TABLE thread_messages (
    thread_id UUID REFERENCES threads(id) ON DELETE CASCADE,
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    parent_message_id UUID REFERENCES messages(id),  -- NULL for root
    is_ghost BOOLEAN DEFAULT FALSE,  -- TRUE for JWZ placeholder nodes (missing parent messages)
    depth INTEGER DEFAULT 0,
    position INTEGER DEFAULT 0,       -- ordering within thread
    PRIMARY KEY (thread_id, message_id)
);

CREATE INDEX idx_thread_messages_message_id ON thread_messages(message_id);

-- Embeddings for semantic search (HNSW index — works well at any scale, no minimum row count)
CREATE TABLE message_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE UNIQUE,
    embedding vector(384),            -- sentence-transformers/all-MiniLM-L6-v2 dimension
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_message_embeddings_hnsw
    ON message_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Knowledge nuggets
CREATE TABLE nuggets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    source_message_id UUID REFERENCES messages(id),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    context TEXT,                      -- thread context / summary
    extraction_type TEXT NOT NULL,     -- 'manual' | 'llm_suggested'
    suggestion_status TEXT,            -- 'pending' | 'accepted' | 'rejected' (NULL for manual)
    confidence_score FLOAT,           -- LLM confidence (0-1), only for llm_suggested
    tags TEXT[],
    is_archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_nuggets_user_id ON nuggets(user_id);
CREATE INDEX idx_nuggets_suggestion_status ON nuggets(user_id, suggestion_status)
    WHERE suggestion_status = 'pending';

-- Nugget FTS index (keyword search is sufficient for MVP — semantic search deferred)
CREATE INDEX idx_nuggets_fts ON nuggets
    USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')));

-- Row-level security with explicit policies
-- All queries run with SET LOCAL app.current_user_id = '<uuid>' at the start of each request
ALTER TABLE groups ENABLE ROW LEVEL SECURITY;
CREATE POLICY groups_isolation ON groups
    USING (user_id = current_setting('app.current_user_id')::uuid);

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY messages_isolation ON messages
    USING (group_id IN (SELECT id FROM groups WHERE user_id = current_setting('app.current_user_id')::uuid));

ALTER TABLE threads ENABLE ROW LEVEL SECURITY;
CREATE POLICY threads_isolation ON threads
    USING (group_id IN (SELECT id FROM groups WHERE user_id = current_setting('app.current_user_id')::uuid));

ALTER TABLE thread_messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY thread_messages_isolation ON thread_messages
    USING (thread_id IN (
        SELECT id FROM threads WHERE group_id IN (
            SELECT id FROM groups WHERE user_id = current_setting('app.current_user_id')::uuid
        )
    ));

ALTER TABLE message_embeddings ENABLE ROW LEVEL SECURITY;
CREATE POLICY message_embeddings_isolation ON message_embeddings
    USING (message_id IN (
        SELECT id FROM messages WHERE group_id IN (
            SELECT id FROM groups WHERE user_id = current_setting('app.current_user_id')::uuid
        )
    ));

ALTER TABLE nuggets ENABLE ROW LEVEL SECURITY;
CREATE POLICY nuggets_isolation ON nuggets
    USING (user_id = current_setting('app.current_user_id')::uuid);

-- Audit log for security events
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    action TEXT NOT NULL,          -- 'login', 'token_refresh', 'token_refresh_fail', 'sync_trigger', 'reply_send', 'consent_granted'
    metadata JSONB,
    ip_address TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);
```

**Removed from MVP schema:**
- `nugget_embeddings` table — keyword FTS on nuggets is sufficient for MVP; semantic search on nuggets deferred
- `collections` table and `collection_id` on nuggets — flat tags are sufficient for MVP; hierarchical collections deferred
- BCC field from `recipients` JSONB — BCC must never be stored or displayed to prevent privacy violations
- Auth-related headers (DKIM, ARC, Received chains) from `raw_headers` — stripped before storage

### Security Architecture

#### Authentication Flow

```
User → Click "Sign in with Google"
  → Google OAuth consent screen (scopes: email, profile, gmail.readonly, gmail.send)
  → Redirect with auth code + state param (signed, CSRF protection)
  → Backend validates state param
  → Backend exchanges code for tokens
  → Encrypt tokens with AES-256-GCM (key from ENCRYPTION_KEY env var)
  → Create/update user record (store encrypted tokens)
  → Issue JWT access token (15 min TTL) + refresh token (7 day TTL, rotate on use)
  → Set httpOnly, Secure, SameSite=Strict cookies
  → Redirect to dashboard
  → Audit log: 'login' event
```

#### Token Refresh

```
Access token expired (401 response)
  → Frontend automatically retries with refresh cookie
  → Backend validates refresh token
  → If valid: issue new access + refresh tokens, set new cookies, audit log
  → If invalid: clear cookies, redirect to login, revoke stored Google tokens
```

#### CSRF Protection

Double-submit cookie pattern:
- Backend sets a `csrf_token` cookie (NOT httpOnly, so JS can read it)
- Frontend reads `csrf_token` cookie and sends it as `X-CSRF-Token` header on all mutating requests
- Backend validates header matches cookie on all POST/PUT/DELETE/PATCH

#### Rate Limiting (Redis-backed)

| Endpoint class | Limit | Scope |
|---|---|---|
| Auth (login, refresh) | 5 req/min | Per IP |
| Sync triggers | 2 req/min | Per user |
| Reply sends | 10 req/min | Per user |
| LLM endpoints | 30 req/min, 500 req/hour | Per user |
| Search | 60 req/min | Per user |
| General API | 120 req/min | Per user |

#### Error Responses

All API error responses return generic messages with an error code. Stack traces, internal paths, and debug information are NEVER returned to clients. Format:

```json
{
  "error": "sync_failed",
  "message": "Unable to sync group. Please try again later.",
  "request_id": "uuid-for-support"
}
```

#### LLM Data Consent

Before any email content is sent to the Claude API, the user must explicitly consent:
- First-time consent screen at `/consent` after login
- Records `llm_consent_given_at` timestamp on user record
- Without consent: threading, search, and viewing work normally; LLM features (summarization, nugget extraction) are disabled
- User can revoke consent in settings, which disables LLM processing going forward

#### Parameterized Queries

ALL database queries use parameterized statements via SQLAlchemy ORM. No raw SQL string interpolation. This is especially critical for the FTS search path where user input feeds `ts_query`.

### Gmail Sync Flow

```
User → Add Google Group → Consent check (LLM features only)
  → Backend queries Gmail API: messages matching listid:<group-email>
  → Respect Gmail API quotas (exponential backoff, 250 quota units/sec)
  → Update sync_progress_total and sync_progress_current as messages are fetched
  → Frontend polls /api/groups/{id}/sync-status every 5 seconds, displays SyncProgress component
  → Fetch message headers + bodies in batches (100 per request)
  → Store in messages table (dedup by gmail_id)
  → Save gmail_history_id for future incremental sync
  → Queue threading job (Celery)
  → JWZ algorithm reconstructs threads
  → If user has LLM consent AND group has auto_extract_nuggets enabled:
    → Queue LLM processing (summarize threads with 2-20 messages, extract nuggets)
  → Queue embedding generation
  → Update sync status to 'completed'
  → On any error: set sync_status='error', sync_error_message, audit log
```

**First-time sync UX:**
1. User adds a group → sees `SyncProgress` component with progress bar (X of Y messages)
2. Messages appear in thread list as they're processed (don't wait for full sync)
3. Threading runs incrementally — early threads visible while sync continues
4. If sync fails: `SyncError` component shows error message + "Retry" button
5. On quota exceeded: "Gmail rate limit reached. Sync will resume automatically in 1 hour."

### JWZ Threading Algorithm

The threading engine implements Jamie Zawinski's algorithm:

1. **Build ID table**: Map each Message-ID to its message
2. **Build references graph**: Use References + In-Reply-To headers to link messages
3. **Find root set**: Messages with no parent
4. **Prune empty containers**: Remove placeholder nodes for missing messages
5. **Group by subject**: Merge threads with matching subjects (fallback)
6. **Sort**: Order threads by date, depth-first within threads

Fallback strategies for broken threading:
- Subject matching with time-window constraint (72 hours)
- Sender pattern matching (same sender, similar subject)
- Content quoting detection ("> " prefix analysis)

**Ghost messages (missing parents):**
When JWZ produces a placeholder for a missing parent message, the `thread_messages` row has `is_ghost = TRUE`. The frontend renders `MissingMessageGhost` component: a dashed-border card with "[Message not available — this reply references a message not in your archive]" and a collapse toggle to hide/show child messages below it.

### LLM Processing Pipeline

```
Thread reconstruction complete → Check user LLM consent
  → If no consent: skip LLM processing, mark thread as 'threaded' (not 'analyzed')
  → If consent AND group.auto_extract_nuggets = TRUE:
    → Threads with 2-20 messages: summarize + extract nuggets
    → Threads with >20 messages: summarize only (nugget extraction too expensive)
    → Threads with 1 message: skip summarization, extract nuggets only if informational
  → Store nuggets as extraction_type='llm_suggested', suggestion_status='pending'
  → User reviews in /knowledge/suggestions page (accept/reject)
  → Generate embeddings for semantic search
```

**Claude API usage:**
- Thread summarization: current Sonnet model (from `CLAUDE_MODEL` env var)
- Nugget extraction: current Sonnet model (from `CLAUDE_MODEL` env var)
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2` (local, free)
- Claude API key: stored in `ANTHROPIC_API_KEY` env var, never logged, never in error responses

### Search Architecture

**Full-text search (PostgreSQL FTS):**
- GIN index on `subject || body_text`
- `plainto_tsquery` or `websearch_to_tsquery` for safe user input (parameterized, no raw SQL)
- `ts_rank_cd` for relevance scoring
- Filter by: date range, sender, group, has_attachments, tags

**Semantic search (pgvector):**
- Query embedding generated at search time via local sentence-transformers
- Cosine similarity against message_embeddings
- Combined scoring with normalization:
  - Normalize FTS score: `fts_normalized = 1 / (1 + exp(-ts_rank_cd))` (sigmoid)
  - Cosine similarity already bounded [0, 1]
  - Combined: `0.7 * fts_normalized + 0.3 * cosine_similarity`

### Reply Flow

**Reply-to-specific-message UX:**
1. User clicks "Reply" on a specific `MessageCard` within the thread
2. `ReplyContext` component appears above the composer showing: quoted excerpt (first 3 lines) of the parent message, sender name, and date — confirming which message the reply targets
3. `ReplyComposer` opens with TipTap editor for the reply body
4. User composes reply and clicks "Send"
5. **Confirmation step**: "Send reply to [group-email] in response to [sender]'s message from [date]?" — user must confirm before send
6. Backend constructs proper headers: `In-Reply-To: <parent-message-id>`, `References: <full-chain>`
7. Send via Gmail API with rate limiting (10 sends/min per user)
8. Audit log: 'reply_send' event
9. Store sent message locally, link to thread

## Implementation Phases

### Phase 1: Foundation (Backend scaffolding + DB + Auth + Security)
- FastAPI app skeleton with config, CORS, health check
- Security middleware: CSRF, rate limiting, auth
- Token encryption module (AES-256-GCM)
- PostgreSQL + pgvector via Docker Compose
- Redis via Docker Compose
- Alembic migrations for full data model (including RLS policies)
- Google OAuth 2.0 flow (login, token refresh, JWT httpOnly cookies)
- Audit logging
- Next.js app skeleton with TailwindCSS, Zustand, TanStack Query
- Login page with Google OAuth redirect
- LLM consent screen
- Error handling and loading state components (shared across all phases)
- Empty state component

**Human checkpoint**: Review DB schema, auth flow, security middleware, and project structure before proceeding.

### Phase 2: Gmail Sync + Threading Engine
- Gmail API client (list messages, fetch full messages, incremental sync via historyId)
- Gmail API rate limiting with exponential backoff
- Message storage and deduplication
- JWZ threading algorithm implementation (including ghost message handling)
- Thread counter updates (message_count, participant_count)
- Celery worker for background sync + threading
- Group management API endpoints (add group, trigger sync, check status)
- Sync progress API endpoint (progress_current / progress_total)
- SyncProgress + SyncError UI components
- Basic group list + sync status UI

**Human checkpoint**: Verify threading correctness with real Gmail data before building UI.

### Phase 3: Thread Viewer + Reply
- Thread list API (paginated, sorted by last activity)
- Thread detail API (full hierarchy with messages, ghost nodes marked)
- Thread viewer UI (hierarchical display, collapse/expand, read/unread)
- MissingMessageGhost component for placeholder nodes
- Reply composer with ReplyContext (shows parent message quote)
- Send confirmation step
- Gmail API send integration with rate limiting
- Message card component (sender, date, body, actions)

**Human checkpoint**: Review thread viewer UX and reply flow before search work.

### Phase 4: Search
- Full-text search API endpoint with filters (parameterized queries)
- Embedding generation pipeline (Celery tasks)
- Semantic search via pgvector with HNSW index
- Combined ranking with score normalization (sigmoid on FTS, weighted sum)
- Search UI with filters, faceted results
- Search within thread
- Nugget FTS search

**Human checkpoint**: Test search quality with real data before knowledge features.

### Phase 5: Knowledge Base
- LLM-powered nugget extraction (Claude API integration, consent-gated)
- Nugget suggestion pipeline (opt-in per group, thread size guards)
- Nugget suggestion review page (/knowledge/suggestions — accept/reject)
- Manual nugget creation from message selection
- Flat tagging (no hierarchical collections for MVP)
- Knowledge base browser UI
- Nugget detail view with source thread context
- Dashboard with activity overview

**Human checkpoint**: Full MVP review before deployment prep.

### Phase 6: Deployment + Polish
- Docker Compose for full stack (frontend, backend, postgres, redis)
- Environment configuration (.env templates with all required vars)
- Responsive design pass
- Production Dockerfiles (multi-stage builds)

## Non-Goals for MVP

- Email/password authentication (Google OAuth only)
- IMAP sync (Gmail API only)
- Real-time updates / WebSockets (polling is fine for MVP)
- Mobile-specific UI (responsive web is sufficient)
- Export/import of knowledge base
- Multiple LLM provider support
- Self-registration (invite-only initially)
- Attachment preview/download
- Notification system
- Saved searches and search history (post-MVP — core search is sufficient for MVP)
- Hierarchical collections for nuggets (flat tags for MVP, collections post-MVP)
- Semantic search on nuggets (FTS is sufficient for user-created content)
- Nugget-to-nugget linking
- Drag-and-drop nugget organization

## Design Review Changes Log

Changes made in response to Round 1 design review (PM, Architect, Designer, Security, CTO):

1. Added per-user message duplication as explicit tradeoff in Key Decisions table
2. Specified JWT storage as httpOnly/Secure/SameSite=Strict cookies
3. Specified token encryption: AES-256-GCM with ENCRYPTION_KEY env var
4. Defined all RLS policies with USING clauses and join paths
5. Added RLS to thread_messages and message_embeddings
6. Added CSRF double-submit cookie pattern
7. Added rate limits for all endpoint classes
8. Added LLM data consent gate and consent screen
9. Added missing indexes on messages, threads, nuggets, thread_messages
10. Switched from IVFFlat to HNSW for embedding index
11. Defined counter update mechanism (threading service, not triggers)
12. Added score normalization (sigmoid on FTS) before combining with cosine similarity
13. Added gmail_history_id for incremental sync
14. Added first-time sync UX (SyncProgress, SyncError components)
15. Added sync error/recovery flow
16. Defined broken-thread ghost message UI (MissingMessageGhost component)
17. Defined reply-to-specific-message UX (ReplyContext + confirmation step)
18. Added nugget suggestion review surface (/knowledge/suggestions)
19. Moved saved searches and search history to Non-Goals
20. Descoped hierarchical collections to flat tags
21. Made auto nugget extraction opt-in per group with thread size guards
22. Removed nugget_embeddings table from MVP
23. Added audit_log table
24. Specified parameterized queries requirement
25. Specified error response format (no stack traces)
26. Stripped BCC from stored recipients
27. Stripped auth headers from raw_headers before storage
28. Made Claude model config-driven (env var, not hardcoded)
29. Moved error handling/loading states from Phase 6 to Phase 1
30. Added authStore security constraint (no raw tokens)
