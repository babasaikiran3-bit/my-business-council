import fs from 'fs/promises';
import path from 'path';
import { config } from '../config.js';
import type {
  Conversation,
  ConversationMetadata,
  Stage1Response,
  Stage2Ranking,
  Stage3Response,
} from '../types/index.js';

/**
 * Ensure the data directory exists
 */
async function ensureDataDir(): Promise<void> {
  try {
    await fs.mkdir(config.dataDir, { recursive: true });
  } catch (error) {
    // Directory might already exist
  }
}

/**
 * Get the file path for a conversation
 */
function getConversationPath(conversationId: string): string {
  return path.join(config.dataDir, `${conversationId}.json`);
}

/**
 * Create a new conversation
 */
export async function createConversation(conversationId: string): Promise<Conversation> {
  await ensureDataDir();

  const conversation: Conversation = {
    id: conversationId,
    created_at: new Date().toISOString(),
    title: 'New Conversation',
    messages: [],
  };

  const filePath = getConversationPath(conversationId);
  await fs.writeFile(filePath, JSON.stringify(conversation, null, 2));

  return conversation;
}

/**
 * Load a conversation from storage
 */
export async function getConversation(conversationId: string): Promise<Conversation | null> {
  const filePath = getConversationPath(conversationId);

  try {
    const data = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(data);
  } catch (error) {
    return null;
  }
}

/**
 * Save a conversation to storage
 */
export async function saveConversation(conversation: Conversation): Promise<void> {
  await ensureDataDir();

  const filePath = getConversationPath(conversation.id);
  await fs.writeFile(filePath, JSON.stringify(conversation, null, 2));
}

/**
 * List all conversations (metadata only)
 */
export async function listConversations(): Promise<ConversationMetadata[]> {
  await ensureDataDir();

  const conversations: ConversationMetadata[] = [];

  try {
    const files = await fs.readdir(config.dataDir);

    for (const filename of files) {
      if (filename.endsWith('.json')) {
        const filePath = path.join(config.dataDir, filename);
        const data = await fs.readFile(filePath, 'utf-8');
        const conv: Conversation = JSON.parse(data);

        conversations.push({
          id: conv.id,
          created_at: conv.created_at,
          title: conv.title,
          message_count: conv.messages.length,
        });
      }
    }
  } catch (error) {
    // Directory might not exist yet
  }

  // Sort by creation time, newest first
  conversations.sort((a, b) => {
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  return conversations;
}

/**
 * Add a user message to a conversation
 */
export async function addUserMessage(
  conversationId: string,
  content: string
): Promise<void> {
  const conversation = await getConversation(conversationId);
  if (!conversation) {
    throw new Error(`Conversation ${conversationId} not found`);
  }

  conversation.messages.push({
    role: 'user',
    content,
  });

  await saveConversation(conversation);
}

/**
 * Add an assistant message with all 3 stages to a conversation
 */
export async function addAssistantMessage(
  conversationId: string,
  stage1: Stage1Response[],
  stage2: Stage2Ranking[],
  stage3: Stage3Response
): Promise<void> {
  const conversation = await getConversation(conversationId);
  if (!conversation) {
    throw new Error(`Conversation ${conversationId} not found`);
  }

  conversation.messages.push({
    role: 'assistant',
    stage1,
    stage2,
    stage3,
  });

  await saveConversation(conversation);
}

/**
 * Update the title of a conversation
 */
export async function updateConversationTitle(
  conversationId: string,
  title: string
): Promise<void> {
  const conversation = await getConversation(conversationId);
  if (!conversation) {
    throw new Error(`Conversation ${conversationId} not found`);
  }

  conversation.title = title;
  await saveConversation(conversation);
}
