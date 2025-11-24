import { config } from '../config.js';
import type { OpenRouterMessage, OpenRouterResponse } from '../types/index.js';

/**
 * Query a single model via OpenRouter API
 */
export async function queryModel(
  model: string,
  messages: OpenRouterMessage[],
  timeout: number = 120000
): Promise<OpenRouterResponse | null> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(config.openRouterApiUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${config.openRouterApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model,
        messages,
      }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    const message = data.choices[0].message;

    return {
      content: message.content,
      reasoning_details: message.reasoning_details,
    };
  } catch (error) {
    clearTimeout(timeoutId);
    console.error(`Error querying model ${model}:`, error);
    return null;
  }
}

/**
 * Query multiple models in parallel
 */
export async function queryModelsParallel(
  models: string[],
  messages: OpenRouterMessage[]
): Promise<Record<string, OpenRouterResponse | null>> {
  const tasks = models.map(model => queryModel(model, messages));
  const responses = await Promise.all(tasks);

  const result: Record<string, OpenRouterResponse | null> = {};
  models.forEach((model, index) => {
    result[model] = responses[index];
  });

  return result;
}
