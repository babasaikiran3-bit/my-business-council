# Message Editing & Version History Design

This document describes the implementation of ChatGPT-style message editing for LLM Council, where users can edit any previous message in a conversation, regenerate responses from that point, and navigate between different versions.

## Overview

The core insight is that message editing creates a **tree structure**: each edit creates a new branch from a shared parent. This design uses parent pointers to represent this tree efficiently.

## Data Structure

### Current (Linear Array)
```json
{
  "id": "conversation-id",
  "title": "...",
  "messages": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "stage1": [...], "stage2": [...], "stage3": {...} }
  ]
}
```

### New (Tree with Parent Pointers)
```json
{
  "id": "conversation-id",
  "title": "...",
  "created_at": "...",
  "schema_version": 2,
  "messages": {
    "m_abc123": {
      "id": "m_abc123",
      "parent_id": null,
      "role": "user",
      "content": "What is the capital of France?",
      "created_at": "2024-01-14T10:00:00Z"
    },
    "m_def456": {
      "id": "m_def456",
      "parent_id": "m_abc123",
      "role": "assistant",
      "stage1": [...],
      "stage2": [...],
      "stage3": {...},
      "created_at": "2024-01-14T10:00:05Z"
    },
    "m_ghi789": {
      "id": "m_ghi789",
      "parent_id": "m_def456",
      "role": "user",
      "content": "What about Germany?",
      "created_at": "2024-01-14T10:01:00Z"
    },
    "m_jkl012": {
      "id": "m_jkl012",
      "parent_id": "m_ghi789",
      "role": "assistant",
      "stage1": [...],
      "stage2": [...],
      "stage3": {...},
      "created_at": "2024-01-14T10:01:05Z"
    }
  },
  "current_leaf_id": "m_jkl012"
}
```

### After Editing First Message

User edits "What is the capital of France?" → "What is the largest city in France?"

```json
{
  "messages": {
    "m_abc123": { "id": "m_abc123", "parent_id": null, "role": "user", "content": "What is the capital of France?" },
    "m_def456": { "id": "m_def456", "parent_id": "m_abc123", "role": "assistant", ... },
    "m_ghi789": { "id": "m_ghi789", "parent_id": "m_def456", "role": "user", "content": "What about Germany?" },
    "m_jkl012": { "id": "m_jkl012", "parent_id": "m_ghi789", "role": "assistant", ... },

    "m_mno345": { "id": "m_mno345", "parent_id": null, "role": "user", "content": "What is the largest city in France?" },
    "m_pqr678": { "id": "m_pqr678", "parent_id": "m_mno345", "role": "assistant", ... }
  },
  "current_leaf_id": "m_pqr678"
}
```

The tree now looks like:
```
null
├── m_abc123 (user: "capital of France?")
│   └── m_def456 (assistant)
│       └── m_ghi789 (user: "What about Germany?")
│           └── m_jkl012 (assistant)
│
└── m_mno345 (user: "largest city in France?")  ← EDITED VERSION
    └── m_pqr678 (assistant)
```

## Key Concepts

### Message Path
The ordered list of message IDs from root to a given leaf. Computed by traversing `parent_id` chain and reversing.

```python
def get_message_path(messages: dict, leaf_id: str) -> list[str]:
    path = []
    current_id = leaf_id
    while current_id is not None:
        path.append(current_id)
        current_id = messages[current_id]["parent_id"]
    return list(reversed(path))
```

### Siblings
Messages that share the same `parent_id`. These represent different versions/edits at the same position in the conversation.

```python
def get_siblings(messages: dict, message_id: str) -> list[str]:
    target_parent = messages[message_id]["parent_id"]
    return [
        mid for mid, msg in messages.items()
        if msg["parent_id"] == target_parent and msg["role"] == messages[message_id]["role"]
    ]
```

### Current Branch
The conversation as currently viewed, determined by `current_leaf_id`. The UI displays only messages in the path from root to this leaf.

## API Changes

### Modified Endpoints

#### `GET /api/conversations/{id}`

Returns conversation with tree structure:

```json
{
  "id": "...",
  "title": "...",
  "created_at": "...",
  "schema_version": 2,
  "messages": { ... },
  "current_leaf_id": "m_xyz",
  "current_path": ["m_abc", "m_def", "m_xyz"]
}
```

The `current_path` is computed server-side for convenience.

#### `POST /api/conversations/{id}/message`

Now requires `parent_id` for non-root messages (derived from `current_leaf_id` if not provided):

Request:
```json
{
  "content": "User's message"
}
```

