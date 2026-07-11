import { useState, useEffect } from 'react';
import { api } from '../api';
import './CouncilConfig.css';

/**
 * Panel de configuración del consejo: activar/desactivar modelos, elegir chairman.
 * La selección se persiste en el backend; el stream usa esa config por defecto.
 * onSaved(cfg) notifica al padre para refrescar el contador.
 */
export default function CouncilConfig({ onSaved }) {
  const [open, setOpen] = useState(false);
  const [models, setModels] = useState([]);
  const [members, setMembers] = useState([]);
  const [chairman, setChairman] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const load = () => {
    api.fetchModels()
      .then((data) => {
        setModels(data.models || []);
        setMembers(data.members || []);
        setChairman(data.chairman);
      })
      .catch((e) => setError(String(e)));
  };

  useEffect(() => { load(); }, []);

  const councilModels = models.filter((m) => !m.title_only);

  const toggle = (id, available) => {
    if (!available) return;
    setMembers((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleSave = async () => {
    setError(null);
    let ch = chairman;
    if (!members.includes(ch)) ch = members[0];
    setSaving(true);
    try {
      const saved = await api.saveCouncilConfig(members, ch);
      setChairman(saved.chairman);
      onSaved?.(saved);
      setOpen(false);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="council-config">
      <button className="config-toggle" onClick={() => { setOpen(!open); if (!open) load(); }}>
        ⚙ Consejo ({members.length})
      </button>

      {open && (
        <div className="config-panel">
          <div className="config-header">Configurar consejo</div>
          <div className="config-list">
            {councilModels.map((m) => (
              <div key={m.id} className={`config-row ${!m.available ? 'unavailable' : ''}`}>
                <label className="config-member">
                  <input
                    type="checkbox"
                    checked={members.includes(m.id)}
                    disabled={!m.available}
                    onChange={() => toggle(m.id, m.available)}
                  />
                  <span className="member-label">{m.label}</span>
                  {m.available ? (
                    <span className="health ok" title="disponible">✓</span>
                  ) : (
                    <span className="health bad" title={m.reason}>✗ {m.reason}</span>
                  )}
                </label>
                <label className="chairman-pick" title="chairman (sintetiza)">
                  <input
                    type="radio"
                    name="chairman"
                    checked={chairman === m.id}
                    disabled={!members.includes(m.id)}
                    onChange={() => setChairman(m.id)}
                  />
                  chairman
                </label>
              </div>
            ))}
          </div>
          {error && <div className="config-error">{error}</div>}
          <div className="config-actions">
            <button className="config-save" onClick={handleSave} disabled={saving || members.length === 0}>
              {saving ? 'Guardando…' : 'Guardar'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
