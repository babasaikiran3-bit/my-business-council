/**
 * Tests for StageTimer component (Fix 8)
 * 
 * These tests verify that:
 * 1. StageTimer updates its display every 500ms while a stage is active
 * 2. StageTimer stops updating and shows "Completed in X.Xs" when stage completes
 * 3. StageTimer manages its own interval (doesn't require parent re-renders)
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { StageTimer } from './ProgressIndicator'

describe('StageTimer Component (Fix 8)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('Active Timer Behavior', () => {
    it('should display initial elapsed time based on startTime', () => {
      const startTime = Date.now() - 1500 // 1.5 seconds ago
      render(<StageTimer startTime={startTime} completed={false} />)
      
      // Should show approximately 1.5s (may vary slightly due to timing)
      const timerText = screen.getByText(/\d+\.\d+s/)
      expect(timerText).toBeInTheDocument()
    })

    it('should update display every 500ms while active', async () => {
      const startTime = Date.now()
      render(<StageTimer startTime={startTime} completed={false} updateInterval={500} />)
      
      // Initial state - should be close to 0.0s
      expect(screen.getByText('0.0s')).toBeInTheDocument()
      
      // Advance by 500ms
      await act(async () => {
        vi.advanceTimersByTime(500)
      })
      expect(screen.getByText('0.5s')).toBeInTheDocument()
      
      // Advance by another 500ms
      await act(async () => {
        vi.advanceTimersByTime(500)
      })
      expect(screen.getByText('1.0s')).toBeInTheDocument()
      
      // Advance by another 1000ms
      await act(async () => {
        vi.advanceTimersByTime(1000)
      })
      expect(screen.getByText('2.0s')).toBeInTheDocument()
    })

    it('should respect custom updateInterval prop', async () => {
      const startTime = Date.now()
      render(<StageTimer startTime={startTime} completed={false} updateInterval={1000} />)
      
      expect(screen.getByText('0.0s')).toBeInTheDocument()
      
      // Advance by 500ms - should NOT update yet (interval is 1000ms)
      await act(async () => {
        vi.advanceTimersByTime(500)
      })
      // Still shows 0.0s because interval hasn't fired
      expect(screen.getByText('0.0s')).toBeInTheDocument()
      
      // Advance by another 500ms (total 1000ms) - should update now
      await act(async () => {
        vi.advanceTimersByTime(500)
      })
      expect(screen.getByText('1.0s')).toBeInTheDocument()
    })
  })

  describe('Completed Timer Behavior', () => {
    it('should display "Completed in X.Xs" when completed with finalElapsed', () => {
      render(<StageTimer startTime={Date.now()} completed={true} finalElapsed={5500} />)
      
      expect(screen.getByText('Completed in 5.5s')).toBeInTheDocument()
    })

    it('should NOT update after completion', async () => {
      const startTime = Date.now() - 2000
      render(<StageTimer startTime={startTime} completed={true} finalElapsed={2000} />)
      
      expect(screen.getByText('Completed in 2.0s')).toBeInTheDocument()
      
      // Advance time - should NOT change the display
      await act(async () => {
        vi.advanceTimersByTime(5000)
      })
      
      // Should still show the same value
      expect(screen.getByText('Completed in 2.0s')).toBeInTheDocument()
    })

    it('should stop interval when transitioning from active to completed', async () => {
      const startTime = Date.now()
      const { rerender } = render(
        <StageTimer startTime={startTime} completed={false} updateInterval={500} />
      )
      
      // Let it run for a bit
      await act(async () => {
        vi.advanceTimersByTime(1000)
      })
      expect(screen.getByText('1.0s')).toBeInTheDocument()
      
      // Mark as completed
      rerender(<StageTimer startTime={startTime} completed={true} finalElapsed={1500} />)
      
      // Should show completed message
      expect(screen.getByText('Completed in 1.5s')).toBeInTheDocument()
      
      // Advance more time - should NOT update
      await act(async () => {
        vi.advanceTimersByTime(5000)
      })
      expect(screen.getByText('Completed in 1.5s')).toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('should display 0.0s when startTime is not provided', () => {
      render(<StageTimer completed={false} />)
      expect(screen.getByText('0.0s')).toBeInTheDocument()
    })

    it('should handle startTime of 0 gracefully', () => {
      render(<StageTimer startTime={0} completed={false} />)
      // Should show some large elapsed time
      const timerText = screen.getByText(/\d+\.\d+s/)
      expect(timerText).toBeInTheDocument()
    })
  })
})

