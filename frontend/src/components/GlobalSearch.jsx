/**
 * GlobalSearch - A prominent search bar component for the dashboard header.
 *
 * Features:
 * - Typesense-powered full-text search with typo tolerance
 * - User-scoped results (only shows data the user has access to)
 * - Grouped results by source (Conversations, Messages)
 * - Debounced search input (200ms)
 * - Keyboard navigation support
 *
 * Security:
 * - Uses scoped API keys with embedded user_id filter
 * - Keys expire after 1 hour and are refreshed automatically
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useAuth } from '@workos-inc/authkit-react'
import { Search, MessageSquare, MessagesSquare, Loader2 } from 'lucide-react'
import TypesenseInstantSearchAdapter from 'typesense-instantsearch-adapter'

import { cn } from '@/lib/utils'
import { useDebounce } from '@/hooks/use-debounce'
import { api } from '@/api'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
  PopoverAnchor,
} from '@/components/ui/popover'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'

// Cache for Typesense adapter to avoid recreating on every render
let typesenseAdapter = null
let adapterExpiresAt = 0
let adapterUserId = null  // Track which user the adapter was created for

/**
 * Get or create Typesense adapter with scoped search key.
 * Caches the adapter and refreshes when key expires or user changes.
 *
 * @param {string} userId - Current user's ID to ensure cache is valid for this user
 */
async function getTypesenseAdapter(userId) {
  const now = Date.now()

  // Return cached adapter if still valid (with 5 min buffer) AND for the same user
  if (
    typesenseAdapter &&
    adapterExpiresAt > now + 5 * 60 * 1000 &&
    adapterUserId === userId
  ) {
    return typesenseAdapter
  }

  // Fetch new scoped key from backend
  const config = await api.getSearchKey()

  // Create new adapter with scoped key
  typesenseAdapter = new TypesenseInstantSearchAdapter({
    server: {
      apiKey: config.search_key,
      nodes: [{
        host: config.typesense_host,
        port: config.typesense_port,
        protocol: config.typesense_protocol,
      }],
    },
    additionalSearchParameters: {
      query_by: 'title,content,original_query',
      highlight_full_fields: 'title,content',
    },
  })

  // Key expires in 1 hour, set expiry with buffer
  adapterExpiresAt = now + 55 * 60 * 1000
  adapterUserId = userId

  return typesenseAdapter
}

/**
 * Reset the adapter cache. Called when user changes to ensure fresh keys.
 */
function resetAdapterCache() {
  typesenseAdapter = null
  adapterExpiresAt = 0
  adapterUserId = null
}

/**
 * Perform multi-collection search using Typesense.
 *
 * @param {string} query - Search query
 * @param {string} userId - Current user's ID for cache validation
 */
async function performSearch(query, userId) {
  if (!query || query.trim().length < 2) {
    return { conversations: [], messages: [] }
  }

  try {
    const adapter = await getTypesenseAdapter(userId)
    const client = adapter.typesenseClient

    // Multi-search across collections
    const searchRequests = {
      searches: [
        {
          collection: 'conversations',
          q: query,
          query_by: 'title,original_query',
          highlight_full_fields: 'title',
          per_page: 5,
        },
        {
          collection: 'messages',
          q: query,
          query_by: 'content',
          highlight_full_fields: 'content',
          per_page: 5,
        },
      ],
    }

    const results = await client.multiSearch.perform(searchRequests)

    return {
      conversations: results.results[0]?.hits || [],
      messages: results.results[1]?.hits || [],
    }
  } catch (error) {
    // Check for auth errors (expired/invalid key) and reset cache
    const errorStr = String(error.message || error)
    if (errorStr.includes('401') || errorStr.includes('403') || errorStr.includes('Unauthorized')) {
      console.warn('Search key expired or invalid, resetting cache')
      resetAdapterCache()
    }
    console.error('Search error:', error)
    return { conversations: [], messages: [] }
  }
}

