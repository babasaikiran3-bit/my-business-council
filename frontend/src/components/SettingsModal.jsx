import { useState, useEffect, useCallback } from 'react';
import { api } from '../api';
import './SettingsModal.css';

const DEFAULT_MODELS = [
  'openai/gpt-5.1',
  'openai/gpt-4.1',
  'openai/gpt-4.1-mini',
  'openai/o3',
  'openai/o4-mini',
  'google/gemini-3-pro-preview',
  'google/gemini-2.5-pro-preview',
  'google/gemini-2.5-flash',
  'anthropic/claude-sonnet-4.5',
  'anthropic/claude-sonnet-4',
  'anthropic/claude-3.5-sonnet',
  'x-ai/grok-4',
  'x-ai/grok-3',
  'meta-llama/llama-4-maverick',
  'meta-llama/llama-3.3-70b-instruct',
  'deepseek/deepseek-r1',
  'deepseek/deepseek-chat-v3',
];

export default function SettingsModal({ isOpen, onClose, onSettingsChange }) {
  const [activeTab, setActiveTab] = useState('models');
  const [councilModels, setCouncilModels] = useState([]);
  const [chairmanModel, setChairmanModel] = useState('');
  const [showCost, setShowCost] = useState(true);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [newModel, setNewModel] = useState('');
  const [customModels, setCustomModels] = useState([]);
  const [verifying, setVerifying] = useState(false);
  const [verifyError, setVerifyError] = useState('');
  const [modelHealth, setModelHealth] = useState({}); // {modelId: 'healthy' | 'unhealthy' | 'checking'}
  
  // Combined list: default + custom models (sorted)
  const availableModels = [...new Set([...DEFAULT_MODELS, ...customModels])].sort();

  // Save health status to localStorage when it changes
  const updateHealthStatus = useCallback((updates) => {
    setModelHealth(prev => {
      const newHealth = { ...prev, ...updates };
      // Filter out 'checking' status before saving
      const toSave = {};
      Object.entries(newHealth).forEach(([k, v]) => {
        if (v !== 'checking') toSave[k] = v;
      });
      localStorage.setItem('modelHealth', JSON.stringify(toSave));
      return newHealth;
    });
  }, []);

  const checkSingleModelHealth = useCallback(async (model) => {
    setModelHealth(prev => ({ ...prev, [model]: 'checking' }));
    try {
      const result = await api.verifyModel(model);
      updateHealthStatus({ [model]: result.valid ? 'healthy' : 'unhealthy' });
    } catch {
      updateHealthStatus({ [model]: 'unhealthy' });
    }
  }, [updateHealthStatus]);

  const checkModelHealth = useCallback(async (models) => {
    if (!models || models.length === 0) return;
    
    // Set all to checking
    const initialHealth = {};
    models.forEach(m => { initialHealth[m] = 'checking'; });
    setModelHealth(prev => ({ ...prev, ...initialHealth }));
    
    // Check all models in parallel
    const results = await Promise.all(
      models.map(async (model) => {
        try {
          const result = await api.verifyModel(model);
          return { model, status: result.valid ? 'healthy' : 'unhealthy' };
        } catch {
          return { model, status: 'unhealthy' };
        }
      })
    );
    
    // Update health status and save to localStorage
    const healthMap = {};
    results.forEach(r => { healthMap[r.model] = r.status; });
    updateHealthStatus(healthMap);
  }, [updateHealthStatus]);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const config = await api.getCouncilConfig();
      setCouncilModels(config.council_models || []);
      setChairmanModel(config.chairman_model || '');
      setCustomModels(config.custom_models || []);
      
      // Load UI preferences from localStorage
      const savedShowCost = localStorage.getItem('showCost');
      setShowCost(savedShowCost !== 'false');
      
      // Load saved health status
      const savedHealth = localStorage.getItem('modelHealth');
      if (savedHealth) {
        try {
          setModelHealth(JSON.parse(savedHealth));
        } catch {}
      }
    } catch (error) {
      console.error('Failed to load config:', error);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadConfig();
    }
  }, [isOpen, loadConfig]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.updateCouncilConfig({
        council_models: councilModels,
        chairman_model: chairmanModel,
        custom_models: customModels,
      });
      // Save UI preference to localStorage
      localStorage.setItem('showCost', showCost.toString());
      // Notify parent about settings change
      if (onSettingsChange) {
        onSettingsChange({ showCost });
      }
      onClose();
    } catch (error) {
      console.error('Failed to save config:', error);
      alert('Failed to save configuration');
    }
    setSaving(false);
  };

  const handleAddModel = async () => {
    const modelToAdd = newModel.trim();
    if (!modelToAdd) return;
    
    // Check if already in list
    if (DEFAULT_MODELS.includes(modelToAdd) || customModels.includes(modelToAdd)) {
      setVerifyError('Model already in list');
      return;
    }
    
    // Verify model is callable
    setVerifying(true);
    setVerifyError('');
    
    try {
      const result = await api.verifyModel(modelToAdd);
      
      if (result.valid) {
        const newCustomModels = [...customModels, modelToAdd];
        setCustomModels(newCustomModels);
        setNewModel('');
        setVerifyError('');
        
        // Set health status to healthy (just verified)
        setModelHealth(prev => ({ ...prev, [modelToAdd]: 'healthy' }));
        
        // Save to backend immediately
        await api.updateCouncilConfig({
          custom_models: newCustomModels,
        });
      } else {
        setVerifyError(result.error || 'Model verification failed');
      }
    } catch (error) {
      setVerifyError('Failed to verify model. Check your connection.');
    }
    
    setVerifying(false);
  };

  const handleRemoveModel = (model) => {
    setCouncilModels(councilModels.filter(m => m !== model));
  };

  const handleRemoveCustomModel = async (model) => {
    const newCustomModels = customModels.filter(m => m !== model);
    setCustomModels(newCustomModels);
    
    // Also remove from council if present
    const newCouncilModels = councilModels.filter(m => m !== model);
    setCouncilModels(newCouncilModels);
    
    // Reset chairman if it was this model
    if (chairmanModel === model) {
      setChairmanModel('');
    }
    
    // Save to backend immediately
    await api.updateCouncilConfig({
      custom_models: newCustomModels,
    });
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Settings</h2>
          <button className="close-button" onClick={onClose}>&times;</button>
        </div>

        {/* Tab Navigation */}
        <div className="modal-tabs">
          <button 
            className={`tab-btn ${activeTab === 'models' ? 'active' : ''}`}
            onClick={() => setActiveTab('models')}
          >
            Custom Models
          </button>
          <button 
            className={`tab-btn ${activeTab === 'council' ? 'active' : ''}`}
            onClick={() => setActiveTab('council')}
          >
            Council Config
          </button>
          <button 
            className={`tab-btn ${activeTab === 'display' ? 'active' : ''}`}
            onClick={() => setActiveTab('display')}
          >
            Display
          </button>
        </div>

        {loading ? (
          <div className="modal-loading">Loading...</div>
        ) : (
          <div className="modal-body">
            {/* Tab: Custom Models */}
            {activeTab === 'models' && (
              <>
                <div className="setting-group">
                  <label>Add Custom Model</label>
                  <p className="setting-description">
                    Add models (especially free ones) to the list. Find model IDs at{' '}
                    <a href="https://openrouter.ai/models?q=:free" target="_blank" rel="noopener noreferrer">openrouter.ai/models</a>
                  </p>
                  <div className="add-model">
                    <input
                      type="text"
                      placeholder="e.g. google/gemma-3n-e4b-it:free"
                      value={newModel}
                      onChange={e => {
                        setNewModel(e.target.value);
                        setVerifyError('');
                      }}
                      onKeyDown={e => e.key === 'Enter' && !verifying && handleAddModel()}
                      disabled={verifying}
                    />
                    <button 
                      onClick={handleAddModel} 
                      disabled={!newModel.trim() || verifying}
                    >
                      {verifying ? 'Verifying...' : 'Add'}
                    </button>
                  </div>
                  {verifyError && (
                    <p className="verify-error">{verifyError}</p>
                  )}
                </div>

                {customModels.length > 0 && (
                  <div className="setting-group">
                    <label>
                      Your Custom Models
                      <button 
                        className="check-health-btn"
                        onClick={() => checkModelHealth(customModels)}
                        disabled={Object.values(modelHealth).some(s => s === 'checking')}
                      >
                        {Object.values(modelHealth).some(s => s === 'checking') ? 'Checking...' : 'Check Availability'}
                      </button>
                    </label>
                    <p className="setting-description">
                      Verify all models at once or check individually with ↻ button.
                    </p>
                    <div className="custom-models-grid">
                      {customModels.map((model, idx) => (
                        <div 
                          key={idx} 
                          className={`custom-model-item ${modelHealth[model] === 'unhealthy' ? 'unhealthy' : ''}`}
                        >
                          <span className={`health-indicator ${modelHealth[model] || 'unknown'}`} />
                          <span className="model-name" title={model}>{model}</span>
                          <div className="model-actions">
                            <button 
                              className="refresh-single-btn"
                              onClick={() => checkSingleModelHealth(model)}
                              disabled={modelHealth[model] === 'checking'}
                              title="Check availability"
                            >
                              ↻
                            </button>
                            <button 
                              className="remove-tag-btn"
                              onClick={() => handleRemoveCustomModel(model)}
                              title="Remove"
                            >
                              &times;
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="health-legend">
                      <span><span className="health-indicator healthy" /> Available</span>
                      <span><span className="health-indicator unhealthy" /> Unavailable</span>
                      <span><span className="health-indicator unknown" /> Not checked</span>
                    </div>
                  </div>
                )}

                {customModels.length === 0 && (
                  <div className="empty-state">
                    No custom models added yet. Add free models from OpenRouter to use them in your council.
                  </div>
                )}
              </>
            )}

            {/* Tab: Council Config */}
            {activeTab === 'council' && (
              <>
                <div className="setting-group">
                  <label>Council Members</label>
                  <p className="setting-description">
                    Models that will respond to queries and rank each other.
                  </p>
                  
                  <div className="model-list">
                    {councilModels.map((model, idx) => (
                      <div key={idx} className="model-item">
                        <span>{model}</span>
                        <button 
                          className="remove-model-btn"
                          onClick={() => handleRemoveModel(model)}
                        >
                          &times;
                        </button>
                      </div>
                    ))}
                    {councilModels.length === 0 && (
                      <div className="empty-list">No council members selected</div>
                    )}
                  </div>

                  <div className="add-model">
                    <select 
                      value=""
                      onChange={e => {
                        if (e.target.value && !councilModels.includes(e.target.value)) {
                          setCouncilModels([...councilModels, e.target.value]);
                        }
                      }}
                    >
                      <option value="">Add model to council...</option>
                      {availableModels.filter(m => !councilModels.includes(m)).map(model => (
                        <option key={model} value={model}>{model}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="setting-group">
                  <label>Chairman Model</label>
                  <p className="setting-description">
                    The model that synthesizes the final response from all council inputs.
                  </p>
                  <select 
                    value={chairmanModel}
                    onChange={e => setChairmanModel(e.target.value)}
                    className="chairman-select"
                  >
                    <option value="">Select chairman...</option>
                    {availableModels.map(model => (
                      <option key={model} value={model}>{model}</option>
                    ))}
                  </select>
                </div>
              </>
            )}

            {/* Tab: Display */}
            {activeTab === 'display' && (
              <div className="setting-group">
                <label>Display Options</label>
                <div className="checkbox-option">
                  <input
                    type="checkbox"
                    id="showCost"
                    checked={showCost}
                    onChange={e => setShowCost(e.target.checked)}
                  />
                  <label htmlFor="showCost">Show cost information</label>
                </div>
                <p className="setting-description">
                  Show or hide cost details in conversations and sidebar.
                </p>
              </div>
            )}
          </div>
        )}

        <div className="modal-footer">
          <button className="cancel-btn" onClick={onClose}>Cancel</button>
          <button 
            className="save-btn" 
            onClick={handleSave}
            disabled={saving || councilModels.length === 0}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
