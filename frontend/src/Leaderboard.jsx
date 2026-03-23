import { useState, useEffect } from "react";
import { api } from "./api";

export default function Leaderboard({ onClose }) {
  const [stats, setStats] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getStats().then((data) => {
      setStats(data);
      setLoading(false);
    });
  }, []);

  const medal = (i) => ["🥇", "🥈", "🥉"][i] || `#${i + 1}`;

  const barColor = (winRate) => {
    if (winRate >= 0.6) return "#27ae60";
    if (winRate >= 0.3) return "#f39c12";
    return "#e74c3c";
  };

  return (
    <div style={overlay}>
      <div style={modal}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <h2 style={{ margin: 0 }}>🏆 Model Leaderboard</h2>
          <button onClick={onClose} style={closeBtn}>✕</button>
        </div>

        {loading ? (
          <p style={{ color: "#aaa" }}>Loading stats...</p>
        ) : stats.length === 0 ? (
          <p style={{ color: "#aaa" }}>No data yet — run some queries first!</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ color: "#aaa", fontSize: 12, textAlign: "left" }}>
                <th style={th}>Rank</th>
                <th style={th}>Model</th>
                <th style={th}>Win Rate</th>
                <th style={th}>Wins</th>
                <th style={th}>Appearances</th>
                <th style={th}>Avg Rank</th>
              </tr>
            </thead>
            <tbody>
              {stats.map((s, i) => (
                <tr key={s.model} style={{ borderBottom: "1px solid #2a2a3e" }}>
                  <td style={td}>{medal(i)}</td>
                  <td style={{ ...td, fontSize: 13 }}>{s.model.split("/")[1] || s.model}</td>
                  <td style={td}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div style={{ background: "#2a2a3e", borderRadius: 4, width: 80, height: 8 }}>
                        <div style={{
                          background: barColor(s.win_rate),
                          width: `${s.win_rate * 100}%`,
                          height: "100%",
                          borderRadius: 4
                        }} />
                      </div>
                      <span style={{ fontSize: 12 }}>{Math.round(s.win_rate * 100)}%</span>
                    </div>
                  </td>
                  <td style={{ ...td, color: "#27ae60" }}>{s.wins}</td>
                  <td style={td}>{s.total_appearances}</td>
                  <td style={td}>{s.avg_rank}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <p style={{ color: "#666", fontSize: 11, marginTop: 20 }}>
          Based on peer rankings across all council sessions. Lower avg rank = better.
        </p>
      </div>
    </div>
  );
}

const overlay = { position:"fixed", inset:0, background:"rgba(0,0,0,0.7)", display:"flex", alignItems:"center", justifyContent:"center", padding:"16px", zIndex:1000 };
const modal = { background:"#1e1e2e", padding:30, borderRadius:12, width:"min(640px, calc(100vw - 32px))", color:"#fff", maxHeight:"calc(100vh - 32px)", overflowY:"auto" };
const closeBtn = { background:"#333", border:"none", borderRadius:6, color:"#fff", padding:"4px 10px", cursor:"pointer", fontSize:16 };
const th = { padding:"8px 12px", fontWeight:600 };
const td = { padding:"10px 12px", color:"#ddd" };
