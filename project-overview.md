# Smart Mailing List Archive & Knowledge Manager

## Initial Requirements

### User's Problem Statement

I have a mailing list that's on Google Groups that I'm a member of, and it has loads of really good information, but it's completely screwed up by the way different people's email systems work. I lose threads, and I can't really tell what was responded to when it was. It's also really filling up my inbox with a bunch of disconnected threads that it's hard to read through.

The other issue is that, on this email group, occasionally there are things that are really useful nuggets that I want to store and save. Like somebody says, "Oh, this is my stack for doing this type of development." And I want to be able to add that to my personal store of information.

Then, once I have the information, I want to be able to search, and also respond to messages in a way that pins on to the appropriate place in the thread. 

So I want to set this up so that it's something that anyone who is a member of any Google group can do. It'll have all the same functions for them that it does for me, but of course be stored separately.

There are a couple of issues that we'll have to figure out as we're going through this, in terms of how do I get my Google Groups info into this viewer. I will need to align things on the backend. I will probably have LLMs that are part of it.

## Research Findings

### Google Groups API Limitations

**Key Discovery**: Google does not provide a direct API for exporting Google Groups message archives. This appears to be an intentional decision.

**Available APIs**:
- **Admin SDK Directory API** - For creating, updating, and deleting groups and managing membership
- **Groups Settings API** - For managing group settings like permissions and message moderation
- **Groups Migration API** - Only for **importing** messages into Google Groups, not exporting
- **Cloud Identity Groups API** - REST API for working with Cloud Identity Groups

**Workarounds for Data Access**:
1. **Gmail API Method** - Query a group member's Gmail mailbox using `listid:group.domain.com`
2. **IMAP Access** - Retrieve messages from "All Mail" folder using X-GM-LABELS extension
3. **Email Forwarding** - Set up forwarding rules to capture new messages

### Email Threading Technology

**Standard Email Headers for Threading**:
- **Message-ID**: Unique identifier for each email
- **In-Reply-To**: Contains the message ID of the parent email
- **References**: Chain of message IDs to reconstruct discussion tree

**Threading Algorithms**:
- **JWZ (Jamie Zawinski) Algorithm** - Field-tested by millions of users, handles:
  - Missing messages
  - Non-compliant email clients
  - Subject-based grouping fallbacks
  - Broken threading reconstruction

**Additional Approaches**:
- Header meta-information based
- Timing, subject, and content analysis
- Topic-based heuristics for thread merging/decomposition

### Existing Archive Solutions

**Open Source Mailing List Archivers**:
- **HyperKitty** - Django-based archiver for Mailman 3
- **Pipermail** - Default archiver for Mailman 2 (legacy)
- **Listmonk** - High performance, self-hosted newsletter and mailing list manager
- **Gray Duck Mail** - Uses external email providers
- **Dada Mail** - Web-based list management for announcements/discussions

## Core Problems Being Solved

### Threading Issues
**Problem**: Different email clients break threads in various ways - missing headers, wrong References, subject-only threading
**Solution**: JWZ algorithm with fallbacks for subject matching, time-based grouping, and content similarity

### Lost Context
**Problem**: Can't tell what was responded to or when in broken threads
**Solution**: Reconstruct proper thread hierarchy, show visual thread flow, maintain complete conversation context

### Information Overload
**Problem**: Inbox filled with disconnected threads, hard to follow conversations
**Solution**: Unified thread view, collapse/expand controls, thread summaries, unread tracking per thread

### Knowledge Loss
**Problem**: Valuable information buried in email threads, no way to extract and save
**Solution**: LLM-powered extraction, manual highlighting, organized knowledge base, searchable nuggets

### Reply Positioning
**Problem**: Replies don't attach to the right place in threads
**Solution**: Proper RFC-compliant headers (Message-ID, In-Reply-To, References), visual confirmation of reply position