export default function GlobalSearch({ onNavigate }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState({ conversations: [], messages: [] })
  const [isLoading, setIsLoading] = useState(false)
  const [isConfigured, setIsConfigured] = useState(null) // null = loading, true/false = result
  const inputRef = useRef(null)
  const { isLoading: isAuthLoading, user } = useAuth()

  const debouncedQuery = useDebounce(query, 200)

  // Reset adapter cache when user changes to ensure fresh scoped keys
  useEffect(() => {
    resetAdapterCache()
  }, [user?.id])

  // Check if search is configured when user is authenticated
  useEffect(() => {
    // Don't check until auth is complete
    if (isAuthLoading) return

    // If not authenticated, search won't work
    if (!user) {
      setIsConfigured(false)
      return
    }

    // User is authenticated, check if Typesense is configured
    api.getSearchKey()
      .then(() => setIsConfigured(true))
      .catch((err) => {
        console.error('Search configuration check failed:', err)
        setIsConfigured(false)
      })
  }, [isAuthLoading, user])

  // Perform search when debounced query changes
  useEffect(() => {
    if (!debouncedQuery || debouncedQuery.length < 2 || !user?.id) {
      setResults({ conversations: [], messages: [] })
      return
    }

    setIsLoading(true)
    performSearch(debouncedQuery, user.id)
      .then(setResults)
      .finally(() => setIsLoading(false))
  }, [debouncedQuery, user?.id])

  // Handle result selection
  const handleSelect = useCallback((type, item) => {
    setOpen(false)
    setQuery('')

    if (type === 'conversation') {
      // Navigate to Copilot with conversation selected
      if (onNavigate) {
        onNavigate('copilot', { conversationId: item.document.id })
      }
    } else if (type === 'message') {
      // Navigate to the conversation containing this message
      if (onNavigate) {
        onNavigate('copilot', { conversationId: item.document.conversation_id })
      }
    }
  }, [onNavigate])

  // Truncate text for display
  const truncate = (text, maxLength = 60) => {
    if (!text) return ''
    return text.length > maxLength ? text.slice(0, maxLength) + '...' : text
  }

  // Get highlighted text or fallback to original
  const getHighlight = (hit, field) => {
    const highlight = hit.highlight?.[field]?.snippet
    if (highlight) {
      return <span dangerouslySetInnerHTML={{ __html: highlight }} />
    }
    return truncate(hit.document?.[field])
  }

  const hasResults = results.conversations.length > 0 || results.messages.length > 0

  // Show loading state while checking configuration
  if (isConfigured === null) {
    return (
      <div className="relative w-full max-w-md">
        <div className="flex h-9 items-center rounded-md border border-input bg-muted/50 px-3 text-sm text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          <span>Loading search...</span>
        </div>
      </div>
    )
  }

  // If search is not configured, show disabled state
  if (!isConfigured) {
    return (
      <div className="relative w-full max-w-md">
        <div className="flex h-9 items-center rounded-md border border-input bg-muted/50 px-3 text-sm text-muted-foreground">
          <Search className="mr-2 h-4 w-4" />
          <span>Search not configured</span>
        </div>
      </div>
    )
  }

  return (
    <Popover open={open && (query.length >= 2)} onOpenChange={setOpen}>
      <PopoverAnchor asChild>
        <div className="relative w-full max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Search conversations and messages..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              if (e.target.value.length >= 2) {
                setOpen(true)
              }
            }}
            onFocus={() => {
              if (query.length >= 2) {
                setOpen(true)
              }
            }}
            className={cn(
              "flex h-9 w-full rounded-md border border-input bg-background pl-9 pr-3 py-2 text-sm",
              "ring-offset-background placeholder:text-muted-foreground",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              "disabled:cursor-not-allowed disabled:opacity-50"
            )}
          />
          {isLoading && (
            <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
          )}
        </div>
      </PopoverAnchor>

      <PopoverContent
        className="w-[var(--radix-popover-trigger-width)] p-0"
        align="start"
        sideOffset={4}
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <Command shouldFilter={false}>
          <CommandList>
            {!hasResults && !isLoading && (
              <CommandEmpty>No results found.</CommandEmpty>
            )}

            {results.conversations.length > 0 && (
              <CommandGroup heading="Conversations">
                {results.conversations.map((hit) => (
                  <CommandItem
                    key={hit.document.id}
                    value={hit.document.id}
                    onSelect={() => handleSelect('conversation', hit)}
                    className="cursor-pointer"
                  >
                    <MessagesSquare className="mr-2 h-4 w-4 text-muted-foreground" />
                    <div className="flex flex-col">
                      <span className="font-medium">
                        {getHighlight(hit, 'title')}
                      </span>
                      {hit.document.original_query && (
                        <span className="text-xs text-muted-foreground">
                          {truncate(hit.document.original_query, 50)}
                        </span>
                      )}
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}

            {results.messages.length > 0 && (
              <CommandGroup heading="Messages">
                {results.messages.map((hit) => (
                  <CommandItem
                    key={hit.document.id}
                    value={hit.document.id}
                    onSelect={() => handleSelect('message', hit)}
                    className="cursor-pointer"
                  >
                    <MessageSquare className="mr-2 h-4 w-4 text-muted-foreground" />
                    <span className="text-sm">
                      {getHighlight(hit, 'content')}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}

