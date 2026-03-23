import { useState, useEffect } from "react";
import { api } from "./api";

export default function Settings({ onClose }) {
  const [models, setModels] = useState([]);
  const [chairman, setChairman] = useState("");
  const [newModel, setNewModel] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getConfig().then((cfg) => {
      setModels(cfg.council_models);
      setChairman(cfg.chairman_model);
    });
  }, []);

  const addModel = () => {
    if (newModel.trim() && !models.includes(newModel.trim())) {
      setModels([...models, newModel.trim()]);
      setNewModel("");
    }
  };

  const removeModel = (m) => setModels(models.filter((x) => x !== m));

  const save = async () => {
    await api.saveConfig({ council_models: models, chairman_model: chairman });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div style={overlay}>
      <div style={modal}>
        <h2>⚙️ Council Settings</h2>

        <h3>Council Models</h3>
        {models.map((m) => (
          <div key={m} style={row}>
            <span>{m}</span>
            <button onClick={() => removeModel(m)} style={removeBtn}>✕</button>
          </div>
        ))}
        <div style={row}>
          <input
            value={newModel}
            onChange={(e) => setNewModel(e.target.value)}
            placeholder="e.g. openai/gpt-4o"
            style={input}
            onKeyDown={(e) => e.key === "Enter" && addModel()}
          />
          <button onClick={addModel} style={addBtn}>+ Add</button>
        </div>

        <h3>Chairman Model</h3>
        <input
          value={chairman}
          onChange={(e) => setChairman(e.target.value)}
          style={{ ...input, width: "100%" }}
        />

        <div style={{ marginTop: 20, display: "flex", gap: 10 }}>
          <button onClick={save} style={saveBtn}>
            {saved ? "✅ Saved!" : "Save"}
          </button>
          <button onClick={onClose} style={cancelBtn}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

const overlay = { position:"fixed", inset:0, background:"rgba(0,0,0,0.6)", display:"flex", alignItems:"center", justifyContent:"center", padding:"16px", zIndex:1000 };
const modal = { background:"#1e1e2e", padding:30, borderRadius:12, width:"min(640px, calc(100vw - 32px))", maxHeight:"calc(100vh - 32px)", overflowY:"auto", color:"#fff" };
const row = { display:"flex", alignItems:"center", gap:10, marginBottom:8, flexWrap:"wrap" };
const input = { background:"#2a2a3e", border:"1px solid #444", borderRadius:6, padding:"6px 10px", color:"#fff", flex:1 };
const removeBtn = { background:"#c0392b", border:"none", borderRadius:6, color:"#fff", padding:"4px 8px", cursor:"pointer" };
const addBtn = { background:"#2980b9", border:"none", borderRadius:6, color:"#fff", padding:"6px 12px", cursor:"pointer" };
const saveBtn = { background:"#27ae60", border:"none", borderRadius:6, color:"#fff", padding:"8px 20px", cursor:"pointer" };
const cancelBtn = { background:"#555", border:"none", borderRadius:6, color:"#fff", padding:"8px 20px", cursor:"pointer" };
