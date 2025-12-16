-- ============================================
-- Eternal Ops Control Database Schema
-- ============================================
-- This script creates all tables and RLS policies for the Eternal Ops Control application.
-- Run this in the Supabase SQL Editor to set up a new environment.
--
-- Usage:
--   1. Go to Supabase Dashboard > SQL Editor
--   2. Paste this entire script
--   3. Click "Run"
--
-- Or use the Supabase CLI:
--   supabase db push --db-url "postgresql://postgres:[PASSWORD]@db.[PROJECT-ID].supabase.co:5432/postgres"

-- ============================================
-- Enable UUID extension (usually already enabled)
-- ============================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- Conversations Table
-- ============================================
-- Stores conversation metadata for each user
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    organization_id TEXT,
    title TEXT DEFAULT 'New Conversation',
    original_query TEXT,
    improved_query TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

-- Index for faster user lookups
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_organization_id ON conversations(organization_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at DESC);

-- ============================================
-- Messages Table
-- ============================================
-- Stores user messages within conversations (user queries only)
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster conversation message lookups
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- ============================================
-- Assistant Responses Table
-- ============================================
-- Stores AI responses linked to user messages (1:1 relationship)
-- Each user message can have at most one assistant response
CREATE TABLE IF NOT EXISTS assistant_responses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_message_id UUID UNIQUE NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    stage1_responses JSONB,
    stage2_evaluations JSONB,
    stage3_synthesis JSONB,
    stage1_duration_ms INTEGER,
    stage2_duration_ms INTEGER,
    stage3_duration_ms INTEGER,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for efficient response lookups by user message
CREATE INDEX IF NOT EXISTS idx_assistant_responses_user_message_id ON assistant_responses(user_message_id);
CREATE INDEX IF NOT EXISTS idx_assistant_responses_created_at ON assistant_responses(created_at);

-- ============================================
-- Conversation Shares Table (Future Feature)
-- ============================================
-- For organization-based sharing between @eternal.ag users
CREATE TABLE IF NOT EXISTS conversation_shares (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    shared_with_user_id TEXT,
    shared_with_organization_id TEXT,
    permission TEXT DEFAULT 'read' CHECK (permission IN ('read', 'write', 'admin')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT NOT NULL
);

-- Index for share lookups
CREATE INDEX IF NOT EXISTS idx_shares_conversation_id ON conversation_shares(conversation_id);
CREATE INDEX IF NOT EXISTS idx_shares_shared_with_user ON conversation_shares(shared_with_user_id);
CREATE INDEX IF NOT EXISTS idx_shares_shared_with_org ON conversation_shares(shared_with_organization_id);

-- ============================================
-- Row Level Security (RLS) Policies
-- ============================================
-- Enable RLS on all tables
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE assistant_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_shares ENABLE ROW LEVEL SECURITY;

-- ============================================
-- Conversations Policies
-- ============================================
-- Users can only see their own conversations
CREATE POLICY "Users can view own conversations"
    ON conversations FOR SELECT
    USING (auth.uid()::text = user_id OR user_id = current_setting('app.current_user_id', true));

-- Users can insert their own conversations
CREATE POLICY "Users can create own conversations"
    ON conversations FOR INSERT
    WITH CHECK (auth.uid()::text = user_id OR user_id = current_setting('app.current_user_id', true));

-- Users can update their own conversations
CREATE POLICY "Users can update own conversations"
    ON conversations FOR UPDATE
    USING (auth.uid()::text = user_id OR user_id = current_setting('app.current_user_id', true));

-- Users can delete (soft delete) their own conversations
CREATE POLICY "Users can delete own conversations"
    ON conversations FOR DELETE
    USING (auth.uid()::text = user_id OR user_id = current_setting('app.current_user_id', true));

-- ============================================
-- Messages Policies
-- ============================================
-- Users can view messages in their conversations
CREATE POLICY "Users can view messages in own conversations"
    ON messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM conversations c
            WHERE c.id = messages.conversation_id
            AND (c.user_id = auth.uid()::text OR c.user_id = current_setting('app.current_user_id', true))
        )
    );

-- Users can insert messages in their conversations
CREATE POLICY "Users can create messages in own conversations"
    ON messages FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM conversations c
            WHERE c.id = messages.conversation_id
            AND (c.user_id = auth.uid()::text OR c.user_id = current_setting('app.current_user_id', true))
        )
    );

-- ============================================
-- Assistant Responses Policies
-- ============================================
-- Users can view assistant responses for their messages
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

-- Users can insert assistant responses for their messages
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

-- Users can update assistant responses for their messages (for incremental saves)
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
-- Conversation Shares Policies
-- ============================================
-- Users can view shares for their conversations or shares with them
CREATE POLICY "Users can view relevant shares"
    ON conversation_shares FOR SELECT
    USING (
        shared_with_user_id = auth.uid()::text
        OR shared_with_user_id = current_setting('app.current_user_id', true)
        OR EXISTS (
            SELECT 1 FROM conversations c
            WHERE c.id = conversation_shares.conversation_id
            AND (c.user_id = auth.uid()::text OR c.user_id = current_setting('app.current_user_id', true))
        )
    );

-- ============================================
-- Service Role Bypass
-- ============================================
-- The service role key bypasses RLS automatically.
-- This is used by the backend server for all operations.

CREATE TRIGGER update_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Helpful Views (Optional)
-- ============================================
-- View for conversations with message counts
CREATE OR REPLACE VIEW conversation_summaries AS
SELECT
    c.id,
    c.user_id,
    c.organization_id,
    c.title,
    c.original_query,
    c.created_at,
    c.updated_at,
    COUNT(m.id) as message_count,
    MAX(m.created_at) as last_message_at
FROM conversations c
LEFT JOIN messages m ON c.id = m.conversation_id
WHERE c.is_deleted = FALSE
GROUP BY c.id;

-- ============================================
-- Verification Queries
-- ============================================
-- Run these to verify the schema was created correctly:
--
-- Check tables exist:
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
--
-- Check RLS is enabled:
-- SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';
--
-- Check policies exist:
-- SELECT tablename, policyname FROM pg_policies WHERE schemaname = 'public';

