import { describe, it, expect } from 'vitest';
import { councilReducer, createAssistantMessage } from './councilReducer';

const msg = () => createAssistantMessage();

describe('createAssistantMessage', () => {
  it('returns a fresh object each call', () => {
    const a = createAssistantMessage();
    const b = createAssistantMessage();
    expect(a).not.toBe(b);
    expect(a).toEqual(b);
  });

  it('has the expected shape', () => {
    const m = createAssistantMessage();
    expect(m.role).toBe('assistant');
    expect(m.live).toEqual({});
    expect(m.stage).toBeNull();
    expect(m.stage1).toBeNull();
    expect(m.stage2).toBeNull();
    expect(m.stage3).toBeNull();
    expect(m.metadata).toBeNull();
    expect(m.research).toBeNull();
  });
});

describe('councilReducer', () => {
  it('returns same state for unknown action', () => {
    const m = msg();
    expect(councilReducer(m, { type: 'UNKNOWN' })).toBe(m);
  });

  // ── STAGE ─────────────────────────────────────────────────────────
  describe('STAGE', () => {
    it('sets the stage', () => {
      const m = msg();
      const n = councilReducer(m, { type: 'STAGE', stage: 'research' });
      expect(n.stage).toBe('research');
      expect(n).not.toBe(m);
    });

    it('overwrites previous stage', () => {
      const m = { ...msg(), stage: 'research' };
      const n = councilReducer(m, { type: 'STAGE', stage: 'stage1' });
      expect(n.stage).toBe('stage1');
    });
  });

  // ── AGENT ─────────────────────────────────────────────────────────
  describe('AGENT', () => {
    it('adds live entry for a model', () => {
      const m = msg();
      const n = councilReducer(m, {
        type: 'AGENT',
        model: 'gpt-5',
        status: 'thinking',
        reason: 'analysing',
      });
      expect(n.live['gpt-5']).toEqual({
        status: 'thinking',
        reason: 'analysing',
      });
    });

    it('merges with existing live entry', () => {
      const m = {
        ...msg(),
        live: { 'gpt-5': { status: 'connecting', tool: 'read' } },
      };
      const n = councilReducer(m, {
        type: 'AGENT',
        model: 'gpt-5',
        status: 'thinking',
        reason: 'analysing',
      });
      expect(n.live['gpt-5']).toEqual({
        status: 'thinking',
        reason: 'analysing',
        tool: 'read',
      });
    });

    it('preserves other models', () => {
      const m = {
        ...msg(),
        live: { 'claude': { status: 'working' } },
      };
      const n = councilReducer(m, {
        type: 'AGENT',
        model: 'gpt-5',
        status: 'thinking',
        reason: null,
      });
      expect(n.live['claude']).toEqual({ status: 'working' });
      expect(n.live['gpt-5']).toEqual({
        status: 'thinking',
        reason: null,
      });
    });
  });

  // ── TOOL ──────────────────────────────────────────────────────────
  describe('TOOL', () => {
    it('replaces model entry with tool info', () => {
      const m = {
        ...msg(),
        live: { 'gpt-5': { status: 'thinking', reason: 'x' } },
      };
      const n = councilReducer(m, {
        type: 'TOOL',
        model: 'gpt-5',
        tool: 'read_file',
        detail: 'foo.py',
      });
      expect(n.live['gpt-5']).toEqual({
        status: 'working',
        tool: 'read_file',
        detail: 'foo.py',
      });
    });
  });

  // ── THOUGHT ───────────────────────────────────────────────────────
  describe('THOUGHT', () => {
    it('replaces model entry with thought', () => {
      const m = msg();
      const n = councilReducer(m, {
        type: 'THOUGHT',
        model: 'claude',
        text: 'Let me think...',
      });
      expect(n.live['claude']).toEqual({
        status: 'working',
        thought: 'Let me think...',
      });
    });
  });

  // ── RESULT ────────────────────────────────────────────────────────
  describe('RESULT', () => {
    it('appends first result', () => {
      const m = msg();
      const n = councilReducer(m, {
        type: 'RESULT',
        model: 'gpt-5',
        text: 'The answer is 42.',
      });
      expect(n.stage1).toEqual([
        { model: 'gpt-5', response: 'The answer is 42.' },
      ]);
    });

    it('replaces existing result for same model', () => {
      const m = {
        ...msg(),
        stage1: [{ model: 'gpt-5', response: 'old' }],
      };
      const n = councilReducer(m, {
        type: 'RESULT',
        model: 'gpt-5',
        text: 'new',
      });
      expect(n.stage1).toEqual([
        { model: 'gpt-5', response: 'new' },
      ]);
    });

    it('accumulates results from different models', () => {
      const m = {
        ...msg(),
        stage1: [{ model: 'gpt-5', response: 'a' }],
      };
      const n = councilReducer(m, {
        type: 'RESULT',
        model: 'claude',
        text: 'b',
      });
      expect(n.stage1).toEqual([
        { model: 'gpt-5', response: 'a' },
        { model: 'claude', response: 'b' },
      ]);
    });
  });

  // ── RESEARCH ──────────────────────────────────────────────────────
  describe('RESEARCH', () => {
    it('sets research and clears live', () => {
      const m = {
        ...msg(),
        live: { 'claude': { status: 'working' } },
      };
      const n = councilReducer(m, {
        type: 'RESEARCH',
        model: 'claude',
        brief: 'Found 3 files.',
      });
      expect(n.research).toEqual({
        model: 'claude',
        brief: 'Found 3 files.',
      });
      expect(n.live).toEqual({});
    });
  });

  // ── RANKING ───────────────────────────────────────────────────────
  describe('RANKING', () => {
    it('sets aggregate_rankings in metadata', () => {
      const m = msg();
      const rankings = [{ model: 'gpt-5', avg_position: 1.0 }];
      const n = councilReducer(m, { type: 'RANKING', aggregate: rankings });
      expect(n.metadata).toEqual({ aggregate_rankings: rankings });
    });

    it('preserves existing metadata', () => {
      const m = { ...msg(), metadata: { label_to_model: { A: 'gpt-5' } } };
      const rankings = [{ model: 'gpt-5', avg_position: 1.0 }];
      const n = councilReducer(m, { type: 'RANKING', aggregate: rankings });
      expect(n.metadata).toEqual({
        label_to_model: { A: 'gpt-5' },
        aggregate_rankings: rankings,
      });
    });
  });

  // ── METADATA ──────────────────────────────────────────────────────
  describe('METADATA', () => {
    it('merges metadata', () => {
      const m = { ...msg(), metadata: { existing: true } };
      const n = councilReducer(m, {
        type: 'METADATA',
        metadata: { newKey: 'value' },
      });
      expect(n.metadata).toEqual({ existing: true, newKey: 'value' });
    });

    it('handles null initial metadata', () => {
      const m = msg();
      const n = councilReducer(m, {
        type: 'METADATA',
        metadata: { key: 'val' },
      });
      expect(n.metadata).toEqual({ key: 'val' });
    });
  });

  // ── CONSENSUS_FILE ────────────────────────────────────────────────
  describe('CONSENSUS_FILE', () => {
    it('sets consensusFile path', () => {
      const m = msg();
      const n = councilReducer(m, {
        type: 'CONSENSUS_FILE',
        path: '/tmp/consensus.md',
      });
      expect(n.consensusFile).toBe('/tmp/consensus.md');
    });
  });

  // ── FINAL ─────────────────────────────────────────────────────────
  describe('FINAL', () => {
    it('sets stage3', () => {
      const m = msg();
      const n = councilReducer(m, {
        type: 'FINAL',
        model: 'gemini',
        text: '# Final Answer\n\nHello.',
      });
      expect(n.stage3).toEqual({
        model: 'gemini',
        response: '# Final Answer\n\nHello.',
      });
    });
  });

  // ── DONE ──────────────────────────────────────────────────────────
  describe('DONE', () => {
    it('sets all final fields and clears stage/live', () => {
      const m = {
        ...msg(),
        stage: 'stage3',
        live: { 'gpt-5': { status: 'working' } },
      };
      const n = councilReducer(m, {
        type: 'DONE',
        stage1: [{ model: 'gpt-5', response: 'x' }],
        stage2: [{ model: 'gpt-5', evaluation: 'good' }],
        stage3: { model: 'gemini', response: 'final' },
        metadata: { aggregate_rankings: [] },
      });
      expect(n.stage1).toEqual([{ model: 'gpt-5', response: 'x' }]);
      expect(n.stage2).toEqual([{ model: 'gpt-5', evaluation: 'good' }]);
      expect(n.stage3).toEqual({ model: 'gemini', response: 'final' });
      expect(n.metadata).toEqual({ aggregate_rankings: [] });
      expect(n.stage).toBeNull();
      expect(n.live).toEqual({});
    });

    it('updates research from metadata if present', () => {
      const m = { ...msg(), research: { model: 'old', brief: 'old' } };
      const n = councilReducer(m, {
        type: 'DONE',
        stage1: [],
        stage2: [],
        stage3: null,
        metadata: { research: { model: 'claude', brief: 'new' } },
      });
      expect(n.research).toEqual({ model: 'claude', brief: 'new' });
    });

    it('keeps existing research if metadata has none', () => {
      const m = { ...msg(), research: { model: 'claude', brief: 'keep' } };
      const n = councilReducer(m, {
        type: 'DONE',
        stage1: [],
        stage2: [],
        stage3: null,
        metadata: {},
      });
      expect(n.research).toEqual({ model: 'claude', brief: 'keep' });
    });
  });

  // ── FATAL ─────────────────────────────────────────────────────────
  describe('FATAL', () => {
    it('sets error and clears stage', () => {
      const m = { ...msg(), stage: 'stage1' };
      const n = councilReducer(m, {
        type: 'FATAL',
        message: 'connection lost',
      });
      expect(n.error).toBe('connection lost');
      expect(n.stage).toBeNull();
    });
  });

  // ── ERROR ─────────────────────────────────────────────────────────
  describe('ERROR', () => {
    it('sets error on message', () => {
      const m = msg();
      const n = councilReducer(m, {
        type: 'ERROR',
        message: 'something went wrong',
      });
      expect(n.error).toBe('something went wrong');
    });
  });

  // ── Sequence tests ────────────────────────────────────────────────
  describe('sequences', () => {
    it('handles a full normal pipeline', () => {
      let m = msg();

      m = councilReducer(m, { type: 'STAGE', stage: 'research' });
      m = councilReducer(m, {
        type: 'AGENT',
        model: 'claude',
        status: 'thinking',
        reason: 'researching',
      });
      m = councilReducer(m, {
        type: 'TOOL',
        model: 'claude',
        tool: 'grep',
        detail: 'searching...',
      });
      m = councilReducer(m, {
        type: 'RESEARCH',
        model: 'claude',
        brief: 'Found relevant code.',
      });

      m = councilReducer(m, { type: 'STAGE', stage: 'stage1' });
      m = councilReducer(m, {
        type: 'AGENT',
        model: 'gpt-5',
        status: 'thinking',
        reason: 'deliberating',
      });
      m = councilReducer(m, {
        type: 'RESULT',
        model: 'gpt-5',
        text: 'Answer from gpt-5',
      });
      m = councilReducer(m, {
        type: 'AGENT',
        model: 'claude',
        status: 'thinking',
        reason: 'deliberating',
      });
      m = councilReducer(m, {
        type: 'RESULT',
        model: 'claude',
        text: 'Answer from claude',
      });

      m = councilReducer(m, { type: 'STAGE', stage: 'stage2' });
      m = councilReducer(m, {
        type: 'RANKING',
        aggregate: [{ model: 'gpt-5', avg_position: 1.0 }],
      });
      m = councilReducer(m, {
        type: 'METADATA',
        metadata: { label_to_model: { A: 'gpt-5' } },
      });

      m = councilReducer(m, { type: 'STAGE', stage: 'stage3' });
      m = councilReducer(m, {
        type: 'FINAL',
        model: 'gemini',
        text: '# Synthesised answer',
      });

      m = councilReducer(m, {
        type: 'DONE',
        stage1: m.stage1,
        stage2: m.stage2,
        stage3: m.stage3,
        metadata: m.metadata,
      });

      expect(m.stage1).toHaveLength(2);
      expect(m.stage2).toBeDefined();
      expect(m.stage3).toBeDefined();
      expect(m.metadata).toBeDefined();
      expect(m.stage).toBeNull();
      expect(m.live).toEqual({});
      expect(m.research).toBeDefined();
    });

    it('handles a fatal error mid-stream', () => {
      let m = msg();
      m = councilReducer(m, { type: 'STAGE', stage: 'stage1' });
      m = councilReducer(m, {
        type: 'AGENT',
        model: 'gpt-5',
        status: 'thinking',
        reason: null,
      });
      m = councilReducer(m, {
        type: 'RESULT',
        model: 'gpt-5',
        text: 'partial',
      });
      m = councilReducer(m, {
        type: 'FATAL',
        message: 'upstream timeout',
      });

      expect(m.error).toBe('upstream timeout');
      expect(m.stage).toBeNull();
      expect(m.stage1).toEqual([
        { model: 'gpt-5', response: 'partial' },
      ]);
      // live is preserved so the UI can show what was happening
      expect(m.live['gpt-5']).toBeDefined();
    });

    it('handles empty partial stream gracefully', () => {
      let m = msg();
      m = councilReducer(m, {
        type: 'DONE',
        stage1: [],
        stage2: [],
        stage3: null,
        metadata: {},
      });
      expect(m.stage1).toEqual([]);
      expect(m.stage2).toEqual([]);
      expect(m.stage3).toBeNull();
      expect(m.error).toBeUndefined();
    });
  });
});
