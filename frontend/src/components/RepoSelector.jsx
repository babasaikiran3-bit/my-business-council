import { useState, useEffect, useRef } from 'react';
import { api } from '../api';
import FileUploader from './FileUploader';
import './RepoSelector.css';

export default function RepoSelector({ conversationId, onReposChanged, onFilesChanged }) {
  const [isOpen, setIsOpen] = useState(false);
  const [githubRepos, setGithubRepos] = useState([]);
  const [attachedRepos, setAttachedRepos] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const dropdownRef = useRef(null);

  // Load GitHub repos when dropdown opens
  useEffect(() => {
    if (isOpen && githubRepos.length === 0) {
      loadGithubRepos();
    }
  }, [isOpen]);

  // Load attached repos when conversation changes
  useEffect(() => {
    if (conversationId) {
      loadAttachedRepos();
    }
  }, [conversationId]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  const loadGithubRepos = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listGithubRepos();
      if (data.error) {
        setError(data.error);
      } else {
        setGithubRepos(data.repos || []);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadAttachedRepos = async () => {
    try {
      const data = await api.listConversationRepos(conversationId);
      setAttachedRepos(data.repos || []);
      if (onReposChanged) {
        onReposChanged(data.repos || []);
      }
    } catch (err) {
      console.error('Failed to load attached repos:', err);
    }
  };

  const handleToggleRepo = async (repo) => {
    const isAttached = attachedRepos.some((r) => r.full_name === repo.full_name);

    try {
      if (isAttached) {
        // Detach
        await api.detachRepo(conversationId, repo.full_name);
      } else {
        // Attach
        await api.attachRepo(conversationId, repo.full_name);
      }
      // Reload attached repos
      await loadAttachedRepos();
    } catch (err) {
      console.error('Failed to toggle repo:', err);
      setError(err.message);
    }
  };

  const isRepoAttached = (repoFullName) => {
    return attachedRepos.some((r) => r.full_name === repoFullName);
  };

  return (
    <div className="repo-selector" ref={dropdownRef}>
      <button
        className="add-context-button"
        onClick={() => setIsOpen(!isOpen)}
        disabled={!conversationId}
        title={conversationId ? 'Add context from GitHub repos' : 'Create a conversation first'}
      >
        <span className="add-icon">+</span>
        Add Context
        <span className={`dropdown-icon ${isOpen ? 'open' : ''}`}>▼</span>
      </button>

      {isOpen && (
        <div className="context-dropdown">
          <div className="dropdown-section">
            <div className="section-header">
              <span className="github-icon">🐙</span>
              <span>GitHub Repositories</span>
            </div>

            {error && (
              <div className="error-message">
                {error}
                {error.includes('not configured') && (
                  <div className="config-help">
                    Set GITHUB_TOKEN in your .env file
                  </div>
                )}
              </div>
            )}

            {loading && (
              <div className="loading-message">Loading repositories...</div>
            )}

            {!loading && !error && githubRepos.length === 0 && (
              <div className="empty-message">No repositories found</div>
            )}

            {!loading && githubRepos.length > 0 && (
              <div className="repo-list">
                {githubRepos.map((repo) => (
                  <div
                    key={repo.full_name}
                    className={`repo-item ${isRepoAttached(repo.full_name) ? 'attached' : ''}`}
                    onClick={() => handleToggleRepo(repo)}
                  >
                    <input
                      type="checkbox"
                      checked={isRepoAttached(repo.full_name)}
                      onChange={() => {}}
                      className="repo-checkbox"
                    />
                    <div className="repo-info">
                      <div className="repo-name">{repo.name}</div>
                      {repo.description && (
                        <div className="repo-description">{repo.description}</div>
                      )}
                      <div className="repo-meta">
                        {repo.language && (
                          <span className="repo-language">{repo.language}</span>
                        )}
                        {repo.stars > 0 && (
                          <span className="repo-stars">⭐ {repo.stars}</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <FileUploader
            conversationId={conversationId}
            onFilesChanged={onFilesChanged}
          />
        </div>
      )}
    </div>
  );
}
