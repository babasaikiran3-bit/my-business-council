import dotenv from 'dotenv';

dotenv.config();

export const config = {
  // OpenRouter API key
  openRouterApiKey: process.env.OPENROUTER_API_KEY || '',

  // Council members - list of OpenRouter model identifiers
  councilModels: [
    'openai/gpt-5.1',
    'google/gemini-3-pro-preview',
    'anthropic/claude-sonnet-4.5',
    'x-ai/grok-4',
  ],

  // Chairman model - synthesizes final response
  chairmanModel: 'google/gemini-3-pro-preview',

  // OpenRouter API endpoint
  openRouterApiUrl: 'https://openrouter.ai/api/v1/chat/completions',

  // Data directory for conversation storage
  dataDir: 'data/conversations',

  // Server port
  port: parseInt(process.env.PORT || '8001', 10),
};
