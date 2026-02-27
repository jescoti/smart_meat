# Smart Meat MVP Design Document

## Status: DRAFT — Pending Design Review

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
    db/
      engine.py                # Async SQLAlchemy engine
      models.py                # ORM models
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
      gmail.py                 # Gmail API client (sync, fetch)
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

### Frontend (Next.js 14 + TypeScript)

**Directory structure:**
```
frontend/
  src/
    app/
      layout.tsx               # Root layout, providers
      page.tsx                 # Landing / redirect to dashboard
      login/page.tsx           # Google OAuth login
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
        [nuggetId]/page.tsx    # Nugget detail
    components/
      thread/
        ThreadViewer.tsx       # Hierarchical thread display
        MessageCard.tsx        # Individual message in thread
        ReplyComposer.tsx      # Inline reply with threading
      search/
        SearchBar.tsx          # Search input with suggestions
        SearchResults.tsx      # Results with facets
        SearchFilters.tsx      # Date, sender, tags filters
      knowledge/
        NuggetCard.tsx         # Knowledge nugget display
        NuggetExtractor.tsx    # Extract nugget from message
        CollectionView.tsx     # User collection browser
      layout/
        Sidebar.tsx            # Navigation sidebar
        Header.tsx             # Top bar with search
    lib/
      api.ts                   # API client (fetch wrapper)
      auth.ts                  # Auth utilities
      hooks/
        useThreads.ts          # TanStack Query hooks
        useSearch.ts
        useKnowledge.ts
    stores/
      authStore.ts             # Zustand auth state
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

### Data Model (PostgreSQL)

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_id TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    avatar_url TEXT,
    access_token TEXT,          -- encrypted
    refresh_token TEXT,         -- encrypted
    token_expires_at TIMESTAMPTZ,
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
    sync_status TEXT DEFAULT 'pending',  -- pending, syncing, completed, error
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, google_group_id)
);

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
    recipients JSONB,                -- {to: [], cc: [], bcc: []}
    date TIMESTAMPTZ NOT NULL,
    body_text TEXT,
    body_html TEXT,
    has_attachments BOOLEAN DEFAULT FALSE,
    attachments JSONB,               -- [{name, mime_type, size}]
    labels TEXT[],
    is_read BOOLEAN DEFAULT FALSE,
    raw_headers JSONB,
    processing_status TEXT DEFAULT 'pending',  -- pending, threaded, analyzed, indexed
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(group_id, gmail_id)
);

-- Full-text search index
CREATE INDEX idx_messages_fts ON messages
    USING GIN (to_tsvector('english', coalesce(subject, '') || ' ' || coalesce(body_text, '')));

-- Threads table (reconstructed by JWZ)
CREATE TABLE threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
    root_message_id UUID REFERENCES messages(id),
    subject TEXT NOT NULL,
    participant_count INTEGER DEFAULT 0,
    message_count INTEGER DEFAULT 0,
    first_message_at TIMESTAMPTZ,
    last_message_at TIMESTAMPTZ,
    summary TEXT,                     -- LLM-generated
    tags TEXT[],                      -- auto + manual tags
    is_starred BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Thread-message relationship (preserves hierarchy)
CREATE TABLE thread_messages (
    thread_id UUID REFERENCES threads(id) ON DELETE CASCADE,
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    parent_message_id UUID REFERENCES messages(id),  -- NULL for root
    depth INTEGER DEFAULT 0,
    position INTEGER DEFAULT 0,       -- ordering within thread
    PRIMARY KEY (thread_id, message_id)
);

-- Embeddings for semantic search
CREATE TABLE message_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE UNIQUE,
    embedding vector(384),            -- sentence-transformers dimension
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_message_embeddings_ivfflat
    ON message_embeddings USING ivfflat (embedding vector_cosine_ops);

-- Knowledge nuggets
CREATE TABLE nuggets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    source_message_id UUID REFERENCES messages(id),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    context TEXT,                      -- thread context / summary
    extraction_type TEXT NOT NULL,     -- 'manual' | 'llm_auto' | 'llm_suggested'
    confidence_score FLOAT,           -- LLM confidence (0-1)
    tags TEXT[],
    collection_id UUID,
    is_archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Nugget embeddings for semantic search
CREATE TABLE nugget_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nugget_id UUID REFERENCES nuggets(id) ON DELETE CASCADE UNIQUE,
    embedding vector(384),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Collections (user-organized folders for nuggets)
CREATE TABLE collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    parent_id UUID REFERENCES collections(id),  -- hierarchical
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE nuggets ADD CONSTRAINT fk_nuggets_collection
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE SET NULL;

-- Row-level security
ALTER TABLE groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE nuggets ENABLE ROW LEVEL SECURITY;
ALTER TABLE collections ENABLE ROW LEVEL SECURITY;
```

