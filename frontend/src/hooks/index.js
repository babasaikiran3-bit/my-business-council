/**
 * Custom hooks for the LLM Council application.
 * These hooks encapsulate complex state logic for better reusability and testing.
 */

export { useConversations } from './useConversations'
export { useStageTimings, useLiveElapsedTime, DEFAULT_STAGE_TIMINGS } from './useStageTimings'
export {
  useStreamState,
  createInitialStreamState,
  STREAM_TIMEOUT_MS,
  MAX_SIMULTANEOUS_STREAMS,
  STALE_CHECK_INTERVAL_MS,
  STALE_THRESHOLD_MS,
} from './useStreamState'

