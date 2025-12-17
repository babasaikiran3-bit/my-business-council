import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

/**
 * Extract display name from model identifier.
 * E.g., "openai/gpt-4" -> "gpt-4", "gpt-4" -> "gpt-4", null -> "Unknown"
 *
 * @param {string|null|undefined} model - Model identifier string
 * @returns {string} Display name for the model
 */
export function getModelDisplayName(model) {
  if (!model) return 'Unknown'
  const parts = model.split('/')
  return parts.length > 1 ? parts[1] : model
}

/**
 * Fix #4.4: Shared timestamp formatting utility
 * Format a timestamp into a human-readable relative or absolute format.
 *
 * @param {string} isoString - ISO 8601 timestamp string
 * @returns {string|null} Formatted timestamp or null if invalid
 */
export function formatTimestamp(isoString) {
  if (!isoString) return null

  try {
    const date = new Date(isoString)
    if (isNaN(date.getTime())) return null

    const now = new Date()
    const diffMs = now - date
    const diffSec = Math.floor(diffMs / 1000)
    const diffMin = Math.floor(diffSec / 60)
    const diffHour = Math.floor(diffMin / 60)
    const diffDay = Math.floor(diffHour / 24)

    if (diffSec < 60) return 'Just now'
    if (diffMin < 60) return `${diffMin}m ago`
    if (diffHour < 24) return `${diffHour}h ago`
    if (diffDay === 1) return 'Yesterday'
    if (diffDay < 7) return `${diffDay}d ago`

    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
    })
  } catch {
    return null
  }
}

