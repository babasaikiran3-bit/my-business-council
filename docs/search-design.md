# Search Feature Design Document

This document outlines the design for adding ChatGPT-style search functionality to LLM Council, enabling users to search across their conversation history.

## Problem Statement

As users accumulate conversations in LLM Council, finding specific past discussions becomes increasingly difficult. Users need the ability to:
- Search for conversations by keywords or phrases
- Find specific messages within conversations
- Quickly navigate to relevant past discussions
- Search both active and archived conversations

## Current State

### Data Storage
- Conversations stored as JSON files in `data/conversations/` (active) and `data/archived/` (archived)
- Tree-based message structure with parent pointers (schema v2)
- Each conversation contains:
  - `title`: Conversation title
  - `messages`: Dict of message objects, each with:
    - User messages: `content` field with the query text
    - Assistant messages: `stage1` (individual responses), `stage2` (rankings), `stage3` (final synthesis)

### Scale Considerations
- Personal/small team tool, not enterprise scale
- Currently: ~40 archived conversations, ~4 active conversations
- Expected growth: Hundreds to low thousands of conversations over time
- Message sizes vary: Simple greetings to multi-paragraph discussions

## Research Findings

### Approach 1: Simple In-Memory Text Search

**How it works**: Load all conversations into memory and use Python string matching (case-insensitive substring search).

**Libraries**: None required (built-in Python)

**Pros**:
- Zero dependencies
- Trivial implementation (~50 lines)
- No indexing overhead or storage
- Works immediately with existing data

**Cons**:
- O(n) search time - must scan all text
- No relevance ranking
- No fuzzy matching or typo tolerance
- Memory usage scales with data size
- Slower as data grows (though still fast for small datasets)

**Best for**: Very small datasets (<100 conversations), prototyping

### Approach 2: SQLite FTS5 (Full-Text Search)

**How it works**: Create a SQLite database with FTS5 virtual table that indexes conversation text. Queries use the built-in BM25 ranking algorithm.

**Libraries**: `sqlite3` (built-in Python), optionally `pysqlite3` for newer FTS5 features

**Pros**:
- Part of Python standard library
- Proven, mature technology
- Fast indexing and retrieval
- BM25 relevance ranking out of the box
- Supports prefix matching, phrase queries, boolean operators
- Can use 'porter' stemmer for word variations
- Single file database, easy to backup/reset
- Memory efficient - data stays on disk

**Cons**:
- Requires index synchronization (rebuild when conversations change)
- No semantic understanding (misses synonyms/related concepts)
- No typo tolerance by default (trigram tokenizer can help but increases index size)
- Query syntax can be confusing for users

**Best for**: Small to medium datasets, keyword-based search

### Approach 3: Semantic/Vector Search (Embeddings)

**How it works**: Convert text to vector embeddings using a model like `all-MiniLM-L6-v2`, store in a vector database like ChromaDB, search using cosine similarity.

**Libraries**: `chromadb`, `sentence-transformers`

**Pros**:
- Understands semantic meaning (finds conceptually similar content)
- Works across languages
- No exact keyword match required
- Can find "what did I ask about Python errors?" even if query didn't contain those exact words

**Cons**:
- Significant dependencies (~300MB for embedding model)
- Slower initial indexing (must generate embeddings)
- Higher memory usage
- May miss exact keyword matches that lexical search would find
- Overkill for small datasets
- Requires re-embedding on data changes

**Best for**: Large datasets, concept-based search, multilingual support

### Approach 4: Hybrid Search (Full-Text + Vector)

**How it works**: Combine SQLite FTS5 for keyword matching with ChromaDB for semantic search. Merge results using Reciprocal Rank Fusion (RRF).

**Libraries**: `sqlite3`, `chromadb`, `sentence-transformers`

**Pros**:
- Best of both worlds - exact matches AND semantic similarity
- Handles edge cases better (product names, jargon + natural language)
- Most similar to enterprise search experiences

**Cons**:
- Most complex to implement
- Highest resource usage
- Two indices to maintain
- Significant overkill for personal tool scale

**Best for**: Large-scale applications, production systems

## Recommended Approach: SQLite FTS5

### Justification

For LLM Council's use case, **SQLite FTS5** offers the best balance of:

1. **Simplicity**: No external services, single-file storage, familiar SQL
2. **Performance**: Handles thousands of documents easily, sub-millisecond queries
3. **Features**: BM25 ranking, phrase search, boolean operators, snippets
4. **Maintenance**: Zero-dependency (built into Python), easy to reset/rebuild
5. **Extensibility**: Can add semantic search later if needed

The semantic search approach is tempting but introduces significant complexity for marginal benefit at this scale. Users searching their own conversations typically remember keywords from their queries.

### Why Not Simpler?
Simple string matching lacks ranking (which result is most relevant?) and becomes slow as data grows. SQLite FTS5 is barely more complex to implement but provides much better UX.

### Why Not More Complex?
Hybrid search and pure semantic search add substantial dependencies and complexity. For a personal tool with hundreds of conversations, this is premature optimization.

## High-Level Implementation Plan

### Phase 1: Backend (Python)

#### 1.1 Create Search Index Module (`backend/search.py`)

```python
"""Search index management using SQLite FTS5."""

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

SEARCH_DB_PATH = "data/search_index.db"

def init_search_db():
    """Initialize the FTS5 search database."""
    conn = sqlite3.connect(SEARCH_DB_PATH)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS conversation_search USING fts5(
            conversation_id,
            message_id,
            role,
            content,
            tokenize='porter unicode61'
        )
    """)
    conn.commit()
    conn.close()

def index_conversation(conversation: Dict[str, Any]):
    """Index a conversation's messages for search."""
    # Extract searchable text from messages
    # For user messages: content
    # For assistant messages: stage3.response (final answer)
    pass

def search(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Search conversations using FTS5.

    Returns list of {conversation_id, message_id, snippet, rank}
    """
    pass

def rebuild_index():
    """Rebuild the entire search index from conversation files."""
    pass
```

#### 1.2 Searchable Content Strategy