### Search Limitations
**Problem**: Gmail search doesn't understand thread context or content semantics
**Solution**: Full-text search, semantic search, thread-aware search, search within knowledge base

## Proposed Solution Architecture

### System Overview

A multi-tenant web application that:
1. Ingests Google Groups messages through multiple methods
2. Reconstructs proper email threading
3. Uses LLMs to extract knowledge and insights
4. Provides a clean, searchable interface with advanced search capabilities
5. Enables replying to messages with proper thread placement
6. Maintains a personal knowledge base per user

### Data Ingestion Strategy

#### Primary Method: Gmail API
- Users authorize OAuth access to their Gmail account
- System queries for group messages using `listid:` filter
- Preserves full email headers for threading
- Incremental sync capability

#### Secondary Method: IMAP Sync
- Direct IMAP connection to Gmail
- Filter by X-GM-LABELS
- Good for bulk initial imports

#### Tertiary Method: Email Forwarding
- Dedicated inbox for forwarded messages
- Real-time processing of new messages
- Fallback for restricted environments

### Core Components

#### Backend Services

**Message Ingestion Service**
- Handles multiple input methods (Gmail API, IMAP, forwarding)
- Message deduplication
- Header extraction and validation
- Queue management for processing

**Threading Engine**
- Implements JWZ algorithm
- Handles broken threads gracefully
- Subject-based fallback grouping
- Thread merging and splitting logic
- Maintains proper Message-ID/References chains for replies

