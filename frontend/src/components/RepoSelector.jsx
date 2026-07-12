import { useState, useEffect, useMemo, useRef } from 'react';
import { api } from '../api';
import './RepoSelector.css';

const HISTORY_KEY = 'councilRepoHistory';
const HISTORY_MAX = 8;

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY)) || [];
  } catch {
    return [];
  }
}

function pushHistory(path) {
  if (!path) return loadHistory();
  const hist = [path, ...loadHistory().filter((p) => p !== path)].slice(0, HISTORY_MAX);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(hist));
  return hist;
}

/**
 * Selector de repositorio: botón que abre una pantalla de selección (modal)
 * con buscador, lista de repos autodetectados, recientes y path manual.
 * value/onChange manejan el path actual (string vacío = sin repo).
 */
export default function RepoSelector({ value, onChange }) {
  const [repos, setRepos] = useState([]);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [manual, setManual] = useState('');
  const [history, setHistory] = useState(loadHistory);
  const searchRef = useRef(null);

  const handleOpen = () => {
    setQuery('');
    setManual('');
    setOpen(true);
  };

  useEffect(() => {
    if (!open) return;
    api.fetchRepos()
      .then((data) => setRepos(data.repos || []))
      .catch((e) => console.error('fetchRepos', e));
    // foco al abrir
    setTimeout(() => searchRef.current?.focus(), 50);
  }, [open]);

  // Cerrar con Escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return repos;
    return repos.filter(
      (r) => r.name.toLowerCase().includes(q) || r.path.toLowerCase().includes(q)
    );
  }, [repos, query]);

  const pick = (path) => {
    onChange(path);
    setHistory(pushHistory(path));
    setOpen(false);
  };

  const currentName = value ? value.split('/').filter(Boolean).pop() : null;

  return (
    <div className="repo-selector">
      <button className="repo-trigger" onClick={handleOpen} title={value || 'Sin repo'}>
        <span className="repo-trigger-icon">📁</span>
        {value ? (
          <span className="repo-trigger-name">{currentName}</span>
        ) : (
          <span className="repo-trigger-empty">Elegir repo…</span>
        )}
      </button>

      {open && (
        <div className="repo-modal-overlay" onMouseDown={() => setOpen(false)}>
          <div className="repo-modal" onMouseDown={(e) => e.stopPropagation()}>
            <div className="repo-modal-head">
              <h3>Seleccionar repositorio</h3>
              <button className="repo-modal-close" onClick={() => setOpen(false)}>✕</button>
            </div>

            <input
              ref={searchRef}
              className="repo-search"
              type="text"
              placeholder="Buscar repo por nombre o ruta…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />

            <div className="repo-modal-body">
              {/* Sin repo */}
              <button
                className={`repo-item repo-item-none ${!value ? 'active' : ''}`}
                onClick={() => pick('')}
              >
                <span className="repo-item-icon">💬</span>
                <span className="repo-item-text">
                  <span className="repo-item-name">Sin repo</span>
                  <span className="repo-item-path">Q&amp;A general (el consejo no explora código)</span>
                </span>
              </button>

              {/* Recientes */}
              {history.length > 0 && (
                <>
                  <div className="repo-section-label">Recientes</div>
                  {history.map((p) => (
                    <button
                      key={`hist-${p}`}
                      className={`repo-item ${p === value ? 'active' : ''}`}
                      onClick={() => pick(p)}
                    >
                      <span className="repo-item-icon">🕘</span>
                      <span className="repo-item-text">
                        <span className="repo-item-name">{p.split('/').filter(Boolean).pop()}</span>
                        <span className="repo-item-path">{p}</span>
                      </span>
                    </button>
                  ))}
                </>
              )}

              {/* Detectados */}
              <div className="repo-section-label">
                Detectados {filtered.length > 0 && `(${filtered.length})`}
              </div>
              {filtered.length === 0 ? (
                <div className="repo-empty">Sin coincidencias</div>
              ) : (
                filtered.map((r) => (
                  <button
                    key={r.path}
                    className={`repo-item ${r.path === value ? 'active' : ''}`}
                    onClick={() => pick(r.path)}
                  >
                    <span className="repo-item-icon">📦</span>
                    <span className="repo-item-text">
                      <span className="repo-item-name">{r.name}</span>
                      <span className="repo-item-path">{r.path}</span>
                    </span>
                  </button>
                ))
              )}
            </div>

            {/* Path manual */}
            <form
              className="repo-manual"
              onSubmit={(e) => { e.preventDefault(); if (manual.trim()) pick(manual.trim()); }}
            >
              <input
                className="repo-manual-input"
                type="text"
                placeholder="…o pegá una ruta manual /home/andres/…"
                value={manual}
                onChange={(e) => setManual(e.target.value)}
              />
              <button type="submit" className="repo-manual-btn" disabled={!manual.trim()}>
                Usar ruta
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