What to index per message:
- **User messages**: `content` field (the user's question)
- **Assistant messages**: `stage3.response` (the final synthesized answer)
  - Optionally: individual model responses from `stage1` for more comprehensive search
  - Skip `stage2` (rankings) as they're procedural, not content-focused

Also index:
- **Conversation title**: Include in search for navigation
- **Conversation ID**: For linking results back to conversations

#### 1.3 Add API Endpoints (`backend/main.py`)

```python
@app.get("/api/search")
async def search_conversations(q: str, limit: int = 20):
    """
    Search across all conversations.

    Returns:
    {
        "results": [
            {
                "conversation_id": "...",
                "conversation_title": "...",
                "message_id": "...",  # null if title match
                "snippet": "...matched text...",
                "message_role": "user" | "assistant",
                "rank": 1.5
            }
        ],
        "query": "original query",
        "total_results": 15
    }
    """
    pass

@app.post("/api/search/rebuild")
async def rebuild_search_index():
    """Rebuild the search index (admin operation)."""
    pass
```

#### 1.4 Index Maintenance

Keep index in sync with conversations:
- **On new message**: Add to index after saving conversation
- **On conversation delete/archive**: Remove from index (or mark as archived)
- **Startup**: Verify index exists, rebuild if missing

### Phase 2: Frontend (React)

#### 2.1 Search UI Component (`frontend/src/components/Search.jsx`)

```jsx
// Search modal/sidebar with:
// - Search input with debounced API calls
// - Results list showing conversation title + snippet
// - Click result -> navigate to conversation (and optionally to specific message)
// - Keyboard navigation (arrow keys, enter to select)
// - Cmd/Ctrl+K shortcut to open search
```

#### 2.2 Integration Points

- Add search icon/button to sidebar header
- Global keyboard shortcut handler
- Navigation to specific conversation on result click
- Highlight matching text in conversation view (optional enhancement)

### Phase 3: Polish & Edge Cases

- Handle archived conversations in search results
- Pagination for large result sets
- Empty state UI
- Loading states
- Error handling
- Index corruption recovery

## Data Schema

### Search Index Table (SQLite FTS5)

```sql
CREATE VIRTUAL TABLE conversation_search USING fts5(
    conversation_id,        -- UUID of conversation
    conversation_title,     -- For searching by title
    message_id,            -- Message ID within conversation (null for title-only entry)
    role,                  -- 'user' or 'assistant'
    content,               -- Searchable text content
    created_at UNINDEXED,  -- For sorting (not searchable)
    tokenize='porter unicode61'
);
```

### Search Result Object

```typescript
interface SearchResult {
  conversation_id: string;
  conversation_title: string;
  message_id: string | null;
  role: 'user' | 'assistant';
  snippet: string;  // Highlighted excerpt
  rank: number;     // BM25 relevance score
  created_at: string;
}
```

## API Design

### `GET /api/search?q={query}&limit={limit}`

Search across all conversations.

**Parameters**:
- `q` (required): Search query string
- `limit` (optional, default 20): Maximum results to return
- `include_archived` (optional, default true): Include archived conversations

**Response**:
```json
{
  "results": [
    {
      "conversation_id": "50d62784-999a-405c-a390-78b9205c3b28",
      "conversation_title": "Python Error Debugging",
      "message_id": "m_abc123",
      "role": "user",
      "snippet": "...how do I fix this <mark>Python</mark> <mark>error</mark>...",
      "rank": 2.5,
      "created_at": "2026-01-16T18:24:34.452959"
    }
  ],
  "query": "python error",
  "total_results": 3
}
```

### `POST /api/search/rebuild`

Rebuild the search index from scratch.

**Response**:
```json
{
  "status": "success",
  "indexed_conversations": 44,
  "indexed_messages": 312,
  "duration_ms": 450
}
```

## User Experience

### Search Flow

1. User presses `Cmd+K` (Mac) or `Ctrl+K` (Windows/Linux)
2. Search modal appears with focus on input
3. User types query; results update after 300ms debounce
4. Results show conversation title and relevant snippet
5. User clicks result or uses keyboard to navigate
6. Modal closes, selected conversation loads
7. (Optional) Scroll to matching message within conversation

### Result Display

```
┌─────────────────────────────────────────────────────┐
│ 🔍 Search conversations...                    [esc] │
├─────────────────────────────────────────────────────┤
│                                                     │
│ ▸ Python Error Debugging                            │
│   "...how do I fix this Python error..."            │
│   Jan 15, 2026                                      │
│                                                     │
│   Machine Learning Basics                           │
│   "...Python libraries for ML include..."           │
│   Jan 10, 2026                                      │
│                                                     │
│   API Design Discussion                             │
│   "...using Python FastAPI framework..."            │
│   Jan 8, 2026                                       │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Future Extensibility

### Easy Additions
- **Date filters**: Add `created_at > date` to FTS5 query
- **Role filters**: Search only user questions or only assistant answers
- **Conversation-specific search**: Limit search to current conversation

### Possible Upgrades (If Needed Later)
- **Semantic search layer**: Add ChromaDB alongside FTS5 for hybrid search
- **Typo tolerance**: Add trigram tokenizer or integrate fuzzy matching
- **Search analytics**: Track popular queries to improve title generation

### Migration Path to Hybrid Search

If semantic search becomes necessary:
1. Add `backend/embeddings.py` with ChromaDB integration
2. Generate embeddings on index rebuild
3. Query both FTS5 and ChromaDB
4. Merge results using RRF
5. No breaking changes to API - same response format

## Implementation Checklist

- [ ] Create `backend/search.py` with FTS5 functions
- [ ] Add search index initialization to startup
- [ ] Implement `index_conversation()` function
- [ ] Implement `search()` function with BM25 ranking
- [ ] Add `rebuild_index()` function
- [ ] Add `/api/search` endpoint
- [ ] Add `/api/search/rebuild` endpoint
- [ ] Update `save_conversation()` to trigger re-indexing
- [ ] Create `frontend/src/components/Search.jsx`
- [ ] Add global keyboard shortcut handler
- [ ] Implement search results display
- [ ] Add navigation on result click
- [ ] Handle loading/error states
- [ ] Test with archived conversations
- [ ] Add search to sidebar UI

## Estimated Effort

- Backend: 2-3 hours
- Frontend: 2-3 hours
- Testing & polish: 1-2 hours
- **Total: ~1 day**

## References

- [SQLite FTS5 Documentation](https://www.sqlite.org/fts5.html)
- [ChatGPT Search Feature](https://help.openai.com/en/articles/10056348-how-do-i-search-my-chat-history-in-chatgpt)
- [Whoosh (alternative considered)](https://github.com/mchaput/whoosh)
- [ChromaDB (for future semantic search)](https://www.trychroma.com/)
- [Tantivy-py (high-performance alternative)](https://github.com/quickwit-oss/tantivy-py)
