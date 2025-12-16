# WORKOS.md - Authentication Implementation Guide

This document provides the complete implementation plan for adding WorkOS authentication with Microsoft SSO to the Eternal Copilot application. It serves as the single source of truth for authentication alongside `CLAUDE.md`.

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
   - 1.1 [User Type Classification](#11-user-type-classification)
2. [Implementation Components](#2-implementation-components)
3. [Database Schema Design](#3-database-schema-design)
4. [Migration Strategy](#4-migration-strategy)
5. [WorkOS Configuration for Multi-Auth](#5-workos-configuration-for-multi-auth)
6. [Conversation Sharing Architecture](#6-conversation-sharing-architecture)
7. [Role-Based Access Control (RBAC)](#7-role-based-access-control-rbac)
8. [Implementation Phases](#8-implementation-phases)
9. [Security Best Practices](#9-security-best-practices)
10. [Files to Create/Modify](#10-files-to-createmodify)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (React/Vite)                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │  AuthKitProvider│  │  SignIn/SignUp  │  │  Protected Routes           │  │
│  │  (wraps App)    │  │  (Microsoft SSO)│  │  (useAuth, withAuth)        │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
│                                    │                                         │
│                        Authorization Header (Access Token)                  │
│                                    ▼                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                              BACKEND (FastAPI)                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │  Auth Middleware│  │  Token Validation│ │  User Context Dependency    │  │
│  │  (verify WorkOS │  │  (WorkOS SDK)   │  │  (get_current_user)         │  │
│  │   tokens)       │  │                 │  │                             │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    Storage Layer (User-Scoped)                          ││
│  │   data/users/{user_id}/conversations/{conversation_id}.json             ││
│  │   data/users/{user_id}/profile.json (cached user data)                  ││
│  │   data/shared/{conversation_id}.json (for shared conversations)         ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

### Authentication Flow

1. User visits application → AuthKitProvider checks auth state
2. If not authenticated → Redirect to WorkOS AuthKit hosted UI
3. User selects authentication method (Microsoft SSO, Google, email)
4. After successful login → WorkOS issues access token + refresh token
5. Frontend includes token in `Authorization: Bearer <token>` header
6. Backend validates token using WorkOS User Management API
7. User ID extracted from token → Used to scope all data access

### 1.1 User Type Classification

The system supports multiple user types with different authentication methods, capabilities, and data access levels. This architecture is designed to be extensible for future user types.

#### User Type Taxonomy

| User Type | Description | Auth Method | Default Role | Data Scope |
|-----------|-------------|-------------|--------------|------------|
| `employee` | Internal organization employees | Microsoft SSO (Azure AD) | `user` | Full access to own + shared conversations |
| `external_partner` | Trusted external collaborators | Email/password or Google SSO | `user` | Shared conversations only (no creation by default) |
| `guest` | Temporary access users | Magic link or invite code | `viewer` | View-only on specific shared conversations |
| `service_account` | API integrations | API key (no interactive login) | `service` | Programmatic access only |

#### User Type Metadata Structure

User types are stored in WorkOS User Management metadata alongside roles:

```json
{
  "user_type": "employee",
  "role": "user",
  "organization_id": "org_eternal",
  "department": "Engineering",
  "provisioned_via": "microsoft_oauth",
  "capabilities": {
    "can_create_conversations": true,
    "can_share_conversations": true,
    "can_use_copilot": true,
    "max_conversations_per_day": null
  }
}
```

#### User Type Detection Flow

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        User Type Detection Logic                           │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  User Signs In                                                             │
│       │                                                                    │
│       ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Check Authentication Provider (from WorkOS authentication_method)  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                    │
│       ├── MicrosoftOAuth + email @eternal.ag ──► user_type=employee        │
│       │                                                                    │
│       ├── GoogleOAuth/Password ──► Check invite/allow-list                 │
│       │       │                                                            │
│       │       ├── Has partner invite ──► user_type=external_partner        │
│       │       └── On allow-list ──► user_type=external_partner             │
│       │                                                                    │
│       ├── MagicAuth ──► user_type=guest (time-limited)                     │
│       │                                                                    │
│       └── API key ──► user_type=service_account                            │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

#### Capabilities by User Type

```python
# backend/user_types.py

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class UserType(str, Enum):
    EMPLOYEE = "employee"
    EXTERNAL_PARTNER = "external_partner"
    GUEST = "guest"
    SERVICE_ACCOUNT = "service_account"


@dataclass
class UserCapabilities:
    """Defines what a user can do based on their type."""
    can_create_conversations: bool = False
    can_share_conversations: bool = False
    can_use_copilot: bool = False
    can_invite_users: bool = False
    can_view_analytics: bool = False
    max_conversations_per_day: Optional[int] = None
    max_messages_per_conversation: Optional[int] = None
    session_timeout_hours: Optional[int] = None


# Default capabilities by user type
USER_TYPE_DEFAULTS: dict[UserType, UserCapabilities] = {
    UserType.EMPLOYEE: UserCapabilities(
        can_create_conversations=True,
        can_share_conversations=True,
        can_use_copilot=True,
        can_invite_users=True,
        can_view_analytics=True,
        max_conversations_per_day=None,  # Unlimited
        max_messages_per_conversation=None,
        session_timeout_hours=None,  # Use WorkOS default
    ),
    UserType.EXTERNAL_PARTNER: UserCapabilities(
        can_create_conversations=True,  # Can create but limited
        can_share_conversations=False,  # Cannot re-share
        can_use_copilot=True,
        can_invite_users=False,
        can_view_analytics=False,
        max_conversations_per_day=10,
        max_messages_per_conversation=50,
        session_timeout_hours=24,
    ),
    UserType.GUEST: UserCapabilities(
        can_create_conversations=False,  # View-only
        can_share_conversations=False,
        can_use_copilot=False,  # Can only view results
        can_invite_users=False,
        can_view_analytics=False,
        max_conversations_per_day=0,
        max_messages_per_conversation=0,
        session_timeout_hours=4,  # Short session
    ),
    UserType.SERVICE_ACCOUNT: UserCapabilities(
        can_create_conversations=True,
        can_share_conversations=False,
        can_use_copilot=True,
        can_invite_users=False,
        can_view_analytics=True,
        max_conversations_per_day=1000,  # Rate limited
        max_messages_per_conversation=100,
        session_timeout_hours=None,  # Token-based
    ),
}


def get_user_capabilities(user_type: UserType, overrides: dict = None) -> UserCapabilities:
    """Get capabilities for a user type with optional overrides."""
    defaults = USER_TYPE_DEFAULTS.get(user_type, USER_TYPE_DEFAULTS[UserType.GUEST])

    if overrides:
        # Apply overrides from user's publicMetadata.capabilities
        return UserCapabilities(
            can_create_conversations=overrides.get(
                'can_create_conversations', defaults.can_create_conversations),
            can_share_conversations=overrides.get(
                'can_share_conversations', defaults.can_share_conversations),
            can_use_copilot=overrides.get(
                'can_use_copilot', defaults.can_use_copilot),
            can_invite_users=overrides.get(
                'can_invite_users', defaults.can_invite_users),
            can_view_analytics=overrides.get(
                'can_view_analytics', defaults.can_view_analytics),
            max_conversations_per_day=overrides.get(
                'max_conversations_per_day', defaults.max_conversations_per_day),
            max_messages_per_conversation=overrides.get(
                'max_messages_per_conversation', defaults.max_messages_per_conversation),
            session_timeout_hours=overrides.get(
                'session_timeout_hours', defaults.session_timeout_hours),
        )

    return defaults
```

---

## 2. Implementation Components

### 2.1 Frontend Changes

#### A. Install WorkOS AuthKit React SDK and React Router

```bash
cd frontend
npm install @workos-inc/authkit-react react-router-dom
```

**Note:** React Router is required for handling the OAuth callback route at `/callback`. The application currently doesn't use routing, so this adds minimal complexity while enabling proper OAuth flow handling.

#### B. Environment Variables

Create `frontend/.env` (development):
```env
VITE_WORKOS_CLIENT_ID=client_xxxxx
VITE_WORKOS_REDIRECT_URI=http://localhost:5173/callback
```

#### C. Modified Entry Point with React Router (`frontend/src/main.jsx`)

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthKitProvider } from '@workos-inc/authkit-react'
import './index.css'
import App from './App.jsx'

const WORKOS_CLIENT_ID = import.meta.env.VITE_WORKOS_CLIENT_ID

if (!WORKOS_CLIENT_ID) {
  throw new Error("Missing WorkOS Client ID")
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthKitProvider clientId={WORKOS_CLIENT_ID}>
        <App />
      </AuthKitProvider>
    </BrowserRouter>
  </StrictMode>,
)
```

#### D. New AuthGuard Component (`frontend/src/components/AuthGuard.jsx`)

```jsx
import { useAuth } from '@workos-inc/authkit-react'

export function AuthGuard({ children }) {
  const { isLoading, user, signIn } = useAuth()

  if (isLoading) {
    return <div className="flex h-screen items-center justify-center">Loading...</div>
  }

  if (!user) {
    // Redirect to WorkOS AuthKit hosted UI
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-center">
          <h2 className="text-2xl font-bold mb-4">Eternal Copilot</h2>
          <p className="text-muted-foreground mb-6">Sign in to continue</p>
          <button
            onClick={() => signIn()}
            className="px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
          >
            Sign In
          </button>
        </div>
      </div>
    )
  }

  return children
}

export function useCurrentUser() {
  const { user } = useAuth()

  // Extract metadata from WorkOS user object
  const metadata = user?.metadata || {}

  return {
    id: user?.id,
    email: user?.email,
    name: user?.firstName && user?.lastName
      ? `${user.firstName} ${user.lastName}`
      : user?.email,
    imageUrl: user?.profilePictureUrl,
    role: metadata.role || 'user',
    userType: metadata.user_type || 'employee',
    organizationId: metadata.organization_id,
    authMethod: user?.ssoProfile?.connectionType || 'password',
  }
}
```

#### E. Callback Component (`frontend/src/components/Callback.jsx`)

WorkOS AuthKit requires a callback route to handle the OAuth redirect. This component handles errors gracefully with an inline error display instead of redirecting to a non-existent error page:

```jsx
import { useEffect, useState } from 'react'
import { useAuth } from '@workos-inc/authkit-react'
import { useNavigate } from 'react-router-dom'

export function Callback() {
  const { handleCallback, isLoading } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState(null)

  useEffect(() => {
    async function processCallback() {
      try {
        await handleCallback()
        navigate('/', { replace: true })
      } catch (err) {
        console.error('Auth callback error:', err)
        setError(err.message || 'Authentication failed. Please try again.')
      }
    }
    processCallback()
  }, [handleCallback, navigate])

  // Show error state with retry option
  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-center max-w-md p-6">
          <div className="text-destructive text-4xl mb-4">⚠️</div>
          <h2 className="text-xl font-bold mb-2">Authentication Error</h2>
          <p className="text-muted-foreground mb-4">{error}</p>
          <button
            onClick={() => navigate('/', { replace: true })}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
          >
            Return to Sign In
          </button>
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Signing in...</p>
        </div>
      </div>
    )
  }

  return null
}
```

#### F. Modified App Component with React Router (`frontend/src/App.jsx`)

The App component now uses React Router to handle the `/callback` route for OAuth:

```jsx
import { useState, useEffect, useRef } from 'react';
import { Routes, Route } from 'react-router-dom';
import { useAuth } from '@workos-inc/authkit-react';
import { AuthGuard, useCurrentUser } from './components/AuthGuard';
import { Callback } from './components/Callback';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import UserMenu from './components/UserMenu';
import { api } from './api';

function App() {
  return (
    <Routes>
      {/* OAuth callback route - must be outside AuthGuard */}
      <Route path="/callback" element={<Callback />} />

      {/* All other routes require authentication */}
      <Route path="/*" element={
        <AuthGuard>
          <AuthenticatedApp />
        </AuthGuard>
      } />
    </Routes>
  )
}

function AuthenticatedApp() {
  const { getAccessToken } = useAuth();
  const currentUser = useCurrentUser();
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  // Set auth token for API calls
  useEffect(() => {
    api.setTokenGetter(getAccessToken);
  }, [getAccessToken]);

  // ... rest of existing App component logic ...

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        userMenu={<UserMenu />}
      />
      <ChatInterface
        conversation={currentConversation}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        stageTimings={stageTimings}
        modelStatuses={modelStatuses}
        modelTimings={modelTimings}
      />
    </div>
  );
}

export default App;
```

#### G. Modified API Client with 401 Retry Logic (`frontend/src/api.js`)

The API client includes automatic token refresh and retry on 401 (Unauthorized) responses. This handles token expiration gracefully without requiring user intervention:

```javascript
/**
 * API client for the Eternal Copilot backend with WorkOS authentication.
 * Includes automatic token refresh and retry on 401 responses.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || (
  import.meta.env.PROD ? '' : 'http://localhost:8001'
);

let getAccessToken = null;

// Track if we're currently refreshing to prevent multiple refresh attempts
let isRefreshing = false;
let refreshPromise = null;

export const api = {
  /**
   * Set the token getter function from WorkOS AuthKit's useAuth hook.
   * WorkOS AuthKit's getAccessToken supports a forceRefresh option.
   */
  setTokenGetter(tokenGetter) {
    getAccessToken = tokenGetter;
  },

  /**
   * Get authorization headers with WorkOS access token.
   * @param {boolean} forceRefresh - Force token refresh before getting headers
   */
  async getAuthHeaders(forceRefresh = false) {
    if (!getAccessToken) return {};

    try {
      // WorkOS AuthKit's getAccessToken accepts options including forceRefresh
      const token = await getAccessToken({ forceRefresh });
      return token ? { 'Authorization': `Bearer ${token}` } : {};
    } catch (error) {
      console.error('Failed to get access token:', error);
      return {};
    }
  },

  /**
   * Force refresh the access token.
   * Returns new auth headers or throws if refresh fails.
   */
  async refreshToken() {
    // Prevent multiple simultaneous refresh attempts
    if (isRefreshing) {
      return refreshPromise;
    }

    isRefreshing = true;
    refreshPromise = this.getAuthHeaders(true);

    try {
      const headers = await refreshPromise;
      return headers;
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  },

  /**
   * Make a fetch request with automatic 401 retry.
   * If a 401 is received, refreshes the token and retries once.
   */
  async fetchWithRetry(url, options = {}, retryCount = 0) {
    const authHeaders = await this.getAuthHeaders();
    const response = await fetch(url, {
      ...options,
      headers: {
        ...options.headers,
        ...authHeaders,
      },
    });

    // If 401 and haven't retried yet, refresh token and retry once
    if (response.status === 401 && retryCount < 1) {
      console.log('Received 401, attempting token refresh and retry...');

      try {
        const newHeaders = await this.refreshToken();

        // Retry the request with new token
        const retryResponse = await fetch(url, {
          ...options,
          headers: {
            ...options.headers,
            ...newHeaders,
          },
        });

        return retryResponse;
      } catch (refreshError) {
        console.error('Token refresh failed:', refreshError);
        // Return original 401 response if refresh fails
        return response;
      }
    }

    return response;
  },

  /**
   * List all conversations for the authenticated user.
   */
  async listConversations() {
    const response = await this.fetchWithRetry(`${API_BASE}/api/conversations`);
    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication required. Please sign in again.');
      }
      throw new Error('Failed to list conversations');
    }
    return response.json();
  },

  /**
   * Create a new conversation.
   */
  async createConversation() {
    const response = await this.fetchWithRetry(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication required. Please sign in again.');
      }
      throw new Error('Failed to create conversation');
    }
    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await this.fetchWithRetry(
      `${API_BASE}/api/conversations/${conversationId}`
    );
    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication required. Please sign in again.');
      }
      throw new Error('Failed to get conversation');
    }
    return response.json();
  },

  /**
   * Improve a prompt using an LLM.
   */
  async improvePrompt(content) {
    const response = await this.fetchWithRetry(`${API_BASE}/api/improve-prompt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication required. Please sign in again.');
      }
      throw new Error('Failed to improve prompt');
    }
    return response.json();
  },

  /**
   * Send a message in a conversation.
   */
  async sendMessage(conversationId, content) {
    const response = await this.fetchWithRetry(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      }
    );
    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication required. Please sign in again.');
      }
      throw new Error('Failed to send message');
    }
    return response.json();
  },

  /**
   * Send a message and receive streaming updates.
   * Note: SSE streams use initial token; if token expires mid-stream,
   * the stream will fail and should be retried by the caller.
   */
  async sendMessageStream(conversationId, content, onEvent) {
    const authHeaders = await this.getAuthHeaders();
    let response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders,
        },
        body: JSON.stringify({ content }),
      }
    );

    // Handle 401 with token refresh for SSE
    if (response.status === 401) {
      console.log('SSE received 401, attempting token refresh and retry...');
      const newHeaders = await this.refreshToken();
      response = await fetch(
        `${API_BASE}/api/conversations/${conversationId}/message/stream`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...newHeaders,
          },
          body: JSON.stringify({ content }),
        }
      );
    }

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication required. Please sign in again.');
      }
      throw new Error('Failed to send message');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event = JSON.parse(data);
            onEvent(event.type, event);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },
};
```

#### H. New UserMenu Component (`frontend/src/components/UserMenu.jsx`)

```jsx
import { useAuth } from '@workos-inc/authkit-react'
import { useCurrentUser } from './AuthGuard'

export default function UserMenu() {
  const { signOut } = useAuth()
  const user = useCurrentUser()

  return (
    <div className="flex items-center gap-3">
      {user.imageUrl ? (
        <img
          src={user.imageUrl}
          alt={user.name}
          className="w-8 h-8 rounded-full"
        />
      ) : (
        <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-sm font-medium">
          {user.name?.charAt(0) || user.email?.charAt(0) || '?'}
        </div>
      )}
      <div className="flex flex-col">
        <span className="text-sm font-medium">{user.name}</span>
        <span className="text-xs text-muted-foreground">{user.email}</span>
      </div>
      <button
        onClick={() => signOut()}
        className="ml-2 px-3 py-1 text-sm text-muted-foreground hover:text-foreground"
      >
        Sign Out
      </button>
    </div>
  )
}
```

### 2.2 Backend Changes

#### A. Install Python Dependencies

Add to `pyproject.toml`:
```toml
dependencies = [
    # ... existing deps ...
    "workos>=5.0.0",       # WorkOS Python SDK
    "httpx>=0.25.0",       # For async HTTP requests
    "cachetools>=5.3.0",   # For token caching (TTL cache)
    "slowapi>=0.1.9",      # For rate limiting
]
```

Then run:
```bash
uv sync
```

#### B. Configuration Updates (`backend/config.py`)

Add WorkOS configuration:
```python
import os

# WorkOS Authentication
WORKOS_API_KEY = os.getenv("WORKOS_API_KEY")
WORKOS_CLIENT_ID = os.getenv("WORKOS_CLIENT_ID")

# User roles for RBAC
class UserRole:
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
    SERVICE = "service"
```

#### C. New Auth Module (`backend/auth.py`)

```python
"""WorkOS Authentication for FastAPI with token caching."""

import httpx
import logging
from workos import WorkOSClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from dataclasses import dataclass
from functools import lru_cache
from cachetools import TTLCache
import asyncio
from .config import WORKOS_API_KEY, WORKOS_CLIENT_ID

# Configure logging for auth events (useful for debugging and audit)
logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# Token cache: Store verified tokens for 45 seconds to reduce API calls
# Max 1000 tokens in cache to prevent memory issues
# TTL of 45 seconds balances latency reduction with security (tokens refresh quickly)
_token_cache: TTLCache = TTLCache(maxsize=1000, ttl=45)
_token_cache_lock = asyncio.Lock()


@lru_cache()
def get_workos_client() -> WorkOSClient:
    """Get cached WorkOS client."""
    if not WORKOS_API_KEY:
        raise ValueError("WORKOS_API_KEY environment variable not set")
    return WorkOSClient(api_key=WORKOS_API_KEY, client_id=WORKOS_CLIENT_ID)


@dataclass
class AuthenticatedUser:
    """Represents an authenticated user from WorkOS."""
    id: str  # WorkOS user ID (e.g., "user_01H...")
    email: Optional[str] = None
    name: Optional[str] = None
    role: str = "user"
    user_type: str = "employee"  # employee, external_partner, guest, service_account
    organization_id: Optional[str] = None
    auth_provider: Optional[str] = None  # MicrosoftOAuth, GoogleOAuth, Password, MagicAuth
    capabilities: Optional[dict] = None  # Override capabilities from metadata

    def has_role(self, *roles: str) -> bool:
        """Check if user has any of the specified roles."""
        return self.role in roles

    def is_admin(self) -> bool:
        return self.role == "admin"

    def is_employee(self) -> bool:
        return self.user_type == "employee"

    def is_external(self) -> bool:
        return self.user_type in ("external_partner", "guest")

    def can_create_conversations(self) -> bool:
        """Check if user can create new conversations."""
        if self.capabilities and 'can_create_conversations' in self.capabilities:
            return self.capabilities['can_create_conversations']
        # Default by user type
        return self.user_type in ("employee", "external_partner", "service_account")

    def can_share_conversations(self) -> bool:
        """Check if user can share conversations."""
        if self.capabilities and 'can_share_conversations' in self.capabilities:
            return self.capabilities['can_share_conversations']
        return self.user_type == "employee"

    def can_use_copilot(self) -> bool:
        """Check if user can submit queries to the Eternal Copilot."""
        if self.capabilities and 'can_use_copilot' in self.capabilities:
            return self.capabilities['can_use_copilot']
        return self.user_type in ("employee", "external_partner", "service_account")


async def verify_workos_token(token: str) -> dict:
    """
    Verify WorkOS access token and return user info.

    WorkOS AuthKit uses opaque access tokens that must be verified
    via the User Management API, not JWT verification.

    This function implements a 45-second TTL cache to reduce latency
    from repeated WorkOS API calls. The cache is thread-safe using asyncio locks.
    """
    # Check cache first (with lock to prevent race conditions)
    async with _token_cache_lock:
        if token in _token_cache:
            logger.debug("Token cache hit")
            return _token_cache[token]

    # Token not in cache, verify with WorkOS API
    try:
        workos = get_workos_client()

        # Use WorkOS User Management to get user from access token
        user = workos.user_management.get_user_by_access_token(token)

        user_info = {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "profile_picture_url": user.profile_picture_url,
            "metadata": user.metadata or {},
            "email_verified": user.email_verified,
            "created_at": user.created_at,
        }

        # Cache the verified token (with lock)
        async with _token_cache_lock:
            _token_cache[token] = user_info
            logger.debug(f"Token cached for user {user.id}")

        return user_info

    except Exception as e:
        # Log the actual error for debugging (server-side only)
        logger.warning(f"Token verification failed: {str(e)}")

        # Return generic error message to client (don't leak internal details)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def invalidate_token_cache(token: str = None):
    """
    Invalidate token cache entries.

    Args:
        token: Specific token to invalidate. If None, clears entire cache.
    """
    if token:
        _token_cache.pop(token, None)
    else:
        _token_cache.clear()


async def get_user_auth_method(user_id: str) -> Optional[str]:
    """Get the authentication method used by a user."""
    try:
        workos = get_workos_client()

        # Get user's authentication methods
        identities = workos.user_management.list_identities(user_id=user_id)

        for identity in identities.data:
            # Return the first identity type
            return identity.type  # 'MicrosoftOAuth', 'GoogleOAuth', 'Password', 'MagicAuth'

        return None
    except Exception:
        return None


def detect_user_type_from_user(user_info: dict, auth_method: Optional[str]) -> str:
    """
    Detect user type based on authentication method and email domain.

    Priority:
    1. Explicit user_type in metadata (already set by admin/webhook)
    2. Detection based on auth provider and email domain
    3. Default to 'guest' for unknown
    """
    import os
    metadata = user_info.get("metadata", {})

    EMPLOYEE_EMAIL_DOMAIN = os.getenv("EMPLOYEE_EMAIL_DOMAIN", "eternal.ag")

    # 1. Check for explicit user_type
    if "user_type" in metadata:
        return metadata["user_type"]

    # 2. Detect based on auth provider
    email = user_info.get("email", "")

    # Check for Microsoft SSO with company domain
    if auth_method == "MicrosoftOAuth":
        if email.endswith(f"@{EMPLOYEE_EMAIL_DOMAIN}"):
            return "employee"

    # Check for Google SSO (likely external partner)
    if auth_method == "GoogleOAuth":
        return "external_partner"

    # Password users
    if auth_method == "Password":
        return "external_partner"

    # Magic link users are guests
    if auth_method == "MagicAuth":
        return "guest"

    # 3. Default to guest
    return "guest"


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> AuthenticatedUser:
    """
    FastAPI dependency to get the current authenticated user.

    Extracts user info including user_type from WorkOS User Management.

    Usage:
        @app.get("/api/conversations")
        async def list_conversations(user: AuthenticatedUser = Depends(get_current_user)):
            return storage.list_conversations(user_id=user.id)
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_info = await verify_workos_token(credentials.credentials)
    metadata = user_info.get("metadata", {})

    # Get authentication method
    auth_method = await get_user_auth_method(user_info["id"])

    # Detect user type
    user_type = detect_user_type_from_user(user_info, auth_method)

    # Build user name from WorkOS user info
    first_name = user_info.get("first_name", "")
    last_name = user_info.get("last_name", "")
    name = f"{first_name} {last_name}".strip() or user_info.get("email")

    # Extract user info from WorkOS
    return AuthenticatedUser(
        id=user_info["id"],  # WorkOS user ID
        email=user_info.get("email"),
        name=name,
        role=metadata.get("role", "user"),
        user_type=user_type,
        organization_id=metadata.get("organization_id"),
        auth_provider=auth_method,
        capabilities=metadata.get("capabilities"),
    )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[AuthenticatedUser]:
    """Get user if authenticated, None otherwise (for public endpoints)."""
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


def require_role(*roles: str):
    """Decorator-style dependency for role-based access control."""
    async def role_checker(user: AuthenticatedUser = Depends(get_current_user)):
        if not user.has_role(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(roles)}"
            )
        return user
    return role_checker
```

#### D. Modified Storage Module (`backend/storage.py`)

```python
"""User-scoped JSON storage for conversations."""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from .config import DATA_DIR


# Directory structure:
# data/users/{user_id}/conversations/{conversation_id}.json
# data/users/{user_id}/profile.json
# data/shared/{conversation_id}.json (for shared conversations)


def get_user_data_dir(user_id: str) -> str:
    """Get the data directory for a specific user."""
    return os.path.join(DATA_DIR, "users", user_id, "conversations")


def get_shared_data_dir() -> str:
    """Get the directory for shared conversations."""
    return os.path.join(DATA_DIR, "shared")


def ensure_user_data_dir(user_id: str):
    """Ensure the user's data directory exists."""
    Path(get_user_data_dir(user_id)).mkdir(parents=True, exist_ok=True)


def get_conversation_path(conversation_id: str, user_id: str) -> str:
    """Get the file path for a user's conversation."""
    return os.path.join(get_user_data_dir(user_id), f"{conversation_id}.json")


def create_conversation(conversation_id: str, user_id: str) -> Dict[str, Any]:
    """Create a new conversation for a user."""
    ensure_user_data_dir(user_id)

    conversation = {
        "id": conversation_id,
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "title": "New Conversation",
        "messages": [],
        # Sharing and permissions
        "sharing": {
            "is_public": False,
            "shared_with": [],  # List of {user_id, permission: "view"|"edit"}
        }
    }

    path = get_conversation_path(conversation_id, user_id)
    with open(path, 'w') as f:
        json.dump(conversation, f, indent=2)

    return conversation


def get_conversation(conversation_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Load a conversation - checks ownership and sharing permissions."""
    # First check user's own conversations
    path = get_conversation_path(conversation_id, user_id)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)

    # TODO: Check shared conversations
    return None


def save_conversation(conversation: Dict[str, Any], user_id: str):
    """Save a conversation to storage."""
    ensure_user_data_dir(user_id)
    path = get_conversation_path(conversation['id'], user_id)
    with open(path, 'w') as f:
        json.dump(conversation, f, indent=2)


def list_conversations(user_id: str) -> List[Dict[str, Any]]:
    """List all conversations for a user (including shared with them)."""
    ensure_user_data_dir(user_id)
    user_dir = get_user_data_dir(user_id)

    conversations = []
    if os.path.exists(user_dir):
        for filename in os.listdir(user_dir):
            if filename.endswith('.json'):
                path = os.path.join(user_dir, filename)
                with open(path, 'r') as f:
                    data = json.load(f)
                    conversations.append({
                        "id": data["id"],
                        "created_at": data["created_at"],
                        "title": data.get("title", "New Conversation"),
                        "message_count": len(data["messages"]),
                        "is_owner": True,
                    })

    # Sort by creation time, newest first
    conversations.sort(key=lambda x: x["created_at"], reverse=True)
    return conversations


def add_user_message(conversation_id: str, user_id: str, content: str):
    """Add a user message to a conversation."""
    conversation = get_conversation(conversation_id, user_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "user",
        "content": content
    })
    conversation["updated_at"] = datetime.utcnow().isoformat()

    save_conversation(conversation, user_id)


def add_assistant_message(
    conversation_id: str,
    user_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any]
):
    """Add an assistant message with all 3 stages to a conversation."""
    conversation = get_conversation(conversation_id, user_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "assistant",
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3
    })
    conversation["updated_at"] = datetime.utcnow().isoformat()

    save_conversation(conversation, user_id)


def update_conversation_title(conversation_id: str, user_id: str, title: str):
    """Update the title of a conversation."""
    conversation = get_conversation(conversation_id, user_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["title"] = title
    save_conversation(conversation, user_id)
```

#### E. Modified API Endpoints (`backend/main.py`)

```python
"""FastAPI backend for Eternal Copilot with WorkOS authentication."""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import uuid
import json
import asyncio

from . import storage
from .auth import get_current_user, AuthenticatedUser, require_role
from .copilot import (
    run_full_copilot,
    generate_conversation_title,
    stage1_collect_responses,
    stage1_collect_responses_with_progress,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
    improve_user_prompt,
    get_copilot_models,
)

app = FastAPI(title="Eternal Copilot API")

# CORS configuration (unchanged)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models (unchanged)
class CreateConversationRequest(BaseModel):
    pass

class SendMessageRequest(BaseModel):
    content: str

class ImprovePromptRequest(BaseModel):
    content: str


# Health check (no auth required)
@app.get("/")
async def root():
    return {"status": "ok", "service": "Eternal Copilot API"}


# Protected endpoints
@app.get("/api/conversations")
async def list_conversations(user: AuthenticatedUser = Depends(get_current_user)):
    """List all conversations for the authenticated user."""
    return storage.list_conversations(user_id=user.id)


@app.post("/api/conversations")
async def create_conversation(
    request: CreateConversationRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Create a new conversation for the authenticated user."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id, user_id=user.id)
    return conversation


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Get a specific conversation (must be owner or have share access)."""
    conversation = storage.get_conversation(conversation_id, user_id=user.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Send a message and run the 3-stage copilot process."""
    conversation = storage.get_conversation(conversation_id, user_id=user.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_first_message = len(conversation["messages"]) == 0

    storage.add_user_message(conversation_id, user.id, request.content)

    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, user.id, title)

    stage1_results, stage2_results, stage3_result, metadata = await run_full_copilot(
        request.content
    )

    storage.add_assistant_message(
        conversation_id,
        user.id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/improve-prompt")
async def improve_prompt(
    request: ImprovePromptRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Improve a user's prompt using an LLM."""
    improved = await improve_user_prompt(request.content)
    return {"improved_prompt": improved}


# Admin-only endpoint example
@app.get("/api/admin/stats")
async def admin_stats(user: AuthenticatedUser = Depends(require_role("admin"))):
    """Get system statistics (admin only)."""
    # Implementation...
    return {"total_users": 0, "total_conversations": 0}
```

---

## 3. Database Schema Design

The current JSON-based storage can be migrated to a proper database. Here's the recommended schema for PostgreSQL (compatible with Supabase):

### 3.1 Users Table (Synced from WorkOS)

```sql
-- User type enum for type safety
CREATE TYPE user_type_enum AS ENUM ('employee', 'external_partner', 'guest', 'service_account');

CREATE TABLE users (
    id VARCHAR(255) PRIMARY KEY,  -- WorkOS user ID (user_xxx)
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),

    -- User classification
    user_type user_type_enum NOT NULL DEFAULT 'guest',
    role VARCHAR(50) DEFAULT 'user',  -- admin, user, viewer, service

    -- Authentication info
    auth_provider VARCHAR(50),  -- oauth_microsoft, oauth_google, email_password, api_key
    email_domain VARCHAR(255),  -- Extracted for quick domain-based queries

    -- Multi-tenancy
    organization_id VARCHAR(255),  -- For multi-tenancy
    department VARCHAR(255),  -- Optional: For employee organization

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP,

    -- Capabilities and settings
    capabilities JSONB DEFAULT '{}',  -- Override default capabilities
    settings JSONB DEFAULT '{}'  -- User preferences
);

-- Indexes for common queries
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_email_domain ON users(email_domain);
CREATE INDEX idx_users_organization ON users(organization_id);
CREATE INDEX idx_users_user_type ON users(user_type);
CREATE INDEX idx_users_role ON users(role);

-- Composite index for user type + role queries
CREATE INDEX idx_users_type_role ON users(user_type, role);
```

### 3.2 User Type Allow Lists

For controlling which external users can access the system:

```sql
-- Allow list for external partners (by email or domain)
CREATE TABLE user_allow_list (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Match criteria (one of these should be set)
    email VARCHAR(255),  -- Specific email
    email_domain VARCHAR(255),  -- All users from domain (e.g., "partner.com")

    -- What they get
    user_type user_type_enum NOT NULL DEFAULT 'external_partner',
    default_role VARCHAR(50) DEFAULT 'user',
    default_capabilities JSONB DEFAULT '{}',

    -- Metadata
    invited_by VARCHAR(255) REFERENCES users(id),
    expires_at TIMESTAMP,  -- Optional expiry
    created_at TIMESTAMP DEFAULT NOW(),
    notes TEXT,  -- Admin notes about this allow-list entry

    -- Constraints
    CONSTRAINT check_email_or_domain CHECK (
        (email IS NOT NULL AND email_domain IS NULL) OR
        (email IS NULL AND email_domain IS NOT NULL)
    )
);

CREATE INDEX idx_allow_list_email ON user_allow_list(email);
CREATE INDEX idx_allow_list_domain ON user_allow_list(email_domain);
```

### 3.2 Conversations Table

```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    owner_id VARCHAR(255) NOT NULL REFERENCES users(id),
    title VARCHAR(255) DEFAULT 'New Conversation',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    settings JSONB DEFAULT '{}'
);

CREATE INDEX idx_conversations_owner ON conversations(owner_id);
CREATE INDEX idx_conversations_updated ON conversations(updated_at DESC);
```

### 3.3 Messages Table

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- 'user' or 'assistant'
    content TEXT,  -- For user messages
    stage1 JSONB,  -- For assistant messages
    stage2 JSONB,
    stage3 JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_created ON messages(created_at);
```

### 3.4 Conversation Sharing (ACL)

```sql
CREATE TABLE conversation_shares (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    shared_with_user_id VARCHAR(255) REFERENCES users(id),
    shared_with_email VARCHAR(255),  -- Allow sharing before user signs up
    permission VARCHAR(20) NOT NULL,  -- 'view', 'edit', 'admin'
    created_by VARCHAR(255) NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,  -- Optional expiry

    UNIQUE(conversation_id, shared_with_user_id),
    UNIQUE(conversation_id, shared_with_email)
);

CREATE INDEX idx_shares_user ON conversation_shares(shared_with_user_id);
CREATE INDEX idx_shares_email ON conversation_shares(shared_with_email);
CREATE INDEX idx_shares_conversation ON conversation_shares(conversation_id);
```

### 3.5 Organizations (Multi-Tenancy)

```sql
CREATE TABLE organizations (
    id VARCHAR(255) PRIMARY KEY,  -- From WorkOS Organizations
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE organization_members (
    organization_id VARCHAR(255) REFERENCES organizations(id),
    user_id VARCHAR(255) REFERENCES users(id),
    role VARCHAR(50) NOT NULL,  -- 'owner', 'admin', 'member'
    joined_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (organization_id, user_id)
);

CREATE INDEX idx_org_members_user ON organization_members(user_id);

-- Create Eternal as Tenant #1 (initial organization)
INSERT INTO organizations (id, name, slug, settings)
VALUES (
    'org_eternal',
    'Eternal',
    'eternal',
    '{"employee_email_domain": "eternal.ag"}'::jsonb
);
```

### 3.6 Row Level Security (RLS) Policies

For Supabase, add RLS policies to enforce access control:

```sql
-- Enable RLS on all tables
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_shares ENABLE ROW LEVEL SECURITY;

-- Users can only see their own conversations (or shared with them)
CREATE POLICY "Users can view own conversations" ON conversations
    FOR SELECT USING (
        owner_id = auth.uid()::text
        OR id IN (
            SELECT conversation_id FROM conversation_shares
            WHERE shared_with_user_id = auth.uid()::text
        )
    );

-- Users can only insert their own conversations
CREATE POLICY "Users can create own conversations" ON conversations
    FOR INSERT WITH CHECK (owner_id = auth.uid()::text);

-- Users can only update their own conversations
CREATE POLICY "Users can update own conversations" ON conversations
    FOR UPDATE USING (owner_id = auth.uid()::text);

-- Messages inherit conversation access
CREATE POLICY "Users can view messages in accessible conversations" ON messages
    FOR SELECT USING (
        conversation_id IN (
            SELECT id FROM conversations
            WHERE owner_id = auth.uid()::text
        )
        OR conversation_id IN (
            SELECT conversation_id FROM conversation_shares
            WHERE shared_with_user_id = auth.uid()::text
        )
    );
```

---

## 4. Migration Strategy

### 4.1 Migration Script

Create `scripts/migrate_conversations.py`:

```python
#!/usr/bin/env python3
"""
Migrate existing conversations to user-scoped storage.

Usage:
    python -m scripts.migrate_conversations --default-user USER_ID
    python -m scripts.migrate_conversations --assign-to-admin

Prerequisites:
    1. Deploy authentication code first
    2. Have admin sign in to get their WorkOS user ID
    3. Run this script with the admin's user ID
"""

import os
import json
import shutil
import argparse
from datetime import datetime
from pathlib import Path

OLD_DATA_DIR = "data/conversations"
NEW_DATA_DIR = "data/users"
BACKUP_DIR = "data/backup_pre_migration"


def backup_existing():
    """Create backup of existing data."""
    if os.path.exists(OLD_DATA_DIR):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{BACKUP_DIR}_{timestamp}"
        shutil.copytree(OLD_DATA_DIR, backup_path)
        print(f"✓ Backup created at: {backup_path}")
        return backup_path
    return None


def count_conversations():
    """Count existing conversations."""
    if not os.path.exists(OLD_DATA_DIR):
        return 0
    return len([f for f in os.listdir(OLD_DATA_DIR) if f.endswith('.json')])


def migrate_conversations(
    default_user_id: str,
    user_type: str = "employee",  # User type for the target user
    dry_run: bool = False
):
    """
    Migrate all conversations to the specified user.

    Args:
        default_user_id: WorkOS user ID to assign conversations to
        user_type: Type of user (employee, external_partner, guest, service_account)
        dry_run: If True, don't make any changes, just show what would happen
    """
    if not os.path.exists(OLD_DATA_DIR):
        print("No existing conversations to migrate.")
        return

    # Create user directory
    user_conv_dir = os.path.join(NEW_DATA_DIR, default_user_id, "conversations")

    if not dry_run:
        Path(user_conv_dir).mkdir(parents=True, exist_ok=True)

        # Also create a profile.json for the user
        profile_path = os.path.join(NEW_DATA_DIR, default_user_id, "profile.json")
        if not os.path.exists(profile_path):
            profile = {
                "user_id": default_user_id,
                "user_type": user_type,
                "created_at": datetime.utcnow().isoformat(),
                "migrated_from_legacy": True,
            }
            with open(profile_path, 'w') as f:
                json.dump(profile, f, indent=2)
            print(f"✓ Created user profile: {profile_path}")

    migrated = 0
    errors = []

    for filename in os.listdir(OLD_DATA_DIR):
        if not filename.endswith('.json'):
            continue

        old_path = os.path.join(OLD_DATA_DIR, filename)
        new_path = os.path.join(user_conv_dir, filename)

        try:
            # Read existing conversation
            with open(old_path, 'r') as f:
                conversation = json.load(f)

            # Add new fields for user-scoped storage
            conversation['user_id'] = default_user_id
            conversation['user_type'] = user_type  # Track original owner's type
            conversation['updated_at'] = conversation.get(
                'updated_at',
                conversation.get('created_at', datetime.utcnow().isoformat())
            )
            conversation['sharing'] = {
                'is_public': False,
                'shared_with': [],
                # Employees can share, others cannot by default
                'shareable': user_type == 'employee',
            }
            conversation['metadata'] = conversation.get('metadata', {})
            conversation['metadata']['migrated_from_legacy'] = True
            conversation['metadata']['migration_date'] = datetime.utcnow().isoformat()

            if dry_run:
                print(f"  [DRY RUN] Would migrate: {filename}")
            else:
                # Save to new location
                with open(new_path, 'w') as f:
                    json.dump(conversation, f, indent=2)
                print(f"  ✓ Migrated: {filename}")

            migrated += 1

        except Exception as e:
            errors.append((filename, str(e)))
            print(f"  ✗ Error migrating {filename}: {e}")

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Migration complete!")
    print(f"  Migrated: {migrated} conversations")
    print(f"  Errors: {len(errors)}")
    print(f"  User Type: {user_type}")

    if not dry_run and migrated > 0:
        print(f"\nConversations moved to: {user_conv_dir}")
        print(f"You can now safely remove: {OLD_DATA_DIR}")

    return migrated, errors


def main():
    parser = argparse.ArgumentParser(
        description="Migrate conversations to user-scoped storage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be migrated
  python -m scripts.migrate_conversations --default-user user_2abc123 --dry-run

  # Actual migration (default: employee user type)
  python -m scripts.migrate_conversations --default-user user_2abc123

  # Specify user type explicitly
  python -m scripts.migrate_conversations --default-user user_2abc123 --user-type employee

  # Skip backup (not recommended)
  python -m scripts.migrate_conversations --default-user user_2abc123 --no-backup

User Types:
  employee         - Internal organization employees (can share, full access)
  external_partner - Trusted external collaborators (limited sharing)
  guest            - Temporary access users (view-only)
  service_account  - API integrations (programmatic access)
        """
    )
    parser.add_argument(
        "--default-user",
        required=True,
        help="WorkOS user ID to assign all existing conversations to"
    )
    parser.add_argument(
        "--user-type",
        choices=["employee", "external_partner", "guest", "service_account"],
        default="employee",
        help="User type for the target user (default: employee)"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backup (not recommended)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Eternal Copilot - Conversation Migration")
    print("=" * 60)

    count = count_conversations()
    print(f"\nFound {count} conversations to migrate")

    if count == 0:
        print("Nothing to do!")
        return

    print(f"Target user: {args.default_user}")
    print(f"User type: {args.user_type}")

    if args.dry_run:
        print("\n[DRY RUN MODE - No changes will be made]\n")
    else:
        if not args.no_backup:
            print("\nCreating backup...")
            backup_existing()
        else:
            print("\n⚠️  Skipping backup (--no-backup flag)")

    print("\nMigrating conversations...")
    migrate_conversations(
        args.default_user,
        user_type=args.user_type,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
```

### 4.2 Migration Steps

1. **Deploy authentication code** without modifying storage paths
2. **Have admin (employee) sign in** with Microsoft SSO to get their WorkOS user ID
   - Find the user ID in WorkOS Dashboard → User Management → Users → Select user → Copy ID
   - Format: `user_01abc123...`
   - **Important**: Use an employee account so migrated conversations have full capabilities
3. **Run dry-run first**:
   ```bash
   python -m scripts.migrate_conversations --default-user user_2abc123 --user-type employee --dry-run
   ```
4. **Run actual migration**:
   ```bash
   python -m scripts.migrate_conversations --default-user user_2abc123 --user-type employee
   ```
5. **Enable new storage** - Update storage imports to use user-scoped functions
6. **Verify** - Admin employee should see all migrated conversations in their account
7. **Verify user_type** - Check that conversations have `user_type: employee` in their JSON
8. **Clean up** - After verification, remove old `data/conversations/` directory

---

## 5. WorkOS Configuration for Multi-Auth

This section covers configuring WorkOS to support multiple authentication methods for different user types, with Microsoft SSO as the primary method for employees.

### 5.1 Create WorkOS Account and Application

1. Go to [workos.com](https://workos.com) and sign up/log in
2. Create a new environment (Development first, Production later)
3. Note your credentials from the dashboard:
   - **API Key**: `sk_test_xxxxx` (for backend)
   - **Client ID**: `client_xxxxx` (for frontend AuthKit)
4. Configure your redirect URI:
   - Development: `http://localhost:5173/callback`
   - Production: `https://your-app.com/callback`

### 5.2 Authentication Methods by User Type

WorkOS supports multiple authentication methods through AuthKit:

| Auth Method | User Type | Configuration Location |
|-------------|-----------|------------------------|
| Microsoft SSO (Azure AD) | `employee` | SSO → Connections → Microsoft Azure AD |
| Google OAuth | `external_partner` | Authentication → OAuth Providers |
| Email + Password | `external_partner` | Authentication → Password |
| Magic Auth (Email Link) | `guest` | Authentication → Magic Auth |
| API Keys | `service_account` | Backend-only (custom implementation) |

### 5.3 Configure Microsoft SSO (Employees)

#### Step 1: Azure AD App Registration

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory → App Registrations**
3. Click **New Registration**:
   - **Name**: "Eternal Copilot - WorkOS"
   - **Supported account types**: "Accounts in this organizational directory only" (single tenant)
   - **Redirect URI**:
     - Type: Web
     - URL: `https://api.workos.com/sso/callback/<connection_id>`
     - (Get exact URL from WorkOS Dashboard after creating SSO connection)

4. After creation, note the **Application (client) ID** and **Directory (tenant) ID**

5. Go to **Certificates & secrets**:
   - Click **New client secret**
   - Description: "WorkOS Integration"
   - Expiry: Choose appropriate duration
   - **Copy the secret value immediately** (shown only once)

6. Go to **API permissions**:
   - Click **Add a permission**
   - Select **Microsoft Graph**
   - Select **Delegated permissions**
   - Add these permissions:
     - `openid`
     - `email`
     - `profile`
     - `User.Read`
   - Click **Grant admin consent** (if you have admin rights)

#### Step 2: Configure in WorkOS

1. In WorkOS Dashboard, go to **SSO → Connections**
2. Click **Create Connection**
3. Select **Microsoft Azure AD**
4. Configure:
   - **Connection Name**: "Eternal SSO"
   - **Client ID**: Application (client) ID from Azure
   - **Client Secret**: Secret value from Azure
   - **Azure Tenant ID**: Your directory (tenant) ID
5. Copy the **Redirect URI** and add it to your Azure AD app
6. Save and test the connection

### 5.4 Configure Google OAuth (External Partners)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing
3. Navigate to **APIs & Services → Credentials**
4. Click **Create Credentials → OAuth client ID**
5. Configure:
   - Application type: Web application
   - Authorized redirect URIs: `https://authkit.workos.com/callback`

6. In WorkOS Dashboard:
   - Go to **Authentication → OAuth Providers**
   - Enable **Google**
   - Enter Client ID and Client Secret from Google

### 5.5 Configure Email/Password Authentication

1. In WorkOS Dashboard, go to **Authentication**
2. Enable **Password** authentication
3. Configure password policy:
   - Minimum length: 8 characters (WorkOS default)
   - WorkOS handles password hashing and security automatically

### 5.6 Configure Magic Auth (Guests)

1. In WorkOS Dashboard, go to **Authentication**
2. Enable **Magic Auth** (passwordless email links)
3. Configure:
   - Link expiry: Default is 15 minutes
   - Customize email template if needed

### 5.7 Frontend AuthKit Configuration

WorkOS AuthKit provides a hosted authentication UI. Configure the sign-in flow:

```jsx
// frontend/src/components/AuthGuard.jsx

import { useAuth } from '@workos-inc/authkit-react'

export function AuthGuard({ children }) {
  const { isLoading, user, signIn } = useAuth()

  if (isLoading) {
    return <div className="flex h-screen items-center justify-center">Loading...</div>
  }

  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-muted/30">
        <div className="w-full max-w-md text-center">
          <h1 className="text-2xl font-bold mb-4">Eternal Copilot</h1>
          <p className="text-muted-foreground mb-6">
            Sign in to continue
          </p>
          <button
            onClick={() => signIn()}
            className="px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
          >
            Sign In
          </button>
          <p className="text-sm text-muted-foreground mt-4">
            Employees: Sign in with Microsoft<br/>
            Partners: Use Google or email/password
          </p>
        </div>
      </div>
    )
  }

  return children
}
```

### 5.8 Custom Sign-In Options with AuthKit

WorkOS AuthKit allows customizing authentication options via URL parameters:

```jsx
// frontend/src/pages/EmployeeSignIn.jsx
import { useAuth } from '@workos-inc/authkit-react'

export default function EmployeeSignIn() {
  const { signIn } = useAuth()

  // Redirect directly to Microsoft SSO
  const handleSignIn = () => {
    signIn({
      // Use connection ID for your Microsoft SSO connection
      connection: 'conn_xxxxx', // Your WorkOS SSO connection ID
    })
  }

  return (
    <div className="text-center">
      <h2 className="text-xl font-bold mb-4">Employee Sign In</h2>
      <button
        onClick={handleSignIn}
        className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
      >
        <svg className="w-5 h-5" viewBox="0 0 21 21">
          <path fill="currentColor" d="M0 0h10v10H0zm11 0h10v10H11zM0 11h10v10H0zm11 0h10v10H11z"/>
        </svg>
        Sign in with Microsoft
      </button>
    </div>
  )
}

// frontend/src/pages/PartnerSignIn.jsx
import { useAuth } from '@workos-inc/authkit-react'

export default function PartnerSignIn() {
  const { signIn } = useAuth()

  return (
    <div className="text-center">
      <h2 className="text-xl font-bold mb-4">Partner Sign In</h2>
      <div className="space-y-3">
        <button
          onClick={() => signIn({ provider: 'GoogleOAuth' })}
          className="w-full px-6 py-3 bg-white border rounded-lg hover:bg-gray-50"
        >
          Sign in with Google
        </button>
        <button
          onClick={() => signIn()}
          className="w-full px-6 py-3 bg-gray-900 text-white rounded-lg hover:bg-gray-800"
        >
          Sign in with Email
        </button>
      </div>
    </div>
  )
}

// frontend/src/pages/GuestAccess.jsx
import { useAuth } from '@workos-inc/authkit-react'

export default function GuestAccess() {
  const { signIn } = useAuth()

  return (
    <div className="text-center">
      <h2 className="text-xl font-bold mb-4">Guest Access</h2>
      <p className="text-muted-foreground mb-4">
        Enter your email to receive a magic link
      </p>
      <button
        onClick={() => signIn({ screenHint: 'sign-up' })}
        className="px-6 py-3 bg-primary text-primary-foreground rounded-lg"
      >
        Continue with Email
      </button>
    </div>
  )
}
```

### 5.9 Environment Variables

**Backend `.env`**:
```env
# Existing
OPENROUTER_API_KEY=sk-or-v1-xxxxx

# WorkOS Authentication
WORKOS_API_KEY=sk_test_xxxxx
WORKOS_CLIENT_ID=client_xxxxx

# User Type Configuration
EMPLOYEE_EMAIL_DOMAIN=eternal.ag
# ALLOWED_PARTNER_DOMAINS=partner1.com,partner2.com  # Add partner domains as needed
```

**Frontend `.env`**:
```env
VITE_WORKOS_CLIENT_ID=client_xxxxx
VITE_WORKOS_REDIRECT_URI=http://localhost:5173/callback
VITE_EMPLOYEE_EMAIL_DOMAIN=eternal.ag
```

**Production (Vercel)**:
Add all environment variables in Vercel Dashboard → Settings → Environment Variables:
- `WORKOS_API_KEY`
- `WORKOS_CLIENT_ID`
- `VITE_WORKOS_CLIENT_ID`
- `VITE_WORKOS_REDIRECT_URI` (set to production callback URL)
- `EMPLOYEE_EMAIL_DOMAIN`
- `ALLOWED_PARTNER_DOMAINS`

### 5.10 WorkOS SSO Connection IDs

For enterprise SSO, you'll need connection IDs to direct users to specific identity providers:

1. WorkOS Dashboard → SSO → Connections
2. Each connection has a unique ID (e.g., `conn_xxxxx`)
3. Use in frontend: `signIn({ connection: 'conn_xxxxx' })`

### 5.11 Webhook for User Type Assignment

Set up a WorkOS webhook to automatically assign user types on signup:

```python
# backend/webhooks.py

from fastapi import APIRouter, Request, HTTPException
from workos import WorkOSClient
from .user_types import UserType
from .config import WORKOS_API_KEY
import os
import hmac
import hashlib

router = APIRouter()

EMPLOYEE_EMAIL_DOMAIN = os.getenv("EMPLOYEE_EMAIL_DOMAIN", "eternal.ag")
ALLOWED_PARTNER_DOMAINS = os.getenv("ALLOWED_PARTNER_DOMAINS", "").split(",")

# Webhook secret is REQUIRED - use a known development value for local testing
# In production, this should be set to the actual secret from WorkOS Dashboard
# NEVER skip signature verification, even in development
WORKOS_WEBHOOK_SECRET = os.getenv("WORKOS_WEBHOOK_SECRET", "dev_webhook_secret_change_in_production")


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify WorkOS webhook signature using HMAC-SHA256.

    SECURITY: This function ALWAYS verifies signatures. In development,
    use the default secret 'dev_webhook_secret_change_in_production' and
    configure the same value in your local webhook testing tool (e.g., ngrok).

    For production, set WORKOS_WEBHOOK_SECRET to the actual secret from
    WorkOS Dashboard → Webhooks → Signing Secret.
    """
    if not WORKOS_WEBHOOK_SECRET:
        # This should never happen with the default value, but fail-safe
        raise ValueError("WORKOS_WEBHOOK_SECRET is required for webhook verification")

    if not signature:
        return False

    expected = hmac.new(
        WORKOS_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)


@router.post("/api/webhooks/workos")
async def workos_webhook(request: Request):
    """
    Handle WorkOS user.created webhook to assign user_type.

    Configure in WorkOS Dashboard → Webhooks:
    - Endpoint URL: https://your-app.com/api/webhooks/workos
    - Events: user.created, authentication.email_verification_succeeded
    """
    payload = await request.body()
    signature = request.headers.get("WorkOS-Signature", "")

    if not verify_webhook_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    data = await request.json()
    event_type = data.get("event")
    event_data = data.get("data", {})

    if event_type == "user.created":
        user_id = event_data.get("id")
        email = event_data.get("email", "")
        email_domain = email.split("@")[-1] if "@" in email else ""

        # Determine user type based on email domain
        # Note: Auth method comes from separate authentication events
        user_type = determine_user_type_from_email(email_domain)
        default_role = get_default_role(user_type)

        # Update user metadata in WorkOS
        workos = WorkOSClient(api_key=WORKOS_API_KEY)
        workos.user_management.update_user(
            user_id=user_id,
            metadata={
                "user_type": user_type.value,
                "role": default_role,
                "email_domain": email_domain,
            }
        )

        return {"status": "user_type_assigned", "user_type": user_type.value}

    if event_type == "authentication.email_verification_succeeded":
        # User completed email verification
        user_id = event_data.get("user_id")
        # Could update user_type or trigger welcome email
        return {"status": "email_verified"}

    return {"status": "ignored"}


def determine_user_type_from_email(email_domain: str) -> UserType:
    """Determine user type based on email domain."""
    # Employees: Company domain
    if email_domain == EMPLOYEE_EMAIL_DOMAIN:
        return UserType.EMPLOYEE

    # Partners: On allow-list
    if email_domain in ALLOWED_PARTNER_DOMAINS:
        return UserType.EXTERNAL_PARTNER

    # Default to guest
    return UserType.GUEST


def get_default_role(user_type: UserType) -> str:
    """Get default role for user type."""
    return {
        UserType.EMPLOYEE: "user",
        UserType.EXTERNAL_PARTNER: "user",
        UserType.GUEST: "viewer",
        UserType.SERVICE_ACCOUNT: "service",
    }.get(user_type, "viewer")
```

---

## 6. Conversation Sharing Architecture

### 6.1 Sharing Model

```python
# In backend/models.py (new file)

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


class SharePermission(str, Enum):
    VIEW = "view"      # Can read conversation
    EDIT = "edit"      # Can add messages
    ADMIN = "admin"    # Can manage sharing, delete


@dataclass
class ConversationShare:
    """Represents a share grant for a conversation."""
    id: str
    user_id: Optional[str] = None       # WorkOS user ID (if registered)
    email: Optional[str] = None         # Email (if not yet registered)
    permission: SharePermission = SharePermission.VIEW
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    created_by: str = ""                # Who shared it
    expires_at: Optional[str] = None    # Optional expiry


@dataclass
class ConversationSharing:
    """Sharing configuration for a conversation."""
    is_public: bool = False
    public_permission: SharePermission = SharePermission.VIEW
    shared_with: List[ConversationShare] = field(default_factory=list)

    def can_view(self, user_id: str, user_email: str) -> bool:
        """Check if user can view the conversation."""
        if self.is_public:
            return True
        return self._has_permission(user_id, user_email,
                                    SharePermission.VIEW,
                                    SharePermission.EDIT,
                                    SharePermission.ADMIN)

    def can_edit(self, user_id: str, user_email: str) -> bool:
        """Check if user can edit (add messages to) the conversation."""
        return self._has_permission(user_id, user_email,
                                    SharePermission.EDIT,
                                    SharePermission.ADMIN)

    def can_admin(self, user_id: str, user_email: str) -> bool:
        """Check if user can manage sharing settings."""
        return self._has_permission(user_id, user_email,
                                    SharePermission.ADMIN)

    def _has_permission(self, user_id: str, user_email: str, *permissions) -> bool:
        """Check if user has any of the specified permissions."""
        for share in self.shared_with:
            # Check expiry
            if share.expires_at:
                if datetime.fromisoformat(share.expires_at) < datetime.utcnow():
                    continue  # Expired

            # Match by user ID or email
            if share.user_id == user_id or share.email == user_email:
                if share.permission in permissions:
                    return True
        return False
```

### 6.2 Sharing Storage Functions

```python
# Add to backend/storage.py

import uuid


def add_conversation_share(
    conversation_id: str,
    owner_id: str,
    email: str,
    permission: str,
    created_by: str,
    expires_at: Optional[str] = None
) -> Dict[str, Any]:
    """Add a share to a conversation."""
    conversation = get_conversation(conversation_id, owner_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    share = {
        "id": str(uuid.uuid4()),
        "email": email,
        "user_id": None,  # Will be populated when user signs up
        "permission": permission,
        "created_by": created_by,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": expires_at,
    }

    # Initialize sharing if not present
    if "sharing" not in conversation:
        conversation["sharing"] = {"is_public": False, "shared_with": []}

    # Remove existing share for same email
    conversation["sharing"]["shared_with"] = [
        s for s in conversation["sharing"]["shared_with"]
        if s.get("email") != email
    ]

    # Add new share
    conversation["sharing"]["shared_with"].append(share)

    save_conversation(conversation, owner_id)
    return share


def remove_conversation_share(
    conversation_id: str,
    owner_id: str,
    share_id: str
) -> bool:
    """Remove a share from a conversation."""
    conversation = get_conversation(conversation_id, owner_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    original_count = len(conversation.get("sharing", {}).get("shared_with", []))
    conversation["sharing"]["shared_with"] = [
        s for s in conversation["sharing"]["shared_with"]
        if s.get("id") != share_id
    ]

    if len(conversation["sharing"]["shared_with"]) < original_count:
        save_conversation(conversation, owner_id)
        return True
    return False


def list_shared_conversations(user_id: str, user_email: str) -> List[Dict[str, Any]]:
    """List conversations shared with a user."""
    shared = []
    users_dir = os.path.join(DATA_DIR, "users")

    if not os.path.exists(users_dir):
        return shared

    # Scan all users' conversations
    for owner_id in os.listdir(users_dir):
        if owner_id == user_id:
            continue  # Skip own conversations

        conv_dir = os.path.join(users_dir, owner_id, "conversations")
        if not os.path.exists(conv_dir):
            continue

        for filename in os.listdir(conv_dir):
            if not filename.endswith('.json'):
                continue

            path = os.path.join(conv_dir, filename)
            with open(path, 'r') as f:
                conversation = json.load(f)

            sharing = conversation.get("sharing", {})

            # Check if shared with this user
            for share in sharing.get("shared_with", []):
                if share.get("user_id") == user_id or share.get("email") == user_email:
                    shared.append({
                        "id": conversation["id"],
                        "title": conversation.get("title", "New Conversation"),
                        "created_at": conversation["created_at"],
                        "message_count": len(conversation["messages"]),
                        "permission": share.get("permission", "view"),
                        "shared_by": owner_id,
                        "is_owner": False,
                    })
                    break

    shared.sort(key=lambda x: x["created_at"], reverse=True)
    return shared
```

### 6.3 Sharing API Endpoints

```python
# Add to backend/main.py

class ShareRequest(BaseModel):
    """Request to share a conversation."""
    email: str
    permission: str = "view"  # "view", "edit", "admin"
    expires_in_days: Optional[int] = None


class ShareResponse(BaseModel):
    """Response for share operations."""
    id: str
    email: str
    permission: str
    created_at: str
    expires_at: Optional[str]


@app.post("/api/conversations/{conversation_id}/share")
async def share_conversation(
    conversation_id: str,
    request: ShareRequest,
    user: AuthenticatedUser = Depends(get_current_user)
) -> ShareResponse:
    """Share a conversation with another user."""
    conversation = storage.get_conversation(conversation_id, user.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Only owner can share
    if conversation.get("user_id") != user.id:
        raise HTTPException(status_code=403, detail="Only owner can share")

    # Validate permission
    if request.permission not in ["view", "edit", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid permission")

    # Calculate expiry
    expires_at = None
    if request.expires_in_days:
        expires_at = (
            datetime.utcnow() + timedelta(days=request.expires_in_days)
        ).isoformat()

    share = storage.add_conversation_share(
        conversation_id=conversation_id,
        owner_id=user.id,
        email=request.email,
        permission=request.permission,
        created_by=user.id,
        expires_at=expires_at
    )

    return ShareResponse(**share)


@app.get("/api/conversations/{conversation_id}/shares")
async def list_conversation_shares(
    conversation_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
) -> List[ShareResponse]:
    """List all shares for a conversation."""
    conversation = storage.get_conversation(conversation_id, user.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation.get("user_id") != user.id:
        raise HTTPException(status_code=403, detail="Only owner can view shares")

    shares = conversation.get("sharing", {}).get("shared_with", [])
    return [ShareResponse(**s) for s in shares]


@app.delete("/api/conversations/{conversation_id}/shares/{share_id}")
async def revoke_share(
    conversation_id: str,
    share_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Revoke a conversation share."""
    conversation = storage.get_conversation(conversation_id, user.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation.get("user_id") != user.id:
        raise HTTPException(status_code=403, detail="Only owner can revoke shares")

    removed = storage.remove_conversation_share(conversation_id, user.id, share_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Share not found")

    return {"status": "revoked"}


@app.get("/api/shared-with-me")
async def list_shared_with_me(
    user: AuthenticatedUser = Depends(get_current_user)
):
    """List conversations shared with the current user."""
    return storage.list_shared_conversations(user.id, user.email)
```

---

## 7. Role-Based Access Control (RBAC)

### 7.1 Role Definitions

| Role | Capabilities |
|------|-------------|
| **admin** | Full access, manage users, view all conversations (for support), configure system settings |
| **user** | Create conversations, share conversations, use Eternal Copilot features |
| **viewer** | View shared conversations only, cannot create new ones |
| **service** | Programmatic API access, limited to specific operations |

### 7.2 User Type × Role Matrix

Not all roles are available to all user types. This matrix defines allowed combinations:

| User Type | Allowed Roles | Default Role | Notes |
|-----------|---------------|--------------|-------|
| `employee` | admin, user, viewer | user | Only employees can be admins |
| `external_partner` | user, viewer | user | Cannot be admin |
| `guest` | viewer | viewer | View-only access |
| `service_account` | service | service | API access only |

```python
# backend/rbac.py

from .user_types import UserType

# Define which roles are allowed for each user type
ALLOWED_ROLES_BY_TYPE: dict[UserType, set[str]] = {
    UserType.EMPLOYEE: {"admin", "user", "viewer"},
    UserType.EXTERNAL_PARTNER: {"user", "viewer"},
    UserType.GUEST: {"viewer"},
    UserType.SERVICE_ACCOUNT: {"service"},
}

DEFAULT_ROLE_BY_TYPE: dict[UserType, str] = {
    UserType.EMPLOYEE: "user",
    UserType.EXTERNAL_PARTNER: "user",
    UserType.GUEST: "viewer",
    UserType.SERVICE_ACCOUNT: "service",
}


def is_role_allowed(user_type: UserType, role: str) -> bool:
    """Check if a role is allowed for a user type."""
    allowed = ALLOWED_ROLES_BY_TYPE.get(user_type, set())
    return role in allowed


def get_effective_role(user_type: UserType, requested_role: str) -> str:
    """
    Get the effective role, clamping to allowed roles for the user type.
    If requested role is not allowed, return the default for that type.
    """
    if is_role_allowed(user_type, requested_role):
        return requested_role
    return DEFAULT_ROLE_BY_TYPE.get(user_type, "viewer")
```

### 7.3 Permission Matrix

Detailed permission matrix by user type and role:

| Permission | employee:admin | employee:user | partner:user | guest:viewer | service |
|------------|----------------|---------------|--------------|--------------|---------|
| Create conversations | ✅ | ✅ | ✅ (limited) | ❌ | ✅ |
| View own conversations | ✅ | ✅ | ✅ | N/A | ✅ |
| View shared conversations | ✅ | ✅ | ✅ | ✅ | ❌ |
| Share conversations | ✅ | ✅ | ❌ | ❌ | ❌ |
| Use Eternal Copilot | ✅ | ✅ | ✅ | ❌ | ✅ |
| View all conversations | ✅ | ❌ | ❌ | ❌ | ❌ |
| Manage users | ✅ | ❌ | ❌ | ❌ | ❌ |
| Invite users | ✅ | ✅ | ❌ | ❌ | ❌ |
| View analytics | ✅ | ✅ | ❌ | ❌ | ✅ |
| API access | ✅ | ✅ | ✅ | ❌ | ✅ |

### 7.4 Setting Roles in WorkOS

Roles and user types are stored in WorkOS user metadata. There are several ways to set them:

#### Option A: WorkOS Dashboard (Manual)

1. Go to WorkOS Dashboard → User Management → Users
2. Select the user
3. Click **Edit Metadata**
4. Add JSON: `{"user_type": "employee", "role": "admin"}`
5. Save

#### Option B: WorkOS Python SDK (Programmatic)

```python
# backend/workos_admin.py

from workos import WorkOSClient
from .config import WORKOS_API_KEY
from .user_types import UserType
from .rbac import is_role_allowed, get_effective_role


def get_workos_client() -> WorkOSClient:
    """Get WorkOS client instance."""
    return WorkOSClient(api_key=WORKOS_API_KEY)


async def set_user_metadata(user_id: str, metadata: dict) -> bool:
    """Set user's metadata in WorkOS."""
    try:
        workos = get_workos_client()
        workos.user_management.update_user(
            user_id=user_id,
            metadata=metadata
        )
        return True
    except Exception as e:
        print(f"Error setting user metadata: {e}")
        return False


async def set_user_role(user_id: str, role: str, user_type: str = None) -> bool:
    """
    Set a user's role in WorkOS metadata.
    Validates that the role is allowed for the user's type.
    """
    # Get current metadata to check user_type
    current = await get_user_metadata(user_id)
    current_type = user_type or current.get("user_type", "guest")

    # Validate role is allowed
    type_enum = UserType(current_type)
    effective_role = get_effective_role(type_enum, role)

    if effective_role != role:
        print(f"Warning: Role '{role}' not allowed for {current_type}, using '{effective_role}'")

    return await set_user_metadata(user_id, {
        **current,
        "role": effective_role
    })


async def get_user_metadata(user_id: str) -> dict:
    """Get a user's metadata from WorkOS."""
    try:
        workos = get_workos_client()
        user = workos.user_management.get_user(user_id=user_id)
        return user.metadata or {}
    except Exception:
        return {}
```

#### Option C: WorkOS Webhooks (Automatic)

Set up a webhook to automatically assign roles when users sign up:

```python
# Add to backend/main.py

from fastapi import Request
import hmac
import hashlib

WORKOS_WEBHOOK_SECRET = os.getenv("WORKOS_WEBHOOK_SECRET")


def verify_workos_webhook(payload: bytes, signature: str) -> bool:
    """Verify WorkOS webhook signature."""
    if not WORKOS_WEBHOOK_SECRET:
        return True  # Skip in development
    expected = hmac.new(
        WORKOS_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


@app.post("/api/webhooks/workos")
async def workos_webhook(request: Request):
    """Handle WorkOS webhooks for user events."""
    body = await request.body()

    # Verify webhook signature
    signature = request.headers.get("WorkOS-Signature", "")
    if not verify_workos_webhook(body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    data = await request.json()
    event_type = data.get("event")

    if event_type == "user.created":
        user_data = data.get("data", {})
        user_id = user_data.get("id")
        email = user_data.get("email", "")

        # Auto-assign roles based on email domain
        if email.endswith("@eternal.ag"):
            await set_user_role(user_id, "user")
        else:
            await set_user_role(user_id, "viewer")

    return {"received": True}
```

### 7.3 Using Roles in Endpoints

```python
# backend/main.py examples

from .auth import get_current_user, require_role, AuthenticatedUser


# Any authenticated user can access
@app.get("/api/conversations")
async def list_conversations(
    user: AuthenticatedUser = Depends(get_current_user)
):
    return storage.list_conversations(user.id)


# Only admins can access
@app.get("/api/admin/users")
async def list_all_users(
    user: AuthenticatedUser = Depends(require_role("admin"))
):
    # List all users (admin functionality)
    pass


# Only admins and regular users can create (not viewers)
@app.post("/api/conversations")
async def create_conversation(
    user: AuthenticatedUser = Depends(require_role("admin", "user"))
):
    # Viewers cannot create conversations
    pass


# Check role within endpoint logic
@app.get("/api/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user: AuthenticatedUser = Depends(get_current_user)
):
    conversation = storage.get_conversation(conversation_id, user.id)

    if conversation is None:
        # Admins can view any conversation for support
        if user.is_admin():
            conversation = storage.get_any_conversation(conversation_id)

        if conversation is None:
            raise HTTPException(status_code=404, detail="Not found")

    return conversation
```

### 7.4 Frontend Role Checks

```jsx
// frontend/src/components/AuthGuard.jsx

export function useCurrentUser() {
  const { user } = useUser()
  return {
    id: user?.id,
    email: user?.primaryEmailAddress?.emailAddress,
    name: user?.fullName,
    imageUrl: user?.imageUrl,
    role: user?.publicMetadata?.role || 'user',

    // Helper methods
    isAdmin: () => user?.publicMetadata?.role === 'admin',
    canCreate: () => ['admin', 'user'].includes(user?.publicMetadata?.role || 'user'),
    canShare: () => ['admin', 'user'].includes(user?.publicMetadata?.role || 'user'),
  }
}


// Usage in components
function Sidebar({ onNewConversation }) {
  const { canCreate } = useCurrentUser();

  return (
    <div>
      {canCreate() && (
        <Button onClick={onNewConversation}>
          New Conversation
        </Button>
      )}
      {/* ... */}
    </div>
  );
}
```

---

## 8. Implementation Phases

### Phase 1: Basic Authentication - Employees Only (Week 1)

Focus on getting Microsoft SSO working for employees first, with essential security measures.

**Authentication Setup:**
- [ ] Create WorkOS account at workos.com
- [ ] Install WorkOS AuthKit in frontend (`npm install @workos-inc/authkit-react react-router-dom`)
- [ ] Install WorkOS Python SDK and dependencies (`pip install workos cachetools slowapi`)
- [ ] Configure redirect URIs in WorkOS Dashboard
- [ ] Set up Azure AD app registration (single-tenant for your org)
- [ ] Create SSO connection in WorkOS Dashboard for Microsoft Azure AD
- [ ] Add AuthKitProvider and BrowserRouter to frontend entry point (`main.jsx`)
- [ ] Create Callback component for OAuth redirect handling
- [ ] Create AuthGuard component with Microsoft SSO emphasis
- [ ] Create UserMenu component with signOut functionality
- [ ] Implement `backend/auth.py` module with WorkOS token verification and caching
- [ ] Implement `backend/user_types.py` module
- [ ] Add auth dependencies to all API endpoints
- [ ] Update frontend API client with auth headers and 401 retry logic
- [ ] Test employee authentication flow end-to-end
- [ ] Update environment variables documentation
- [ ] Set up `EMPLOYEE_EMAIL_DOMAIN` configuration

**Rate Limiting (Required for Production):**
- [ ] Install slowapi: `pip install slowapi`
- [ ] Configure rate limiter in `backend/main.py`:
  ```python
  from slowapi import Limiter, _rate_limit_exceeded_handler
  from slowapi.util import get_remote_address
  from slowapi.errors import RateLimitExceeded

  limiter = Limiter(key_func=get_remote_address)
  app.state.limiter = limiter
  app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
  ```
- [ ] Add rate limits to authentication endpoints:
  - `/api/conversations` POST: 10/minute (prevent conversation spam)
  - `/api/conversations/{id}/message` POST: 10/minute (prevent message spam)
  - `/api/improve-prompt` POST: 5/minute (expensive LLM operation)
- [ ] Add user-based rate limiting (use user ID from token instead of IP for authenticated requests)
- [ ] Test rate limiting behavior

**Token Caching:**
- [ ] Verify `cachetools` is installed
- [ ] Configure TTL cache in `backend/auth.py` (45-second TTL, 1000 max entries)
- [ ] Test cache behavior under load

### Phase 2: User-Scoped Storage (Week 2)

- [ ] Update `backend/storage.py` for user-scoped paths
- [ ] Update all storage function signatures with `user_id` parameter
- [ ] Update all API endpoints to pass user context to storage
- [ ] Create migration script (`scripts/migrate_conversations.py`)
- [ ] Add `user_type` field to migrated conversations
- [ ] Test migration script with dry-run
- [ ] Backup existing conversations
- [ ] Run migration for existing conversations (assign to admin employee)
- [ ] Verify user isolation (users can only see their own data)
- [ ] Clean up old storage directory

### Phase 2.5: Database Migration (Week 2-3)

**Why This Phase is Critical:**

The current JSON file storage has O(n) query performance for listing conversations and checking shares. Before implementing conversation sharing (Phase 3), migrating to a proper database is strongly recommended to avoid:

1. **Performance degradation** as user count grows
2. **Complex file locking** for concurrent access
3. **Inefficient queries** for shared conversation lookups
4. **Scaling limitations** for multi-tenancy

**Database Options:**

| Option | Pros | Cons | Recommended For |
|--------|------|------|-----------------|
| **Supabase (PostgreSQL)** | Managed, built-in auth, real-time | Vendor lock-in | Quick setup, small teams |
| **PostgreSQL (self-hosted)** | Full control, no limits | Ops overhead | Enterprise, compliance needs |
| **SQLite** | Simple, no server | Single-writer, limited scale | Development, small deployments |

**Migration Steps:**

- [ ] Choose database solution (Supabase recommended for this project)
- [ ] Create database schema:
  ```sql
  -- Users table (synced from WorkOS)
  CREATE TABLE users (
    id TEXT PRIMARY KEY,  -- WorkOS user ID
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    user_type TEXT NOT NULL DEFAULT 'employee',
    role TEXT NOT NULL DEFAULT 'user',
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
  );

  -- Conversations table
  CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id),
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
  );

  -- Messages table
  CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,  -- 'user' or 'assistant'
    content JSONB NOT NULL,  -- Stores stage1, stage2, stage3 for assistant messages
    created_at TIMESTAMPTZ DEFAULT NOW()
  );

  -- Shares table (for Phase 3)
  CREATE TABLE conversation_shares (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    shared_with_id TEXT NOT NULL REFERENCES users(id),
    permission TEXT NOT NULL DEFAULT 'view',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(conversation_id, shared_with_id)
  );

  -- Indexes for common queries
  CREATE INDEX idx_conversations_owner ON conversations(owner_id);
  CREATE INDEX idx_messages_conversation ON messages(conversation_id);
  CREATE INDEX idx_shares_shared_with ON conversation_shares(shared_with_id);
  ```
- [ ] Create `backend/database.py` module with connection pooling
- [ ] Update `backend/storage.py` to use database instead of JSON files
- [ ] Create data migration script from JSON to database
- [ ] Test migration with production data copy
- [ ] Deploy database changes
- [ ] Run migration in production
- [ ] Verify data integrity
- [ ] Remove JSON file storage code (keep as backup for 30 days)

### Phase 3: Conversation Sharing (Week 3-4)

- [ ] Implement sharing data model
- [ ] Add sharing storage functions
- [ ] Create sharing API endpoints (`/share`, `/shares`, revoke)
- [ ] Implement `list_shared_conversations` function
- [ ] Add `/api/shared-with-me` endpoint
- [ ] Build sharing UI in frontend (share dialog)
- [ ] Implement "Shared with me" section in sidebar
- [ ] Add share permission checks to conversation access
- [ ] Enforce sharing restrictions by user_type (employees only)
- [ ] Test sharing flow with multiple users
- [ ] Add share notifications (optional)

### Phase 4: RBAC & User Type Enforcement (Week 4)

- [ ] Implement `backend/rbac.py` module
- [ ] Create role checking middleware with user_type validation
- [ ] Set up initial admin user (employee only)
- [ ] Add admin-only endpoints
- [ ] Create admin dashboard page
- [ ] Implement role assignment via WorkOS SDK with type validation
- [ ] Set up WorkOS webhooks for automatic user_type assignment
- [ ] Add capability-based permission checks
- [ ] Implement rate limiting by user_type
- [ ] Test user_type × role matrix enforcement

### Phase 5: Multi-User-Type Support (Week 5+)

Enable additional authentication methods for external partners and guests.

- [ ] Enable Google OAuth in WorkOS Dashboard for external partners
- [ ] Enable Password authentication in WorkOS
- [ ] Enable Magic Auth for guest access
- [ ] Create user allow-list management (database table)
- [ ] Implement allow-list check in user.created webhook
- [ ] Create separate sign-in pages/flows by user type
- [ ] Add partner invitation system
- [ ] Implement guest access links (time-limited)
- [ ] Add user type badges in UI
- [ ] Test cross-user-type sharing (employee → partner)
- [ ] Implement usage limits enforcement by user_type

### Phase 6: Multi-tenancy & Organizations (Week 6+)

Optional: For enterprise deployments with multiple organizations.

- [ ] Configure WorkOS Organizations
- [ ] Add organization_id to storage layer
- [ ] Implement organization-level data isolation
- [ ] Add organization admin role
- [ ] Implement organization-level sharing
- [ ] Add organization switching in UI
- [ ] Implement usage analytics per organization
- [ ] Add organization billing integration (optional)

---

## 9. Security Best Practices

### 9.1 Token Validation

- **Always verify access tokens server-side** using WorkOS User Management API
- **Never trust client-provided user IDs** - extract from verified token
- **Handle token expiration gracefully** - WorkOS AuthKit handles refresh automatically
- **Use HTTPS only** in production

### 9.2 Authorization

- **Every endpoint must check permissions** - ownership or share access
- **Validate user owns resource** before modification
- **Use role-based guards** for admin functionality
- **Fail closed** - deny access if uncertain

### 9.3 Data Protection

- **User ID comes from token, not request body**
- **Scope all queries by user ID**
- **Validate conversation ownership** before any operation
- **Audit log sensitive operations** (sharing, deletion)

### 9.4 API Security

```python
# Example: Secure endpoint pattern
@app.post("/api/conversations/{conversation_id}/message")
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    user: AuthenticatedUser = Depends(get_current_user)  # 1. Auth required
):
    # 2. Verify ownership/access
    conversation = storage.get_conversation(conversation_id, user.id)
    if conversation is None:
        raise HTTPException(status_code=404)  # 3. Don't leak info

    # 4. Check write permission for shared conversations
    if conversation.get("user_id") != user.id:
        sharing = conversation.get("sharing", {})
        if not can_edit(sharing, user.id, user.email):
            raise HTTPException(status_code=403)

    # 5. Proceed with authorized operation
    storage.add_user_message(conversation_id, user.id, request.content)
```

### 9.5 CORS Configuration

```python
# Only allow your domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",      # Dev
        "https://yourdomain.com",     # Production
        "https://*.vercel.app",       # Vercel previews (use regex)
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

### 9.6 Rate Limiting

Consider adding rate limiting for API endpoints:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.post("/api/conversations/{conversation_id}/message")
@limiter.limit("10/minute")  # 10 messages per minute
async def send_message(...):
    pass
```

### 9.7 Input Validation

```python
from pydantic import BaseModel, validator, EmailStr


class ShareRequest(BaseModel):
    email: EmailStr  # Validates email format
    permission: str

    @validator('permission')
    def validate_permission(cls, v):
        if v not in ['view', 'edit', 'admin']:
            raise ValueError('Invalid permission')
        return v
```

### 9.8 Pre-Production Security Checklist

Before deploying to production, complete this security checklist:

#### Authentication & Authorization
- [ ] **Webhook signature verification enabled** - `WORKOS_WEBHOOK_SECRET` is set to actual secret from WorkOS Dashboard (not the development default)
- [ ] **Token caching configured** - TTL cache is working with appropriate timeout (30-60 seconds)
- [ ] **Rate limiting active** - All endpoints have appropriate rate limits configured
- [ ] **401 retry logic tested** - Frontend correctly handles token expiration and refresh
- [ ] **Error messages sanitized** - No internal error details exposed to clients

#### HTTP Security Headers
- [ ] **Content Security Policy (CSP)** configured:
  ```python
  # Add to FastAPI middleware
  @app.middleware("http")
  async def add_security_headers(request: Request, call_next):
      response = await call_next(request)
      response.headers["Content-Security-Policy"] = (
          "default-src 'self'; "
          "script-src 'self' 'unsafe-inline'; "
          "style-src 'self' 'unsafe-inline'; "
          "img-src 'self' data: https:; "
          "connect-src 'self' https://api.workos.com https://api.openrouter.ai; "
          "frame-ancestors 'none'; "
          "base-uri 'self';"
      )
      response.headers["X-Content-Type-Options"] = "nosniff"
      response.headers["X-Frame-Options"] = "DENY"
      response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
      return response
  ```
- [ ] **HSTS enabled** (if using HTTPS, which you should be)
- [ ] **X-Content-Type-Options: nosniff** set
- [ ] **X-Frame-Options: DENY** set

#### Audit Logging
- [ ] **Authentication events logged** - Sign-in, sign-out, token refresh failures
- [ ] **Authorization failures logged** - 403 responses with user context
- [ ] **Sensitive operations logged** - Conversation sharing, deletion, admin actions
- [ ] **Log format includes** - Timestamp, user ID, action, resource ID, IP address
- [ ] **Logs do NOT include** - Access tokens, passwords, PII in error messages

Example audit logging setup:
```python
import logging
from datetime import datetime

audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

def log_audit_event(
    action: str,
    user_id: str,
    resource_type: str = None,
    resource_id: str = None,
    details: dict = None,
    ip_address: str = None
):
    audit_logger.info({
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "user_id": user_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "ip_address": ip_address,
        "details": details or {}
    })
```

#### Error Monitoring
- [ ] **Sentry integration configured** (or similar error tracking):
  ```python
  import sentry_sdk
  from sentry_sdk.integrations.fastapi import FastApiIntegration

  sentry_sdk.init(
      dsn=os.getenv("SENTRY_DSN"),
      integrations=[FastApiIntegration()],
      traces_sample_rate=0.1,  # 10% of requests for performance monitoring
      environment=os.getenv("ENVIRONMENT", "development"),
  )
  ```
- [ ] **Error alerts configured** - Critical errors trigger notifications
- [ ] **Performance monitoring enabled** - Slow endpoints are tracked
- [ ] **User context attached to errors** - User ID (not PII) included in error reports

#### CORS Configuration
- [ ] **Production origins configured** - Only your actual domains allowed
- [ ] **Wildcard origins removed** - No `*` in production
- [ ] **Credentials mode correct** - `allow_credentials=True` only with specific origins
- [ ] **Vercel preview URLs handled** - Use regex pattern if needed

#### Environment Variables
- [ ] **All secrets set in production** - No development defaults
- [ ] **Secrets not in code** - All sensitive values from environment
- [ ] **Different secrets per environment** - Dev/staging/prod have unique secrets
- [ ] **Secret rotation plan** - Document how to rotate WorkOS API key, webhook secret

#### Account Security
- [ ] **Account lockout configured** - WorkOS handles this, but verify settings
- [ ] **Session timeout appropriate** - Token expiration matches security requirements
- [ ] **Logout clears all state** - Frontend clears tokens, backend invalidates cache

#### Data Protection
- [ ] **Database backups configured** - If using database (Phase 2.5)
- [ ] **Encryption at rest enabled** - Database and file storage encrypted
- [ ] **PII handling documented** - What data is stored, retention policy
- [ ] **GDPR/privacy compliance** - Data deletion capability exists

#### Testing
- [ ] **Security tests pass** - Authentication bypass attempts fail
- [ ] **Authorization tests pass** - Users cannot access others' data
- [ ] **Rate limiting tests pass** - Limits are enforced correctly
- [ ] **Error handling tests pass** - No stack traces or internal errors exposed

---

## 10. Files to Create/Modify

### New Files to Create

| File | Description |
|------|-------------|
| `frontend/src/components/AuthGuard.jsx` | Protected route wrapper with WorkOS useAuth hook |
| `frontend/src/components/Callback.jsx` | OAuth callback handler for WorkOS redirect |
| `frontend/src/components/UserMenu.jsx` | User avatar and logout button |
| `frontend/src/pages/EmployeeSignIn.jsx` | Employee-specific sign-in (Microsoft SSO) |
| `frontend/src/pages/PartnerSignIn.jsx` | Partner sign-in (Google/email) |
| `frontend/src/pages/GuestAccess.jsx` | Guest access via magic link |
| `backend/auth.py` | WorkOS token verification, user context, user_type detection |
| `backend/user_types.py` | User type enum, capabilities, defaults |
| `backend/rbac.py` | Role-based access control with user_type validation |
| `backend/webhooks.py` | WorkOS webhook handlers for user.created events |
| `backend/workos_admin.py` | WorkOS SDK client for user management |
| `backend/models.py` | Data models for sharing (optional) |
| `scripts/migrate_conversations.py` | Migration script with user_type support |
| `frontend/.env` | Frontend environment variables |

### Files to Modify

| File | Changes |
|------|---------|
| `frontend/src/main.jsx` | Add AuthKitProvider wrapper |
| `frontend/src/App.jsx` | Add AuthGuard wrapper, pass getAccessToken |
| `frontend/src/api.js` | Add auth headers to all requests |
| `frontend/src/components/Sidebar.jsx` | Add UserMenu component, user type badge |
| `frontend/package.json` | Add `@workos-inc/authkit-react` dependency |
| `backend/main.py` | Add auth dependencies, include webhooks router |
| `backend/storage.py` | Add `user_id` and `user_type` parameters |
| `backend/config.py` | Add WorkOS config, employee domain, partner domains |
| `pyproject.toml` | Add `workos` dependency |
| `.env` | Add WorkOS keys, domain config |
| `.env.example` | Document new environment variables |

### Environment Variables Summary

**Frontend (`.env` / Vercel)**:
```env
VITE_WORKOS_CLIENT_ID=client_xxxxx
VITE_WORKOS_REDIRECT_URI=http://localhost:5173/callback
VITE_EMPLOYEE_EMAIL_DOMAIN=eternal.ag
```

**Backend (`.env` / Vercel)**:
```env
# Existing
OPENROUTER_API_KEY=sk-or-v1-xxxxx

# WorkOS Authentication
WORKOS_API_KEY=sk_test_xxxxx
WORKOS_CLIENT_ID=client_xxxxx

# User Type Configuration
EMPLOYEE_EMAIL_DOMAIN=eternal.ag
# ALLOWED_PARTNER_DOMAINS=partner1.com,partner2.com  # Add partner domains as needed

# Optional - Webhooks
WORKOS_WEBHOOK_SECRET=xxxxx
```

---

## Appendix: Quick Start Checklist

### First-Time Setup

1. [ ] Create WorkOS account at workos.com
2. [ ] Create new WorkOS environment (Development)
3. [ ] Set up Azure AD app registration
4. [ ] Create SSO connection in WorkOS for Microsoft Azure AD
5. [ ] Configure redirect URIs in WorkOS Dashboard
6. [ ] Copy environment variables to `.env` files
7. [ ] Install dependencies (`npm install`, `uv sync`)
8. [ ] Start application and test sign-in

### Deployment (Vercel)

1. [ ] Add all environment variables to Vercel
2. [ ] Update CORS origins for production domain
3. [ ] Create WorkOS production environment
4. [ ] Update Azure AD redirect URIs for production
5. [ ] Run migration for any existing data
6. [ ] Test authentication in production

---

## Changelog

### Version 1.3 (December 2024)
- **Token Caching (Section 2.2C)**: Added TTL cache implementation using `cachetools` with 45-second TTL to reduce latency from repeated WorkOS API calls. Includes thread-safe async locking and cache invalidation function.
- **React Router Integration (Section 2.1)**: Added `react-router-dom` installation and configuration for handling OAuth callback route at `/callback`. Updated `main.jsx` with BrowserRouter wrapper and `App.jsx` with Routes configuration.
- **Error Message Sanitization (Section 2.2C)**: Updated `verify_workos_token()` to use generic error messages ("Invalid or expired authentication token") instead of exposing internal error details. Added server-side logging for debugging.
- **Rate Limiting in Phase 1 (Section 8)**: Moved rate limiting implementation to Phase 1 checklist with specific implementation steps using `slowapi`. Added rate limit recommendations for each endpoint type.
- **Database Migration Phase (Section 8)**: Added new "Phase 2.5: Database Migration" between Phase 2 and Phase 3. Includes rationale for database migration before sharing implementation, database options comparison, complete SQL schema, and migration steps.
- **API Client 401 Retry Logic (Section 2.1G)**: Added comprehensive `fetchWithRetry()` function with automatic token refresh on 401 responses. Includes refresh deduplication to prevent multiple simultaneous refresh attempts.
- **Webhook Secret Requirement (Section 5.11)**: Updated `verify_webhook_signature()` to always require a secret. Uses known development default value instead of skipping verification. Added security documentation.
- **Pre-Production Security Checklist (Section 9.8)**: Added comprehensive security checklist covering authentication, HTTP security headers, audit logging, error monitoring (Sentry), CORS configuration, environment variables, account security, data protection, and testing requirements.
- **Dependency Updates (Section 2.2A)**: Added `cachetools>=5.3.0` and `slowapi>=0.1.9` to Python dependencies.
- **Callback Component Enhancement (Section 2.1E)**: Improved error handling with inline error display and retry option instead of redirecting to non-existent error page.

### Version 1.2 (December 2024)
- **Migrated from Clerk to WorkOS** for authentication
- Updated all frontend code to use `@workos-inc/authkit-react` instead of `@clerk/clerk-react`
- Updated backend to use WorkOS Python SDK (`workos>=5.0.0`) instead of PyJWT
- Changed token verification from JWT/JWKS to WorkOS User Management API
- Updated AuthKitProvider configuration and Callback component for OAuth flow
- Updated all environment variables to WorkOS format (`WORKOS_API_KEY`, `WORKOS_CLIENT_ID`)
- Updated SSO configuration instructions for WorkOS Dashboard
- Updated webhook handlers for WorkOS event format
- Updated implementation phases with WorkOS-specific setup steps
- Renamed file from `CLERK.md` to `WORKOS.md`

### Version 1.1 (December 2024)
- Added User Type Classification (Section 1.1)
- Added multi-authentication method support (Microsoft SSO, Google SSO, email/password, magic links)
- Added user type taxonomy: `employee`, `external_partner`, `guest`, `service_account`
- Updated database schema with `user_type` field and allow-list table
- Added User Type × Role matrix in RBAC section
- Added capability-based permission system
- Updated migration script with `--user-type` parameter
- Added Phase 5 (Multi-User-Type Support) and Phase 6 (Multi-tenancy) to implementation plan
- Added webhook handler for automatic user type assignment

### Version 1.0 (December 2024)
- Initial document with Clerk authentication implementation plan
- Microsoft SSO integration for employees
- User-scoped storage architecture
- Conversation sharing with ACL
- Basic RBAC implementation

---

*Last Updated: December 2024*
*Document Version: 1.3*

