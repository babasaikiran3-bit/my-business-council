-- ============================================
-- Incremental Persistence Migration
-- ============================================
-- This migration adds support for storing individual model responses
-- as they arrive during Stage 1 processing, enabling smart retry
-- without duplicate API calls for models that already responded.
--
-- Usage:
--   1. Go to Supabase Dashboard > SQL Editor
--   2. Paste this entire script
--   3. Click "Run"
--
-- Run on all environments: dev, staging, production

-- ============================================
-- Stage Model Responses Table
-- ============================================
-- Stores individual model responses as they arrive during Stage 1.
-- This enables incremental persistence and smart retry at the model level.
--
-- When Stage 1 completes successfully, these rows can be cleaned up
-- since the final aggregated data is stored in assistant_responses.stage1_responses.
-- However, if Stage 1 fails mid-way, these rows enable smart retry.

CREATE TABLE IF NOT EXISTS stage_model_responses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Link to the assistant response (which links to user message)
    assistant_response_id UUID NOT NULL REFERENCES assistant_responses(id) ON DELETE CASCADE,
    
    -- Stage identifier (1, 2, or 3)
    stage INTEGER NOT NULL CHECK (stage IN (1, 2, 3)),
    
    -- Model identifier (e.g., 'openai/gpt-5.2-pro')
    model_name TEXT NOT NULL,
    
    -- Response content (JSONB for flexibility)
    response_content JSONB,
    
    -- Timing information
    elapsed_ms INTEGER,
    
    -- Status: 'pending', 'success', 'failed'
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'success', 'failed')),
    
    -- Error message if failed
    error_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    
    -- Unique constraint: one response per model per stage per assistant_response
    UNIQUE (assistant_response_id, stage, model_name)
);

-- ============================================
-- Indexes for efficient queries
-- ============================================

-- Primary lookup: get all model responses for an assistant response
CREATE INDEX IF NOT EXISTS idx_stage_model_responses_assistant_response_id 
    ON stage_model_responses(assistant_response_id);

-- Filter by stage within a response
CREATE INDEX IF NOT EXISTS idx_stage_model_responses_stage 
    ON stage_model_responses(assistant_response_id, stage);

-- Find incomplete responses (for cleanup or debugging)
CREATE INDEX IF NOT EXISTS idx_stage_model_responses_status 
    ON stage_model_responses(status) WHERE status != 'success';

-- Timestamp for ordering and cleanup
CREATE INDEX IF NOT EXISTS idx_stage_model_responses_created_at 
    ON stage_model_responses(created_at);

-- ============================================
-- Add response_status to assistant_responses
-- ============================================
-- Tracks the overall status of the deliberation
-- This enables quick queries to find incomplete responses

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'assistant_responses' 
        AND column_name = 'response_status'
    ) THEN
        ALTER TABLE assistant_responses 
        ADD COLUMN response_status TEXT DEFAULT 'pending' 
        CHECK (response_status IN (
            'pending',           -- Just created, no stages started
            'stage1_in_progress', -- Stage 1 running, collecting model responses
            'stage1_complete',   -- Stage 1 done, stage 2 not started
            'stage2_in_progress', -- Stage 2 running
            'stage2_complete',   -- Stage 2 done, stage 3 not started
            'stage3_in_progress', -- Stage 3 running
            'complete',          -- All stages done successfully
            'failed'             -- Deliberation failed (check error_details)
        ));
    END IF;
END $$;

-- Add error_details column if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'assistant_responses' 
        AND column_name = 'error_details'
    ) THEN
        ALTER TABLE assistant_responses 
        ADD COLUMN error_details JSONB;
    END IF;
END $$;

-- Index for finding incomplete responses quickly
CREATE INDEX IF NOT EXISTS idx_assistant_responses_status 
    ON assistant_responses(response_status) 
    WHERE response_status NOT IN ('complete', 'failed');

-- ============================================
-- Row Level Security for stage_model_responses
-- ============================================
ALTER TABLE stage_model_responses ENABLE ROW LEVEL SECURITY;

-- Users can view model responses for their assistant responses
CREATE POLICY "Users can view model responses for own conversations"
    ON stage_model_responses FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM assistant_responses ar
            JOIN messages m ON m.id = ar.user_message_id
            JOIN conversations c ON c.id = m.conversation_id
            WHERE ar.id = stage_model_responses.assistant_response_id
            AND (c.user_id = auth.uid()::text OR c.user_id = current_setting('app.current_user_id', true))
        )
    );

-- Users can insert model responses for their assistant responses
CREATE POLICY "Users can create model responses for own conversations"
    ON stage_model_responses FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM assistant_responses ar
            JOIN messages m ON m.id = ar.user_message_id
            JOIN conversations c ON c.id = m.conversation_id
            WHERE ar.id = stage_model_responses.assistant_response_id
            AND (c.user_id = auth.uid()::text OR c.user_id = current_setting('app.current_user_id', true))
        )
    );

-- Users can update model responses for their assistant responses
CREATE POLICY "Users can update model responses for own conversations"
    ON stage_model_responses FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM assistant_responses ar
            JOIN messages m ON m.id = ar.user_message_id
            JOIN conversations c ON c.id = m.conversation_id
            WHERE ar.id = stage_model_responses.assistant_response_id
            AND (c.user_id = auth.uid()::text OR c.user_id = current_setting('app.current_user_id', true))
        )
    );

-- Users can delete model responses for their assistant responses
-- (Deletion usually happens via CASCADE from assistant_responses, but explicit policy for completeness)
CREATE POLICY "Users can delete model responses for own conversations"
    ON stage_model_responses FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM assistant_responses ar
            JOIN messages m ON m.id = ar.user_message_id
            JOIN conversations c ON c.id = m.conversation_id
            WHERE ar.id = stage_model_responses.assistant_response_id
            AND (c.user_id = auth.uid()::text OR c.user_id = current_setting('app.current_user_id', true))
        )
    );

-- ============================================
-- Verification Queries
-- ============================================
-- Run these to verify the migration was applied correctly:
--
-- Check new table exists:
-- SELECT * FROM information_schema.tables WHERE table_name = 'stage_model_responses';
--
-- Check new columns on assistant_responses:
-- SELECT column_name, data_type FROM information_schema.columns
-- WHERE table_name = 'assistant_responses' AND column_name IN ('response_status', 'error_details');
--
-- Check RLS policies:
-- SELECT tablename, policyname FROM pg_policies WHERE tablename = 'stage_model_responses';
--
-- Check indexes:
-- SELECT indexname FROM pg_indexes WHERE tablename = 'stage_model_responses';

