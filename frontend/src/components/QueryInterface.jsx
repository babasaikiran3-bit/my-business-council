import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { api } from '../api';
import './QueryInterface.css';

function shortModelName(model) {
  // "openai/gpt-5.1" -> "GPT-5.1 (OpenAI)"
  const [provider, ...rest] = model.split('/');
  const name = rest.join('/');
  const providerMap = {
    openai: 'OpenAI',
    anthropic: 'Anthropic',
    google: 'Google',
    'x-ai': 'xAI',
    meta: 'Meta',
    mistral: 'Mistral',
    cohere: 'Cohere',
  };
  const providerLabel = providerMap[provider] || provider;
  return { label: name, provider: providerLabel };
}

export default function QueryInterface() {
  const [availableModels, setAvailableModels] = useState([]);
  const [selectedModels, setSelectedModels] = useState([]);
  const [synthesize, setSynthesize] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [responses, setResponses] = useState([]);
  const [synthesis, setSynthesis] = useState(null);
  const [loadingResponses, setLoadingResponses] = useState(false);
  const [loadingSynthesis, setLoadingSynthesis] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getModels().then((data) => {
      setAvailableModels(data.council_models);
      setSelectedModels(data.council_models); // select all by default
    }).catch(() => setError('Failed to load models'));
  }, []);

  const toggleModel = (model) => {
    setSelectedModels((prev) =>
      prev.includes(model) ? prev.filter((m) => m !== model) : [...prev, model]
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!prompt.trim() || selectedModels.length === 0 || loadingResponses) return;

    setError(null);
    setResponses([]);
    setSynthesis(null);
    setLoadingResponses(true);
    setLoadingSynthesis(false);

    try {
      await api.simpleQueryStream(prompt, selectedModels, synthesize, (type, event) => {
        switch (type) {
          case 'responses_complete':
            setResponses(event.data);
            setLoadingResponses(false);
            break;
          case 'synthesis_start':
            setLoadingSynthesis(true);
            break;
          case 'synthesis_complete':
            setSynthesis({ model: event.model, content: event.content });
            setLoadingSynthesis(false);
            break;
          case 'error':
            setError(event.message);
            setLoadingResponses(false);
            setLoadingSynthesis(false);
            break;
          default:
            break;
        }
      });
    } catch (err) {
      setError(err.message);
      setLoadingResponses(false);
      setLoadingSynthesis(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const isLoading = loadingResponses || loadingSynthesis;
  const hasResults = responses.length > 0;

  return (
    <div className="query-interface">
      <div className="query-form-panel">
        <h2 className="query-title">Multi-Model Query</h2>
        <p className="query-subtitle">
          Select models, ask a question, and compare answers side by side.
        </p>

        <form onSubmit={handleSubmit}>
          <div className="model-selector">
            <div className="model-selector-header">
              <span className="selector-label">Models</span>
              <div className="selector-actions">
                <button type="button" className="link-btn" onClick={() => setSelectedModels(availableModels)}>All</button>
                <span className="separator">·</span>
                <button type="button" className="link-btn" onClick={() => setSelectedModels([])}>None</button>
              </div>
            </div>
            <div className="model-checkboxes">
              {availableModels.map((model) => {
                const { label, provider } = shortModelName(model);
                const checked = selectedModels.includes(model);
                return (
                  <label key={model} className={`model-checkbox ${checked ? 'checked' : ''}`}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleModel(model)}
                    />
                    <span className="model-checkbox-name">{label}</span>
                    <span className="model-checkbox-provider">{provider}</span>
                  </label>
                );
              })}
            </div>
          </div>

          <div className="synthesis-toggle">
            <label className={`toggle-label ${synthesize ? 'on' : ''}`}>
              <input
                type="checkbox"
                checked={synthesize}
                onChange={(e) => setSynthesize(e.target.checked)}
              />
              <span className="toggle-switch" />
              <span className="toggle-text">
                Synthesize with Claude
                <span className="toggle-hint"> — get one final answer combining all responses</span>
              </span>
            </label>
          </div>

          <textarea
            className="query-input"
            placeholder="Ask your question... (Enter to send, Shift+Enter for new line)"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            rows={4}
          />

          <button
            type="submit"
            className="query-submit"
            disabled={!prompt.trim() || selectedModels.length === 0 || isLoading}
          >
            {loadingResponses ? 'Querying models...' : loadingSynthesis ? 'Synthesizing...' : 'Ask'}
          </button>
        </form>

        {error && <div className="query-error">{error}</div>}
      </div>

      {(hasResults || loadingResponses) && (
        <div className="query-results">
          {loadingResponses && (
            <div className="responses-loading">
              <div className="spinner" />
              <span>Querying {selectedModels.length} model{selectedModels.length !== 1 ? 's' : ''} in parallel...</span>
            </div>
          )}

          {hasResults && (
            <>
              <div className="responses-grid">
                {responses.map((r) => {
                  const { label, provider } = shortModelName(r.model);
                  return (
                    <div key={r.model} className={`response-card ${r.content ? '' : 'response-card-error'}`}>
                      <div className="response-card-header">
                        <span className="response-model-name">{label}</span>
                        <span className="response-model-provider">{provider}</span>
                      </div>
                      <div className="response-card-body markdown-content">
                        {r.content
                          ? <ReactMarkdown>{r.content}</ReactMarkdown>
                          : <span className="response-failed">Model failed to respond</span>
                        }
                      </div>
                    </div>
                  );
                })}
              </div>

              {loadingSynthesis && (
                <div className="synthesis-loading">
                  <div className="spinner" />
                  <span>Synthesizing answers with Claude...</span>
                </div>
              )}

              {synthesis && (
                <div className="synthesis-result">
                  <div className="synthesis-header">
                    <span className="synthesis-label">Synthesized Answer</span>
                    <span className="synthesis-model">{shortModelName(synthesis.model).label} · {shortModelName(synthesis.model).provider}</span>
                  </div>
                  <div className="synthesis-body markdown-content">
                    <ReactMarkdown>{synthesis.content}</ReactMarkdown>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {!hasResults && !loadingResponses && (
        <div className="query-empty">
          <p>Select models and ask a question to compare their answers.</p>
        </div>
      )}
    </div>
  );
}
