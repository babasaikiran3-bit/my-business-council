import { config } from '../config.js';
import { queryModel, queryModelsParallel } from './openrouter.js';
import type {
  Stage1Response,
  Stage2Ranking,
  Stage3Response,
  CouncilMetadata,
  AggregateRanking,
  OpenRouterMessage,
} from '../types/index.js';

/**
 * Stage 1: Collect individual responses from all council models
 */
export async function stage1CollectResponses(userQuery: string): Promise<Stage1Response[]> {
  const messages: OpenRouterMessage[] = [{ role: 'user', content: userQuery }];

  // Query all models in parallel
  const responses = await queryModelsParallel(config.councilModels, messages);

  // Format results - only include successful responses
  const stage1Results: Stage1Response[] = [];
  for (const [model, response] of Object.entries(responses)) {
    if (response !== null) {
      stage1Results.push({
        model,
        response: response.content,
      });
    }
  }

  return stage1Results;
}

/**
 * Parse the FINAL RANKING section from model's response
 */
export function parseRankingFromText(rankingText: string): string[] {
  // Look for "FINAL RANKING:" section
  if (rankingText.includes('FINAL RANKING:')) {
    const parts = rankingText.split('FINAL RANKING:');
    if (parts.length >= 2) {
      const rankingSection = parts[1];

      // Try to extract numbered list format (e.g., "1. Response A")
      const numberedMatches = rankingSection.match(/\d+\.\s*Response [A-Z]/g);
      if (numberedMatches) {
        return numberedMatches.map(m => {
          const match = m.match(/Response [A-Z]/);
          return match ? match[0] : '';
        }).filter(Boolean);
      }

      // Fallback: Extract all "Response X" patterns in order
      const matches = rankingSection.match(/Response [A-Z]/g);
      return matches || [];
    }
  }

  // Fallback: try to find any "Response X" patterns in order
  const matches = rankingText.match(/Response [A-Z]/g);
  return matches || [];
}

/**
 * Stage 2: Each model ranks the anonymized responses
 */
export async function stage2CollectRankings(
  userQuery: string,
  stage1Results: Stage1Response[]
): Promise<{ rankings: Stage2Ranking[]; labelToModel: Record<string, string> }> {
  // Create anonymized labels for responses (Response A, Response B, etc.)
  const labels = stage1Results.map((_, i) => String.fromCharCode(65 + i));

  // Create mapping from label to model name
  const labelToModel: Record<string, string> = {};
  labels.forEach((label, i) => {
    labelToModel[`Response ${label}`] = stage1Results[i].model;
  });

  // Build the ranking prompt
  const responsesText = stage1Results
    .map((result, i) => `Response ${labels[i]}:\n${result.response}`)
    .join('\n\n');

  const rankingPrompt = `You are evaluating different responses to the following question:

Question: ${userQuery}

Here are the responses from different models (anonymized):

${responsesText}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:`;

  const messages: OpenRouterMessage[] = [{ role: 'user', content: rankingPrompt }];

  // Get rankings from all council models in parallel
  const responses = await queryModelsParallel(config.councilModels, messages);

  // Format results
  const stage2Results: Stage2Ranking[] = [];
  for (const [model, response] of Object.entries(responses)) {
    if (response !== null) {
      const fullText = response.content;
      const parsed = parseRankingFromText(fullText);
      stage2Results.push({
        model,
        ranking: fullText,
        parsed_ranking: parsed,
      });
    }
  }

  return { rankings: stage2Results, labelToModel };
}

/**
 * Stage 3: Chairman synthesizes final response
 */
