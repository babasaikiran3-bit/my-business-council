/**
 * Custom hook for managing stage timing state during deliberations.
 * Handles elapsed time tracking for each stage of the 3-stage process.
 */

import { useState, useCallback, useRef, useEffect } from 'react'

/**
 * Default stage timings structure (used for initialization and reset).
 */
export const DEFAULT_STAGE_TIMINGS = {
  stage1: { startTime: null, elapsed: 0, completed: false },
  stage2: { startTime: null, elapsed: 0, completed: false },
  stage3: { startTime: null, elapsed: 0, completed: false },
}

/**
 * Hook for managing stage timing state.
 *
 * @returns {Object} Stage timing state and operations
 */
export function useStageTimings() {
  const [stageTimings, setStageTimings] = useState({ ...DEFAULT_STAGE_TIMINGS })

  /**
   * Start timing for a specific stage.
   * @param {string} stageName - 'stage1', 'stage2', or 'stage3'
   */
  const startStage = useCallback((stageName) => {
    setStageTimings(prev => ({
      ...prev,
      [stageName]: {
        ...prev[stageName],
        startTime: Date.now(),
        elapsed: 0,
        completed: false,
      }
    }))
  }, [])

  /**
   * Mark a stage as completed and calculate final elapsed time.
   * @param {string} stageName - 'stage1', 'stage2', or 'stage3'
   */
  const completeStage = useCallback((stageName) => {
    setStageTimings(prev => {
      const stageTiming = prev[stageName]
      const finalElapsed = stageTiming.startTime
        ? Date.now() - stageTiming.startTime
        : 0
      return {
        ...prev,
        [stageName]: {
          ...stageTiming,
          completed: true,
          elapsed: finalElapsed,
        }
      }
    })
  }, [])

  /**
   * Reset all stage timings to defaults.
   */
  const resetTimings = useCallback(() => {
    setStageTimings({ ...DEFAULT_STAGE_TIMINGS })
  }, [])

  /**
   * Get the current elapsed time for a stage (live calculation for running stages).
   * @param {string} stageName - 'stage1', 'stage2', or 'stage3'
   * @returns {number} Elapsed time in milliseconds
   */
  const getElapsed = useCallback((stageName) => {
    const stage = stageTimings[stageName]
    if (stage.completed) {
      return stage.elapsed
    }
    if (stage.startTime) {
      return Date.now() - stage.startTime
    }
    return 0
  }, [stageTimings])

  return {
    stageTimings,
    setStageTimings,
    startStage,
    completeStage,
    resetTimings,
    getElapsed,
    DEFAULT_STAGE_TIMINGS,
  }
}

/**
 * Hook for live elapsed time updates (re-renders every second while a stage is running).
 *
 * @param {Object} stageTimings - The stage timings object
 * @returns {Object} Live elapsed times for each stage
 */
export function useLiveElapsedTime(stageTimings) {
  const [, forceUpdate] = useState(0)
  const intervalRef = useRef(null)

  // Check if any stage is currently running (has startTime but not completed)
  const isAnyStageRunning = Object.values(stageTimings).some(
    stage => stage.startTime && !stage.completed
  )

  useEffect(() => {
    if (isAnyStageRunning) {
      // Update every 100ms for smooth timer display
      intervalRef.current = setInterval(() => {
        forceUpdate(n => n + 1)
      }, 100)
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [isAnyStageRunning])

  // Calculate live elapsed times
  return Object.fromEntries(
    Object.entries(stageTimings).map(([stageName, stage]) => {
      let elapsed = 0
      if (stage.completed) {
        elapsed = stage.elapsed
      } else if (stage.startTime) {
        elapsed = Date.now() - stage.startTime
      }
      return [stageName, elapsed]
    })
  )
}