### Authentication Flow

```
User → Click "Sign in with Google"
  → Google OAuth consent screen (scopes: email, profile, gmail.readonly, gmail.send)
  → Redirect back with auth code
  → Backend exchanges code for tokens
  → Create/update user record
  → Issue JWT (access + refresh)
  → Frontend stores JWT, redirects to dashboard
```

### Gmail Sync Flow

```
User → Add Google Group
  → Backend queries Gmail API: messages matching listid:<group-email>
  → Fetch message headers + bodies in batches
  → Store in messages table
  → Queue threading job (Celery)
  → JWZ algorithm reconstructs threads
  → Queue LLM processing (summarize, extract nuggets)
  → Queue embedding generation
  → Update sync status
```

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

### LLM Processing Pipeline

```
Message stored → Celery task queued
  → Thread complete? (all known references resolved)
    → Yes: Summarize thread via Claude API
    → No: Wait for more messages
  → Scan for knowledge nuggets:
    → Claude identifies informational posts (not just replies)
    → Score confidence, extract key insight
    → Store as suggested nuggets (user confirms/rejects)
  → Generate embeddings for semantic search
```

**Claude API usage:**
- Thread summarization: `claude-sonnet-4-5-20250514` (cost-effective for summaries)
- Nugget extraction: `claude-sonnet-4-5-20250514` (good reasoning at lower cost)
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2` (local, free)

### Search Architecture

**Full-text search (PostgreSQL FTS):**
- GIN index on `subject || body_text`
- `ts_query` with operators: AND (`&`), OR (`|`), NOT (`!`), phrase (`<->`)
- `ts_rank` for relevance scoring
- Filter by: date range, sender, group, has_attachments, tags

**Semantic search (pgvector):**
- Query embedding generated at search time
- Cosine similarity against message_embeddings + nugget_embeddings
- Combined scoring: `0.7 * fts_rank + 0.3 * cosine_similarity`

## Implementation Phases

### Phase 1: Foundation (Backend scaffolding + DB + Auth)
- FastAPI app skeleton with config, CORS, health check
- PostgreSQL + pgvector via Docker Compose
- Redis via Docker Compose
- Alembic migrations for full data model
- Google OAuth 2.0 flow (login, token refresh, JWT issuance)
- Next.js app skeleton with TailwindCSS, Zustand, TanStack Query
- Login page with Google OAuth redirect

**Human checkpoint**: Review DB schema, auth flow, and project structure before proceeding.

### Phase 2: Gmail Sync + Threading Engine
- Gmail API client (list messages, fetch full messages, incremental sync)
- Message storage and deduplication
- JWZ threading algorithm implementation
- Celery worker for background sync + threading
- Group management API endpoints (add group, trigger sync, check status)
- Basic group list + sync status UI

**Human checkpoint**: Verify threading correctness with real Gmail data before building UI.

### Phase 3: Thread Viewer + Reply
- Thread list API (paginated, sorted by last activity)
- Thread detail API (full hierarchy with messages)
- Thread viewer UI (hierarchical display, collapse/expand, read/unread)
- Reply composer with proper threading headers (In-Reply-To, References)
- Gmail API send integration
- Message card component (sender, date, body, actions)

**Human checkpoint**: Review thread viewer UX and reply flow before search work.

### Phase 4: Search
- Full-text search API endpoint with filters
- Embedding generation pipeline (Celery tasks)
- Semantic search via pgvector
- Combined ranking (FTS + semantic)
- Search UI with filters, suggestions, faceted results
- Search within thread

**Human checkpoint**: Test search quality with real data before knowledge features.

### Phase 5: Knowledge Base
- LLM-powered nugget extraction (Claude API integration)
- Nugget suggestion pipeline (auto-detect informational posts)
- Manual nugget creation from message selection
- Collections and tagging
- Knowledge base browser UI
- Nugget detail view with source thread context
- Dashboard with activity overview

**Human checkpoint**: Full MVP review before deployment prep.

### Phase 6: Deployment + Polish
- Docker Compose for full stack (frontend, backend, postgres, redis)
- Environment configuration (.env templates)
- Error handling and loading states
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