The endpoint automatically uses `current_leaf_id` as the parent for the new message.

### New Endpoints

#### `POST /api/conversations/{id}/message/edit`

Edit an existing user message, creating a new branch.

Request:
```json
{
  "message_id": "m_abc123",
  "content": "Edited message content"
}
```

Response: Same as `/message` endpoint (stage1, stage2, stage3, metadata)

Behavior:
1. Validate `message_id` exists and is a user message
2. Create new user message with same `parent_id` as the edited message
3. Run council to generate response
4. Create assistant message as child of new user message
5. Update `current_leaf_id` to new assistant message
6. Return response

#### `POST /api/conversations/{id}/navigate`

Switch to a different branch.

Request:
```json
{
  "message_id": "m_def456"
}
```

Response:
```json
{
  "current_leaf_id": "m_jkl012",
  "current_path": ["m_abc123", "m_def456", "m_ghi789", "m_jkl012"]
}
```

Behavior:
1. Find the leaf of the branch containing `message_id`
2. Update `current_leaf_id`
3. Return updated path

To find the leaf: if `message_id` is already a leaf (no children), use it. Otherwise, find the "default" descendant (e.g., first child at each level, or most recent).

## Frontend Changes

### State Management

```javascript
// App.jsx state
const [currentConversation, setCurrentConversation] = useState({
  id: null,
  messages: {},           // Map of message_id -> message
  current_leaf_id: null,
  current_path: []        // Computed path for display
});
```

### UI Components

#### Edit Button
- Appears on hover over user messages
- Click opens inline editor or modal
- Submit calls `/message/edit` endpoint

#### Version Navigator
```jsx
<MessageVersionNav
  messageId="m_abc123"
  siblings={["m_abc123", "m_mno345"]}  // All versions at this position
  currentIndex={0}
  onNavigate={(newMessageId) => api.navigate(convId, newMessageId)}
/>
// Renders: < 1/2 > with clickable arrows
```

#### Message Display
- Only render messages in `current_path`
- Pass sibling info to each message for version navigation

### User Flow

1. **View conversation**: Messages displayed in `current_path` order
2. **Edit message**:
   - Click edit on user message
   - Modify text, submit
   - Loading state while council runs
   - New response appears, version nav shows "2/2"
3. **Navigate versions**:
   - Click < or > on version navigator
   - API updates `current_leaf_id`
   - UI re-renders with new path

## Migration

### Strategy
Run migration on first access (lazy) or via script (eager).

### Migration Logic
```python
def migrate_v1_to_v2(conversation: dict) -> dict:
    if conversation.get("schema_version", 1) >= 2:
        return conversation

    messages_dict = {}
    prev_id = None

    for msg in conversation.get("messages", []):
        msg_id = generate_message_id()
        messages_dict[msg_id] = {
            **msg,
            "id": msg_id,
            "parent_id": prev_id,
            "created_at": msg.get("created_at", conversation["created_at"])
        }
        prev_id = msg_id

    return {
        "id": conversation["id"],
        "title": conversation.get("title", ""),
        "created_at": conversation["created_at"],
        "schema_version": 2,
        "messages": messages_dict,
        "current_leaf_id": prev_id
    }
```

### Backward Compatibility
- Check `schema_version` on load
- Migrate in-memory if v1, save as v2
- New conversations always use v2

## Edge Cases

### Empty Conversation
- `messages`: `{}`
- `current_leaf_id`: `null`
- First message creates root with `parent_id: null`

### Edit Root Message
- New message also has `parent_id: null`
- Both are "roots" (siblings with null parent)

### Navigate to Middle of Branch
- Find leaf by traversing children
- Default: follow first/oldest child at each level
- Alternative: follow most recent child

### Concurrent Edits
- Not supported in v1
- Each edit creates independent branch
- No merge capability

## Testing Plan

1. **Unit tests** for storage functions:
   - `get_message_path()`
   - `get_siblings()`
   - `migrate_v1_to_v2()`

2. **API tests**:
   - Create conversation, add messages, verify tree structure
   - Edit message, verify new branch created
   - Navigate, verify path updates

3. **Frontend tests**:
   - Render conversation with multiple branches
   - Edit flow with loading states
   - Version navigation

4. **Integration tests**:
   - Full flow: create → message → edit → navigate → continue
   - Migration of existing conversations

## Future Enhancements

- **Branch naming**: Allow users to name branches
- **Branch comparison**: Side-by-side view of different branches
- **Merge branches**: Combine insights from multiple branches
- **Delete branch**: Remove unwanted branches
- **Branch from assistant**: Edit/regenerate assistant responses