export async function stage3SynthesizeFinal(
  userQuery: string,
  stage1Results: Stage1Response[],
  stage2Results: Stage2Ranking[]
): Promise<Stage3Response> {
  // Build comprehensive context for chairman
  const stage1Text = stage1Results
    .map(result => `Model: ${result.model}\nResponse: ${result.response}`)
    .join('\n\n');

  const stage2Text = stage2Results
    .map(result => `Model: ${result.model}\nRanking: ${result.ranking}`)
    .join('\n\n');

  const chairmanPrompt = `You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: ${userQuery}

STAGE 1 - Individual Responses:
${stage1Text}

STAGE 2 - Peer Rankings:
${stage2Text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:`;

  const messages: OpenRouterMessage[] = [{ role: 'user', content: chairmanPrompt }];

  // Query the chairman model
  const response = await queryModel(config.chairmanModel, messages);

  if (response === null) {
    return {
      model: config.chairmanModel,
      response: 'Error: Unable to generate final synthesis.',
    };
  }

  return {
    model: config.chairmanModel,
    response: response.content,
  };
}

/**
 * Calculate aggregate rankings across all models
 */
export function calculateAggregateRankings(
  stage2Results: Stage2Ranking[],
  labelToModel: Record<string, string>
): AggregateRanking[] {
  const modelPositions: Record<string, number[]> = {};

  for (const ranking of stage2Results) {
    const parsedRanking = parseRankingFromText(ranking.ranking);

    parsedRanking.forEach((label, index) => {
      if (label in labelToModel) {
        const modelName = labelToModel[label];
        if (!modelPositions[modelName]) {
          modelPositions[modelName] = [];
        }
        modelPositions[modelName].push(index + 1);
      }
    });
  }

  // Calculate average position for each model
  const aggregate: AggregateRanking[] = [];
  for (const [model, positions] of Object.entries(modelPositions)) {
    if (positions.length > 0) {
      const avgRank = positions.reduce((a, b) => a + b, 0) / positions.length;
      aggregate.push({
        model,
        average_rank: Math.round(avgRank * 100) / 100,
        rankings_count: positions.length,
      });
    }
  }

  // Sort by average rank (lower is better)
  aggregate.sort((a, b) => a.average_rank - b.average_rank);

  return aggregate;
}

/**
 * Generate a short title for a conversation
 */
export async function generateConversationTitle(userQuery: string): Promise<string> {
  const titlePrompt = `Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: ${userQuery}

Title:`;

  const messages: OpenRouterMessage[] = [{ role: 'user', content: titlePrompt }];

  // Use gemini-2.5-flash for title generation (fast and cheap)
  const response = await queryModel('google/gemini-2.5-flash', messages, 30000);

  if (response === null) {
    return 'New Conversation';
  }

  let title = response.content.trim();

  // Clean up the title - remove quotes, limit length
  title = title.replace(/^["']|["']$/g, '');

  // Truncate if too long
  if (title.length > 50) {
    title = title.substring(0, 47) + '...';
  }

  return title;
}

/**
 * Run the complete 3-stage council process
 */
export async function runFullCouncil(
  userQuery: string
): Promise<{
  stage1: Stage1Response[];
  stage2: Stage2Ranking[];
  stage3: Stage3Response;
  metadata: CouncilMetadata;
}> {
  // Stage 1: Collect individual responses
  const stage1Results = await stage1CollectResponses(userQuery);

  // If no models responded successfully, return error
  if (stage1Results.length === 0) {
    return {
      stage1: [],
      stage2: [],
      stage3: {
        model: 'error',
        response: 'All models failed to respond. Please try again.',
      },
      metadata: {
        label_to_model: {},
        aggregate_rankings: [],
      },
    };
  }

  // Stage 2: Collect rankings
  const { rankings: stage2Results, labelToModel } = await stage2CollectRankings(
    userQuery,
    stage1Results
  );

  // Calculate aggregate rankings
  const aggregateRankings = calculateAggregateRankings(stage2Results, labelToModel);

  // Stage 3: Synthesize final answer
  const stage3Result = await stage3SynthesizeFinal(userQuery, stage1Results, stage2Results);

  return {
    stage1: stage1Results,
    stage2: stage2Results,
    stage3: stage3Result,
    metadata: {
      label_to_model: labelToModel,
      aggregate_rankings: aggregateRankings,
    },
  };
}
