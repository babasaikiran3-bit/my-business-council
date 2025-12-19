/**
 * Custom hook for managing conversation list state and operations.
 * Handles fetching, pagination, and CRUD operations for conversations.
 */

import { useState, useCallback } from 'react'
import { toast } from 'sonner'
import { api } from '../api'
import { isConnectionError } from '@/contexts/ConnectionErrorContext'

// Pagination constants
const CONVERSATIONS_PAGE_SIZE = 10

/**
 * Hook for managing conversation list with pagination.
 *
 * @returns {Object} Conversation list state and operations
 */
export function useConversations() {
  const [conversations, setConversations] = useState([])
  const [isLoadingConversations, setIsLoadingConversations] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [hasMoreConversations, setHasMoreConversations] = useState(true)
  const [conversationsOffset, setConversationsOffset] = useState(0)

  /**
   * Load the initial page of conversations.
   */
  const loadConversations = useCallback(async () => {
    setIsLoadingConversations(true)
    try {
      const result = await api.listConversations({ limit: CONVERSATIONS_PAGE_SIZE, offset: 0 })
      setConversations(result.conversations)
      setHasMoreConversations(result.has_more)
      setConversationsOffset(result.conversations.length)
    } catch (error) {
      console.error('Failed to load conversations:', error)
      if (!isConnectionError(error)) {
        toast.error('Failed to load conversations')
      }
    } finally {
      setIsLoadingConversations(false)
    }
  }, [])

  /**
   * Load the next page of conversations (infinite scroll).
   */
  const loadMoreConversations = useCallback(async () => {
    if (isLoadingMore || !hasMoreConversations) return

    setIsLoadingMore(true)
    try {
      const result = await api.listConversations({
        limit: CONVERSATIONS_PAGE_SIZE,
        offset: conversationsOffset
      })
      setConversations(prev => [...prev, ...result.conversations])
      setHasMoreConversations(result.has_more)
      setConversationsOffset(prev => prev + result.conversations.length)
    } catch (error) {
      console.error('Failed to load more conversations:', error)
      if (!isConnectionError(error)) {
        toast.error('Failed to load more conversations')
      }
    } finally {
      setIsLoadingMore(false)
    }
  }, [isLoadingMore, hasMoreConversations, conversationsOffset])

  /**
   * Add a new conversation to the list (at the beginning).
   * @param {Object} conversation - The conversation to add
   */
  const addConversation = useCallback((conversation) => {
    setConversations(prev => [conversation, ...prev])
  }, [])

  /**
   * Update a conversation in the list (e.g., title change).
   * @param {string} conversationId - The ID of the conversation to update
   * @param {Object} updates - The fields to update
   */
  const updateConversation = useCallback((conversationId, updates) => {
    setConversations(prev =>
      prev.map(conv =>
        conv.id === conversationId ? { ...conv, ...updates } : conv
      )
    )
  }, [])

  /**
   * Remove a conversation from the list.
   * @param {string} conversationId - The ID of the conversation to remove
   */
  const removeConversation = useCallback((conversationId) => {
    setConversations(prev => prev.filter(conv => conv.id !== conversationId))
  }, [])

  return {
    // State
    conversations,
    isLoadingConversations,
    isLoadingMore,
    hasMoreConversations,
    // Actions
    loadConversations,
    loadMoreConversations,
    addConversation,
    updateConversation,
    removeConversation,
  }
}

