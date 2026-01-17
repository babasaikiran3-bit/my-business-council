import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../api';
import './Search.css';

export default function Search({ isOpen, onClose, onSelectConversation }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);
  const resultsRef = useRef(null);
  const debounceRef = useRef(null);

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
      setQuery('');
      setResults([]);
      setSelectedIndex(0);
    }
  }, [isOpen]);

  // Debounced search
  const performSearch = useCallback(async (searchQuery) => {
    if (!searchQuery.trim()) {
      setResults([]);
      return;
    }

    setIsLoading(true);
    try {
      const response = await api.search(searchQuery);
      setResults(response.results || []);
      setSelectedIndex(0);
    } catch (error) {
      console.error('Search failed:', error);
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Handle input change with debounce
  const handleInputChange = (e) => {
    const value = e.target.value;
    setQuery(value);

    // Clear previous debounce
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    // Debounce search
    debounceRef.current = setTimeout(() => {
      performSearch(value);
    }, 300);
  };

  // Handle keyboard navigation
  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      onClose();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.min(prev + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter' && results.length > 0) {
      e.preventDefault();
      handleSelectResult(results[selectedIndex]);
    }
  };

  // Scroll selected result into view
  useEffect(() => {
    if (resultsRef.current && results.length > 0) {
      const selectedEl = resultsRef.current.children[selectedIndex];
      if (selectedEl) {
        selectedEl.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [selectedIndex, results.length]);

  // Handle result selection
  const handleSelectResult = (result) => {
    onSelectConversation(result.conversation_id);
    onClose();
  };

  // Format date for display
  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: date.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined,
      });
    } catch {
      return '';
    }
  };

  if (!isOpen) return null;

  return (
    <div className="search-overlay" onClick={onClose}>
      <div className="search-modal" onClick={(e) => e.stopPropagation()}>
        <div className="search-header">
          <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <path d="M21 21l-4.35-4.35" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            className="search-input"
            placeholder="Search conversations..."
            value={query}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
          />
          <kbd className="search-shortcut">esc</kbd>
        </div>

        <div className="search-results" ref={resultsRef}>
          {isLoading && (
            <div className="search-loading">
              <div className="spinner-small"></div>
              <span>Searching...</span>
            </div>
          )}

          {!isLoading && query && results.length === 0 && (
            <div className="search-empty">
              No results found for "{query}"
            </div>
          )}

          {!isLoading && results.map((result, index) => (
            <div
              key={`${result.conversation_id}-${result.message_id || 'title'}-${index}`}
              className={`search-result ${index === selectedIndex ? 'selected' : ''}`}
              onClick={() => handleSelectResult(result)}
              onMouseEnter={() => setSelectedIndex(index)}
            >
              <div className="search-result-header">
                <span className="search-result-title">{result.conversation_title}</span>
                <span className="search-result-date">{formatDate(result.created_at)}</span>
              </div>
              <div
                className="search-result-snippet"
                dangerouslySetInnerHTML={{ __html: result.snippet }}
              />
              <div className="search-result-meta">
                <span className={`search-result-role ${result.role}`}>
                  {result.role === 'user' ? 'Question' : result.role === 'assistant' ? 'Answer' : 'Title'}
                </span>
              </div>
            </div>
          ))}

          {!isLoading && !query && (
            <div className="search-hint">
              Type to search across all your conversations
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
