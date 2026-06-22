import React from 'react';
import { useSimulationStore } from '../store/useSimulationStore';
import { Activity, Users, Award, MessageSquare, Download } from 'lucide-react';

export default function TelemetryPanel() {
  const { telemetry, agents, activeInfluencers, selectedAgentId, selectAgent, mutatedNarratives, currentTick } = useSimulationStore();

  const downloadNarratives = (e) => {
    if (e) e.preventDefault();
    if (!mutatedNarratives || mutatedNarratives.length === 0) {
      alert("No narratives to download yet.");
      return;
    }
    const jsonStr = JSON.stringify(mutatedNarratives, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `echo_narratives_tick_${currentTick}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const renderPolarizationChart = () => {
    const history = telemetry.history || [];
    if (history.length < 2) return <div className="empty-chart-text">Waiting for simulation steps...</div>;

    const width = 280, height = 90, padding = 15;
    const maxTick = Math.max(...history.map(h => h.tick));
    const maxVal = 1.0;

    const points = history.map(h => {
      const x = padding + (h.tick / maxTick) * (width - padding * 2);
      const y = height - padding - (h.polarization / maxVal) * (height - padding * 2);
      return `${x},${y}`;
    }).join(' ');

    return (
      <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} className="rct-svg-chart">
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#888" strokeWidth={1} />
        <line x1={padding} y1={padding} x2={padding} y2={height - padding} stroke="#888" strokeWidth={1} />
        <line x1={padding} y1={height/2} x2={width - padding} y2={height/2} stroke="#ddd" strokeDasharray="3,3" />
        <polyline fill="none" stroke="#B22222" strokeWidth={2} points={points} />
        {history.map((h, i) => {
          const x = padding + (h.tick / maxTick) * (width - padding * 2);
          const y = height - padding - (h.polarization / maxVal) * (height - padding * 2);
          return <circle key={i} cx={x} cy={y} r={2.5} fill="#B22222" />;
        })}
      </svg>
    );
  };

  const renderBeliefHistogram = () => {
    if (agents.length === 0) return null;
    const bins = Array(10).fill(0);
    agents.forEach(a => {
      const idx = Math.min(9, Math.floor((a.belief + 1.0) / 2.0 * 10));
      bins[idx]++;
    });

    const maxBin = Math.max(...bins, 1);
    const width = 280, height = 90, padding = 10, barWidth = (width - padding * 2) / bins.length;

    return (
      <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} className="rct-svg-chart">
        {bins.map((val, idx) => {
          const barHeight = (val / maxBin) * (height - padding * 2);
          const x = padding + idx * barWidth;
          const y = height - padding - barHeight;
          let fill = '#8BA88E';
          if (idx < 4) fill = '#9A8B9E';
          if (idx > 5) fill = '#8B4513';
          return <rect key={idx} x={x + 1} y={y} width={barWidth - 2} height={barHeight} fill={fill} stroke="#555" strokeWidth={0.5} />;
        })}
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#888" strokeWidth={1} />
      </svg>
    );
  };

  return (
    <footer className="rct-footer">
      <div className="rct-window telemetry-card">
        <div className="rct-titlebar">
          <Activity className="title-icon" />
          <span>Polarization Over Time (Std Dev)</span>
        </div>
        <div className="rct-panel telemetry-body chart-wrapper">
          {renderPolarizationChart()}
        </div>
      </div>

      <div className="rct-window telemetry-card">
        <div className="rct-titlebar">
          <Users className="title-icon" />
          <span>Belief Spectrum Histogram</span>
        </div>
        <div className="rct-panel telemetry-body chart-wrapper">
          {renderBeliefHistogram()}
        </div>
      </div>

      <div className="rct-window telemetry-card list-card">
        <div className="rct-titlebar">
          <Award className="title-icon" />
          <span>Top Active Influencers (Belief Delta)</span>
        </div>
        <div className="rct-panel telemetry-body list-body">
          {activeInfluencers.length > 0 ? (
            <div className="influencer-list">
              {activeInfluencers.slice(0, 5).map((infId, idx) => {
                const agent = agents[infId];
                if (!agent) return null;
                return (
                  <div key={infId} className={`influencer-item ${selectedAgentId === infId ? 'selected' : ''}`} onClick={() => selectAgent(infId)}>
                    <span className="rank">#{idx + 1}</span>
                    <span className="id">Agent {infId}</span>
                    <span className="detail">Belief: {agent.belief.toFixed(2)}</span>
                    <span className="arousal">Arousal: {agent.arousal.toFixed(2)}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="no-agent-selected" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span>No ticks processed yet</span>
            </div>
          )}
        </div>
      </div>

      <div className="rct-window telemetry-card list-card">
        <div className="rct-titlebar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <MessageSquare className="title-icon" />
            <span>Mutated Narratives Log</span>
          </div>
          <button type="button" className="rct-close-sm" onClick={downloadNarratives} title="Download Logs (JSON)" style={{ display: 'flex', alignItems: 'center', gap: '2px', padding: '2px 4px' }}>
            <Download size={10} />
            <span>SAVE</span>
          </button>
        </div>
        <div className="rct-panel telemetry-body list-body">
          {mutatedNarratives.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {[...mutatedNarratives].reverse().map((log, idx) => (
                <div key={idx} style={{ padding: '4px 6px', borderBottom: '1px dotted #ccc', fontSize: '11px', lineHeight: '1.3' }}>
                  <span style={{ color: '#000080', fontWeight: 'bold' }}>T[{log.tick}] </span>
                  <span style={{ textDecoration: 'underline', cursor: 'pointer', color: '#8b4513', fontWeight: 'bold' }} onClick={() => selectAgent(log.agent_id)}>
                    Agent {log.agent_id}
                  </span>: <span style={{ color: '#333' }}>"{log.message}"</span>
                  <div style={{ marginTop: '3px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    {log.source_agent_ids && log.source_agent_ids.length > 0 && (
                      <span style={{ fontSize: '9px', color: '#666' }}>
                        Inspired by: {log.source_agent_ids.map(id => (
                          <span key={id} style={{ textDecoration: 'underline', cursor: 'pointer', marginRight: '4px' }} onClick={() => selectAgent(id)}>#{id}</span>
                        ))}
                      </span>
                    )}
                    <span style={{ fontSize: '9px', backgroundColor: log.provider === 'groq' ? '#e6ffe6' : log.provider === 'gemini' ? '#e6f2ff' : log.provider === 'manual' ? '#ffe6e6' : '#f5f5f5', color: log.provider === 'groq' ? '#006600' : log.provider === 'gemini' ? '#003366' : log.provider === 'manual' ? '#990000' : '#555', padding: '0px 3px', borderRadius: '2px', textTransform: 'uppercase', marginLeft: 'auto' }}>
                      {log.provider}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="no-agent-selected" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span>No narrative mutations logged yet</span>
            </div>
          )}
        </div>
      </div>
    </footer>
  );
}
