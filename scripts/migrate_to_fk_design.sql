-- ============================================
-- Migration: Messages Table to FK Design
-- ============================================
-- This script migrates from the single-table polymorphic design 
-- (messages with role='user' and role='assistant') to the FK design
-- (user messages in 'messages' table, assistant responses in 'assistant_responses' table)
--
-- IMPORTANT: Run this migration in a transaction and verify before committing!
-- Usage:
--   1. Start a transaction: BEGIN;
--   2. Run this script
--   3. Verify data integrity with the verification queries at the end
--   4. If all looks good: COMMIT;
--   5. If issues found: ROLLBACK;

-- ============================================
-- Step 1: Create the new assistant_responses table
-- ============================================
CREATE TABLE IF NOT EXISTS assistant_responses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_message_id UUID UNIQUE,  -- FK added after data migration
    stage1_responses JSONB,
    stage2_evaluations JSONB,
    stage3_synthesis JSONB,
    stage1_duration_ms INTEGER,
    stage2_duration_ms INTEGER,
    stage3_duration_ms INTEGER,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_assistant_responses_user_message_id ON assistant_responses(user_message_id);
CREATE INDEX IF NOT EXISTS idx_assistant_responses_created_at ON assistant_responses(created_at);

-- ============================================
-- Step 2: Migrate assistant message data to new table
-- ============================================
-- For each assistant message, find the preceding user message in the same 
-- conversation and create a linked response record.

INSERT INTO assistant_responses (
    user_message_id,
    stage1_responses,
    stage2_evaluations,
    stage3_synthesis,
    stage1_duration_ms,
    stage2_duration_ms,
    stage3_duration_ms,
    metadata,
    created_at
)
SELECT 
    prev_user.id AS user_message_id,
    assistant.stage1_responses,
    assistant.stage2_evaluations,
    assistant.stage3_synthesis,
    assistant.stage1_duration_ms,
    assistant.stage2_duration_ms,
    assistant.stage3_duration_ms,
    assistant.metadata,
    assistant.created_at
FROM messages assistant
CROSS JOIN LATERAL (
    SELECT id 
    FROM messages 
    WHERE conversation_id = assistant.conversation_id 
      AND role = 'user' 
      AND created_at < assistant.created_at 
    ORDER BY created_at DESC 
    LIMIT 1
) prev_user
WHERE assistant.role = 'assistant';

-- ============================================
-- Step 3: Verification queries (run these manually to verify)
-- ============================================
-- Check counts match:
-- SELECT 'assistant_messages' as type, COUNT(*) FROM messages WHERE role = 'assistant'
-- UNION ALL
-- SELECT 'migrated_responses' as type, COUNT(*) FROM assistant_responses;

-- Check no orphaned responses (should return 0):
-- SELECT COUNT(*) FROM assistant_responses ar
-- LEFT JOIN messages m ON ar.user_message_id = m.id
-- WHERE m.id IS NULL;

-- ============================================
-- Step 4: Delete assistant messages from old table
-- ============================================
DELETE FROM messages WHERE role = 'assistant';

-- ============================================
-- Step 5: Add FK constraint now that data is clean
-- ============================================
ALTER TABLE assistant_responses 
    ADD CONSTRAINT fk_assistant_responses_user_message
    FOREIGN KEY (user_message_id) 
    REFERENCES messages(id) 
    ON DELETE CASCADE;

-- Make user_message_id NOT NULL after FK is in place
ALTER TABLE assistant_responses ALTER COLUMN user_message_id SET NOT NULL;

-- ============================================
-- Step 6: Drop unused columns from messages table
-- ============================================
ALTER TABLE messages DROP COLUMN IF EXISTS role;
ALTER TABLE messages DROP COLUMN IF EXISTS stage1_responses;
ALTER TABLE messages DROP COLUMN IF EXISTS stage2_evaluations;
ALTER TABLE messages DROP COLUMN IF EXISTS stage3_synthesis;
ALTER TABLE messages DROP COLUMN IF EXISTS stage1_duration_ms;
ALTER TABLE messages DROP COLUMN IF EXISTS stage2_duration_ms;
ALTER TABLE messages DROP COLUMN IF EXISTS stage3_duration_ms;
ALTER TABLE messages DROP COLUMN IF EXISTS metadata;

-- Make content NOT NULL since all remaining messages are user messages
ALTER TABLE messages ALTER COLUMN content SET NOT NULL;

-- ============================================
-- Step 7: Enable RLS on new table
-- ============================================
ALTER TABLE assistant_responses ENABLE ROW LEVEL SECURITY;

-- RLS Policies for assistant_responses
CREATE POLICY "Users can view assistant responses in own conversations"
    ON assistant_responses FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE m.id = assistant_responses.user_message_id
            AND (c.user_id = auth.uid()::text OR c.user_id = current_setting('app.current_user_id', true))
        )
    );

CREATE POLICY "Users can create assistant responses in own conversations"
    ON assistant_responses FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE m.id = assistant_responses.user_message_id
            AND (c.user_id = auth.uid()::text OR c.user_id = current_setting('app.current_user_id', true))
        )
    );

CREATE POLICY "Users can update assistant responses in own conversations"
    ON assistant_responses FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE m.id = assistant_responses.user_message_id
            AND (c.user_id = auth.uid()::text OR c.user_id = current_setting('app.current_user_id', true))
        )
    );

-- ============================================
-- Final Verification Queries
-- ============================================
-- Run these after migration to verify everything is correct:

-- 1. Check that messages table only has user messages (should return 0):
-- SELECT COUNT(*) FROM messages WHERE role IS NOT NULL;

-- 2. Check all assistant_responses have valid user_message_id:
-- SELECT COUNT(*) FROM assistant_responses ar
-- LEFT JOIN messages m ON ar.user_message_id = m.id
-- WHERE m.id IS NULL;

-- 3. Check conversation message counts:
-- SELECT c.id, c.title, COUNT(m.id) as msg_count, COUNT(ar.id) as response_count
-- FROM conversations c
-- LEFT JOIN messages m ON m.conversation_id = c.id
-- LEFT JOIN assistant_responses ar ON ar.user_message_id = m.id
-- GROUP BY c.id, c.title
-- ORDER BY c.created_at DESC
-- LIMIT 10;

