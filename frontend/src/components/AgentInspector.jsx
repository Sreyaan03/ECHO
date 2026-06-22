import React from 'react';
import { useSimulationStore } from '../store/useSimulationStore';
import { Users, Zap } from 'lucide-react';

export default function AgentInspector() {
  const { agents, edges, selectedAgentId, selectAgent, customRumor, setCustomRumor, injectNarrative } = useSimulationStore();
  const [injectBelief, setInjectBelief] = React.useState(0.8);

  const selectedAgent = selectedAgentId !== null ? agents[selectedAgentId] : null;

  return (
    <section className="rct-sidebar-right">
      <div className="rct-window" style={{ height: '100%' }}>
        <div className="rct-titlebar">
          <Users className="title-icon" />
          <span>Inspector Panel</span>
        </div>
        
        <div className="rct-panel inspector-panel" style={{ height: 'calc(100% - 24px)' }}>
          {selectedAgent ? (
            <div className="agent-detail-list">
              <div className="rct-header-sub">
                <span>AGENT #{selectedAgent.agent_id}</span>
                <button className="rct-close-sm" onClick={() => selectAgent(null)}>X</button>
              </div>
              
              {selectedAgent.is_anchor && (
                <div style={{ padding: '4px 8px', backgroundColor: '#ffd700', color: '#8b4500', fontWeight: 'bold', fontSize: '11px', textAlign: 'center', marginBottom: '8px', border: '1px solid #cdaa00' }}>
                  ★ ANCHOR NODE (TOP 10% OSINT)
                </div>
              )}

              <table className="rct-table">
                <tbody>
                  <tr>
                    <td>Political Leaning</td>
                    <td className="value-col">{selectedAgent.political.toFixed(3)}</td>
                  </tr>
                  <tr>
                    <td>Economic Position</td>
                    <td className="value-col">{selectedAgent.economic.toFixed(3)}</td>
                  </tr>
                  <tr>
                    <td>Religious Identity</td>
                    <td className="value-col">Group {selectedAgent.religion}</td>
                  </tr>
                  <tr>
                    <td>Current Belief</td>
                    <td className={`value-col belief-val ${selectedAgent.belief > 0.3 ? 'right-wing' : selectedAgent.belief < -0.3 ? 'left-wing' : ''}`}>
                      {selectedAgent.belief.toFixed(3)}
                    </td>
                  </tr>
                  <tr>
                    <td>Gullibility (Base μ)</td>
                    <td className="value-col">{selectedAgent.gullibility.toFixed(3)}</td>
                  </tr>
                  <tr>
                    <td>Arousal Score</td>
                    <td className={`value-col arousal-val ${selectedAgent.arousal > 0.7 ? 'hot-arousal' : ''}`}>
                      {selectedAgent.arousal.toFixed(3)}
                    </td>
                  </tr>
                  <tr>
                    <td>Media Literacy</td>
                    <td className="value-col">{selectedAgent.literacy.toFixed(3)}</td>
                  </tr>
                  <tr>
                    <td>Active Connections</td>
                    <td className="value-col">
                      {edges.filter(e => e[0] === selectedAgent.agent_id || e[1] === selectedAgent.agent_id).length}
                    </td>
                  </tr>
                </tbody>
              </table>

              <div className="narrative-injector rct-inset">
                <div className="rct-header-sub">
                  <Zap className="btn-icon" />
                  <span>Seeding Payload</span>
                </div>
                <div className="injector-controls">
                  <div className="form-group">
                    <label>Narrative Message:</label>
                    <input 
                      type="text" 
                      value={customRumor} 
                      onChange={(e) => setCustomRumor(e.target.value)}
                      className="rct-text-input"
                    />
                  </div>
                  
                  <div className="form-group">
                    <label>Injected Belief: ({injectBelief.toFixed(2)})</label>
                    <input 
                      type="range" min="-1.0" max="1.0" step="0.1"
                      value={injectBelief} 
                      onChange={(e) => setInjectBelief(parseFloat(e.target.value))}
                    />
                  </div>

                  <button 
                    className="rct-button danger block-btn"
                    onClick={() => injectNarrative(selectedAgent.agent_id, injectBelief, customRumor)}
                  >
                    Inject Narrative Target
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="no-agent-selected">
              <p>No Agent Selected</p>
              <p style={{ fontSize: '11px', color: '#666', marginTop: '10px' }}>
                Click on any voxel block inside the 3D canvas to inspect properties, check media literacy, or inject narratives.
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