**LLM Processing Pipeline**
- Thread summarization
- Topic extraction and categorization
- Knowledge nugget identification (flag posts that are informational introducing, rather than responding to someone else's post)
- Duplicate/spam detection

**Search & Retrieval System**
- Full-text search with PostgreSQL GIN indexes
- Semantic search using embeddings for concept matching
- Search operators (AND, OR, NOT, phrase matching)
- Filter by:
  - Date ranges
  - Sender/recipient
  - Thread participation
  - Has attachments
  - Tags/labels
  - Knowledge nugget status
- Search within specific threads
- Search across knowledge base
- Saved search queries with alerts
- Search suggestions based on history
- Faceted search results with counts

**Knowledge Base Manager**
- Extract and store insights
- User-defined collections
- Tagging and categorization
- Export capabilities

**Reply Service**
- Compose replies with proper threading headers (In-Reply-To, References)
- Send via Gmail API or SMTP
- Generate unique Message-IDs following RFC 5322
- Maintain complete References chain for deep threads
- Quote original message with proper attribution
- Track sent messages and link to threads
- Support both plain text and HTML formats
- Handle attachments if needed
- Preserve group recipient lists (Reply vs Reply All)

#### Data Model

```
Users
├── Authentication (OAuth tokens, refresh tokens)
├── Preferences (sync settings, UI preferences)
├── Groups (subscriptions)
│   ├── Group metadata (name, domain, member count)
│   ├── Sync status (last sync, message count)
│   ├── Messages
│   │   ├── Headers (Message-ID, References, In-Reply-To, Subject)
│   │   ├── Content (plain text, HTML, attachments)
│   │   ├── Metadata (sender, recipients, date, labels)
│   │   └── Processing status (threaded, analyzed, indexed)
│   ├── Threads (reconstructed conversations)
│   │   ├── Thread metadata (participants, message count, date range)
│   │   ├── Thread summary (LLM-generated)
│   │   └── Thread tags (auto and manual)
│   └── Settings (filters, notification preferences)
└── Knowledge Base
    ├── Nuggets (extracted insights)
    │   ├── Source message reference
    │   ├── Extracted content
    │   ├── Context (thread summary)
    │   └── Confidence score
    ├── Tags/Categories (hierarchical)
    ├── Collections (user-organized folders)
    └── Annotations (user notes on nuggets)
```

#### Frontend Features

**Thread Viewer**
- Hierarchical conversation display
- Collapsed/expanded thread states
- Visual indicators for read/unread
- Inline reply with proper thread positioning
- Reply to specific messages in thread
- Thread-level actions (archive, star, tag)
- Visual thread flow indicators

**Search Interface**
- Advanced search with filters
- Search suggestions
- Search history
- Saved searches
- Search within threads

**Knowledge Management**
- Nugget extraction interface
- Drag-and-drop organization
- Tagging and categorization
- Markdown editor for notes
- Link related nuggets
- Export nuggets to markdown or access via API

**Dashboard**
- Activity timeline
- Unread message count
- Recent nuggets
- Popular threads
- Group statistics

### Technical Stack

#### Backend
- **Framework**: FastAPI (Python) - async support, good performance
- **Database**: PostgreSQL - full-text search, JSONB for flexibility
- **Cache**: Redis - session management, job queues
- **Task Queue**: Celery - background processing
- **Message Broker**: RabbitMQ or Redis

#### LLM Integration
- **Primary**: OpenAI API or Anthropic Claude
- **Embeddings**: Sentence Transformers (local)
- **Orchestration**: LangChain
- **Vector Store**: pgvector or Pinecone
- **Fallback**: Local models (Ollama) for privacy

#### Frontend
- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **Styling**: TailwindCSS
- **State Management**: Zustand
- **Data Fetching**: Tanstack Query
- **Rich Text**: TipTap or Lexical

### Security & Privacy

#### Authentication
- Google OAuth 2.0 primary
- Optional email/password with 2FA
- JWT tokens with refresh rotation
- Session management in Redis

#### Data Protection
- Row-level security in PostgreSQL
- Encrypted fields for sensitive data
- TLS for all connections
- Encrypted backups

#### Multi-tenancy
- Complete data isolation per user
- Separate schemas or filtered queries
- No cross-user data leakage
- Audit logging

#### Compliance
- GDPR data export/deletion
- Data retention policies
- Privacy policy and ToS
- Cookie consent management

### Deployment Architecture

**Containerization**: Docker-based deployment for consistency across environments
**Database**: PostgreSQL with pgvector extension for semantic search
**Cache Layer**: Redis for session management and job queues
**Background Jobs**: Celery with Redis/RabbitMQ for async processing
**API Gateway**: FastAPI with async support
**Frontend Delivery**: Next.js with SSR/SSG capabilities

## Open Questions for Decision

1. **Authentication Preference**
   - Google OAuth only?
   - Support multiple auth providers?
   - Custom auth system?

2. **LLM Strategy**
   - Which provider(s) to support?
   - Cost management for processing?
   - Privacy concerns with external APIs?

3. **Storage Requirements**
   - Expected messages per user?
   - Attachment handling?
   - Retention policies?

4. **Update Frequency**
   - Real-time requirements?
   - Batch processing schedule?
   - User-triggered vs automatic?

5. **Deployment Model**
   - SaaS offering?
   - Self-hosted only?
   - Both options?

6. **Monetization (if applicable)**
   - Free tier limits?
   - Pricing model?
   - Enterprise features?

7. **Privacy & Legal**
   - Data residency requirements?
   - Email content liability?
   - Terms of service needs?

## Key Framework Decisions Required

### Critical Technical Choices

1. **Primary Data Access Method**
   - Gmail API (requires user OAuth consent)
   - IMAP (requires app passwords)
   - Hybrid approach

2. **Reply Mechanism**
   - Gmail API send (maintains full integration)
   - SMTP relay (more universal but less integrated)
   - Both with user preference

3. **Search Architecture**
   - PostgreSQL full-text search only
   - PostgreSQL + vector embeddings (pgvector)
   - External search service (Elasticsearch/Typesense)

4. **LLM Integration Approach**
   - API-only (OpenAI/Anthropic)
   - Hybrid with local models for privacy
   - Fully local (Ollama/llama.cpp)

5. **Frontend Framework**
   - Next.js (full-stack capabilities)
   - Separate SPA (React/Vue) + API
   - HTMX + server templates (simpler, less JS)