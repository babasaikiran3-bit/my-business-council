export interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export interface Stage1Response {
  model: string;
  response: string;
}

export interface Stage2Ranking {
  model: string;
  ranking: string;
  parsed_ranking: string[];
}

export interface Stage3Response {
  model: string;
  response: string;
}

export interface ConversationMetadata {
  id: string;
  created_at: string;
  title: string;
  message_count: number;
}

export interface Conversation {
  id: string;
  created_at: string;
  title: string;
  messages: ConversationMessage[];
}

export interface UserMessage {
  role: 'user';
  content: string;
}

export interface AssistantMessage {
  role: 'assistant';
  stage1: Stage1Response[];
  stage2: Stage2Ranking[];
  stage3: Stage3Response;
}

export type ConversationMessage = UserMessage | AssistantMessage;

export interface CouncilMetadata {
  label_to_model: Record<string, string>;
  aggregate_rankings: AggregateRanking[];
}

export interface AggregateRanking {
  model: string;
  average_rank: number;
  rankings_count: number;
}

export interface OpenRouterMessage {
  role: string;
  content: string;
}

export interface OpenRouterResponse {
  content: string;
  reasoning_details?: unknown;
}

export interface StreamEvent {
  type: 'stage1_start' | 'stage1_complete' | 'stage2_start' | 'stage2_complete' | 'stage3_start' | 'stage3_complete' | 'title_complete' | 'complete' | 'error';
  data?: unknown;
  metadata?: CouncilMetadata;
  message?: string;
}
