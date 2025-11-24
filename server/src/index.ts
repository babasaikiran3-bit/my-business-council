import express from 'express';
import cors from 'cors';
import { v4 as uuidv4 } from 'uuid';
import { config } from './config.js';
import * as storage from './services/storage.js';
import * as council from './services/council.js';
import type { Conversation } from './types/index.js';

const app = express();

// Middleware
app.use(cors({
  origin: ['http://localhost:5173', 'http://localhost:3000'],
  credentials: true,
}));
app.use(express.json());

// Health check endpoint
app.get('/', (req, res) => {
  res.json({ status: 'ok', service: 'LLM Council API' });
});

// List all conversations
app.get('/api/conversations', async (req, res) => {
  try {
    const conversations = await storage.listConversations();
    res.json(conversations);
  } catch (error) {
    console.error('Error listing conversations:', error);
    res.status(500).json({ error: 'Failed to list conversations' });
  }
});

// Create a new conversation
app.post('/api/conversations', async (req, res) => {
  try {
    const conversationId = uuidv4();
    const conversation = await storage.createConversation(conversationId);
    res.json(conversation);
  } catch (error) {
    console.error('Error creating conversation:', error);
    res.status(500).json({ error: 'Failed to create conversation' });
  }
});

// Get a specific conversation
app.get('/api/conversations/:id', async (req, res) => {
  try {
    const conversation = await storage.getConversation(req.params.id);
    if (!conversation) {
      return res.status(404).json({ error: 'Conversation not found' });
    }
    res.json(conversation);
  } catch (error) {
    console.error('Error getting conversation:', error);
    res.status(500).json({ error: 'Failed to get conversation' });
  }
});

// Send a message (non-streaming)
app.post('/api/conversations/:id/message', async (req, res) => {
  try {
    const { content } = req.body;
    if (!content || typeof content !== 'string') {
      return res.status(400).json({ error: 'Content is required' });
    }

    const conversation = await storage.getConversation(req.params.id);
    if (!conversation) {
      return res.status(404).json({ error: 'Conversation not found' });
    }

    const isFirstMessage = conversation.messages.length === 0;

    // Add user message
    await storage.addUserMessage(req.params.id, content);

    // Generate title if first message
    if (isFirstMessage) {
      const title = await council.generateConversationTitle(content);
      await storage.updateConversationTitle(req.params.id, title);
    }

    // Run the 3-stage council process
    const result = await council.runFullCouncil(content);

    // Add assistant message
    await storage.addAssistantMessage(
      req.params.id,
      result.stage1,
      result.stage2,
      result.stage3
    );

    // Return the complete response with metadata
    res.json({
      stage1: result.stage1,
      stage2: result.stage2,
      stage3: result.stage3,
      metadata: result.metadata,
    });
  } catch (error) {
    console.error('Error sending message:', error);
    res.status(500).json({ error: 'Failed to send message' });
  }
});

// Send a message (streaming)
app.post('/api/conversations/:id/message/stream', async (req, res) => {
  try {
    const { content } = req.body;
    if (!content || typeof content !== 'string') {
      return res.status(400).json({ error: 'Content is required' });
    }

    const conversation = await storage.getConversation(req.params.id);
    if (!conversation) {
      return res.status(404).json({ error: 'Conversation not found' });
    }

    const isFirstMessage = conversation.messages.length === 0;

    // Set up SSE
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    const sendEvent = (data: unknown) => {
      res.write(`data: ${JSON.stringify(data)}\n\n`);
    };

    try {
      // Add user message
      await storage.addUserMessage(req.params.id, content);

      // Start title generation in parallel (don't await yet)
      const titlePromise = isFirstMessage
        ? council.generateConversationTitle(content)
        : null;

      // Stage 1: Collect responses
      sendEvent({ type: 'stage1_start' });
      const stage1Results = await council.stage1CollectResponses(content);
      sendEvent({ type: 'stage1_complete', data: stage1Results });

      // Stage 2: Collect rankings
      sendEvent({ type: 'stage2_start' });
      const { rankings: stage2Results, labelToModel } =
        await council.stage2CollectRankings(content, stage1Results);
      const aggregateRankings = council.calculateAggregateRankings(
        stage2Results,
        labelToModel
      );
      sendEvent({
        type: 'stage2_complete',
        data: stage2Results,
        metadata: {
          label_to_model: labelToModel,
          aggregate_rankings: aggregateRankings,
        },
      });

      // Stage 3: Synthesize final answer
      sendEvent({ type: 'stage3_start' });
      const stage3Result = await council.stage3SynthesizeFinal(
        content,
        stage1Results,
        stage2Results
      );
      sendEvent({ type: 'stage3_complete', data: stage3Result });

      // Wait for title generation if it was started
      if (titlePromise) {
        const title = await titlePromise;
        await storage.updateConversationTitle(req.params.id, title);
        sendEvent({ type: 'title_complete', data: { title } });
      }

      // Save complete assistant message
      await storage.addAssistantMessage(
        req.params.id,
        stage1Results,
        stage2Results,
        stage3Result
      );

      // Send completion event
      sendEvent({ type: 'complete' });
      res.end();
    } catch (error) {
      sendEvent({ type: 'error', message: String(error) });
      res.end();
    }
  } catch (error) {
    console.error('Error in streaming endpoint:', error);
    res.status(500).json({ error: 'Failed to send message' });
  }
});

// Start server
app.listen(config.port, () => {
  console.log(`🚀 LLM Council server running on port ${config.port}`);
  console.log(`📡 API available at http://localhost:${config.port}`);
});
