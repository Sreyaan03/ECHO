import React, { useState, useEffect } from 'react';
import { useSimulationStore } from '../store/useSimulationStore';
import VoxelCanvas from './VoxelCanvas';
import { 
  Play, Pause, SkipForward, RefreshCw, Zap, Users, 
  Settings, Award, Heart, HelpCircle, Activity, MessageSquare, Download, RotateCcw, Upload
} from 'lucide-react';

export default function Dashboard() {
  const {
    config,
    setConfig,
    isInitialized,
    isPlaying,
    currentTick,
    agents,
    edges,
    activeInfluencers,
    edgesSevered,
    selectedAgentId,
    telemetry,
    narrativeInput,
    setNarrativeInput,
    customRumor,
    setCustomRumor,
    initializeSimulation,
    stepSimulation,
    togglePlay,
    injectNarrative,
    selectAgent,
    mutatedNarratives,
    reactionTemplate,
    injectionTemplate,
    defaultReactionTemplate,
    defaultInjectionTemplate,
    fetchPrompts,
    updatePrompts,
    exportSession,
    resetSimulation,
    loadSession
  } = useSimulationStore();

  const [activeTab, setActiveTab] = useState('topology');
  const [injectBelief, setInjectBelief] = useState(0.8);
  const [localReaction, setLocalReaction] = useState('');
  const [localInjection, setLocalInjection] = useState('');

  // Sync from store once prompts are loaded
  useEffect(() => {
    setLocalReaction(reactionTemplate);
  }, [reactionTemplate]);

  useEffect(() => {
    setLocalInjection(injectionTemplate);
  }, [injectionTemplate]);

  // Auto initialize on first load
  useEffect(() => {
    initializeSimulation();
    fetchPrompts();
  }, []);

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const json = JSON.parse(event.target.result);
        loadSession(json);
      } catch (err) {
        alert("Failed to parse JSON file.");
        console.error(err);
      }
    };
    reader.readAsText(file);
    // Clear input so same file can be uploaded again if needed
    e.target.value = '';
  };

  const selectedAgent = selectedAgentId !== null ? agents[selectedAgentId] : null;

  // Render simple SVG line chart for polarization history
  const renderPolarizationChart = () => {
    const history = telemetry.history || [];
    if (history.length < 2) {
      return (
        <div className="empty-chart-text">
          Waiting for simulation steps...
        </div>
      );
    }

    const width = 280;
    const height = 90;
    const padding = 15;

    const maxTick = Math.max(...history.map(h => h.tick));
    const maxVal = 1.0; // polarization is standard dev of belief in [-1, 1], so max is 1.0

    const points = history.map(h => {
      const x = padding + (h.tick / maxTick) * (width - padding * 2);
      const y = height - padding - (h.polarization / maxVal) * (height - padding * 2);
      return `${x},${y}`;
    }).join(' ');

    return (
      <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} className="rct-svg-chart">
        {/* Grid lines */}
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#888" strokeWidth={1} />
        <line x1={padding} y1={padding} x2={padding} y2={height - padding} stroke="#888" strokeWidth={1} />
        
        {/* Horizontal grid guide */}
        <line x1={padding} y1={height/2} x2={width - padding} y2={height/2} stroke="#ddd" strokeDasharray="3,3" />

        {/* The data line */}
        <polyline
          fill="none"
          stroke="#B22222"
          strokeWidth={2}
          points={points}
        />

        {/* Data points */}
        {history.map((h, i) => {
          const x = padding + (h.tick / maxTick) * (width - padding * 2);
          const y = height - padding - (h.polarization / maxVal) * (height - padding * 2);
          return (
            <circle key={i} cx={x} cy={y} r={2.5} fill="#B22222" />
          );
        })}
      </svg>
    );
  };

  // Render SVG Histogram for belief distribution
  const renderBeliefHistogram = () => {
    if (agents.length === 0) return null;

    const bins = Array(10).fill(0);
    agents.forEach(a => {
      const idx = Math.min(9, Math.floor((a.belief + 1.0) / 2.0 * 10));
      bins[idx]++;
    });

    const maxBin = Math.max(...bins, 1);
    const width = 280;
    const height = 90;
    const padding = 10;
    const barWidth = (width - padding * 2) / bins.length;

    return (
      <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} className="rct-svg-chart">
        {bins.map((val, idx) => {
          const barHeight = (val / maxBin) * (height - padding * 2);
          const x = padding + idx * barWidth;
          const y = height - padding - barHeight;
          
          // Color code from Left (blue/purple) to Right (orange/brown)
          let fill = '#8BA88E';
          if (idx < 4) fill = '#9A8B9E';
          if (idx > 5) fill = '#8B4513';

          return (
            <rect
              key={idx}
              x={x + 1}
              y={y}
              width={barWidth - 2}
              height={barHeight}
              fill={fill}
              stroke="#555"
              strokeWidth={0.5}
            />
          );
        })}
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#888" strokeWidth={1} />
      </svg>
    );
  };

  return (
    <div className="rct-layout">
      {/* Top Retro Game Header bar */}
      <header className="rct-header">
        <div className="rct-header-left">
          <Zap className="rct-header-icon" />
          <h1>ECHO opinion engine sandbox</h1>
        </div>
        <div className="rct-header-right">
          <div className="rct-status-badge">
            Tick: <span>{currentTick}</span>
          </div>
          <div className="rct-status-badge">
            Edges Severed: <span className="severed">{edgesSevered}</span>
          </div>
          <div className="rct-status-badge">
            Edges Formed: <span style={{ color: '#228B22', fontWeight: 'bold' }}>{useSimulationStore(s => s.edgesFormed)}</span>
          </div>
        </div>
      </header>

      {/* Main Sandbox Grid Workspace */}
      <main className="rct-grid">
        {/* Left Side Config Panel */}
        <section className="rct-sidebar-left">
          <div className="rct-window">
            <div className="rct-titlebar">
              <Settings className="title-icon" />
              <span>Simulation Controls</span>
            </div>
            
            {/* Tab navigation */}
            <div className="rct-tabs">
              <button 
                className={`rct-tab-btn ${activeTab === 'topology' ? 'active' : ''}`}
                onClick={() => setActiveTab('topology')}
              >
                Topology
              </button>
              <button 
                className={`rct-tab-btn ${activeTab === 'dynamics' ? 'active' : ''}`}
                onClick={() => setActiveTab('dynamics')}
              >
                Dynamics
              </button>
              <button 
                className={`rct-tab-btn ${activeTab === 'prompts' ? 'active' : ''}`}
                onClick={() => setActiveTab('prompts')}
              >
                Prompts
              </button>
            </div>

            <div className="rct-panel form-panel">
              {activeTab === 'topology' && (
                <div className="form-group-list">
                  <div className="form-group">
                    <label>Agent count:</label>
                    <div className="range-val-container">
                      <input 
                        type="range" min="50" max="500" step="50" 
                        value={config.n_agents} 
                        onChange={(e) => setConfig({ n_agents: parseInt(e.target.value) })}
                      />
                      <span className="value-badge">{config.n_agents}</span>
                    </div>
                  </div>

                  <div className="form-group">
                    <label>Topology Archetype:</label>
                    <select 
                      value={config.topology} 
                      onChange={(e) => setConfig({ topology: e.target.value })}
                    >
                      <option value="small_world">Watts-Strogatz (Small World)</option>
                      <option value="scale_free">Barabási-Albert (Scale Free)</option>
                    </select>
                  </div>

                  {config.topology === 'small_world' ? (
                    <>
                      <div className="form-group">
                        <label>k (Neighbors):</label>
                        <div className="range-val-container">
                          <input 
                            type="range" min="2" max="16" step="2"
                            value={config.topology_params.k}
                            onChange={(e) => setConfig({ 
                              topology_params: { ...config.topology_params, k: parseInt(e.target.value) } 
                            })}
                          />
                          <span className="value-badge">{config.topology_params.k}</span>
                        </div>
                      </div>
                      <div className="form-group">
                        <label>p (Rewire Prob):</label>
                        <div className="range-val-container">
                          <input 
                            type="range" min="0.0" max="1.0" step="0.05"
                            value={config.topology_params.p}
                            onChange={(e) => setConfig({ 
                              topology_params: { ...config.topology_params, p: parseFloat(e.target.value) } 
                            })}
                          />
                          <span className="value-badge">{config.topology_params.p}</span>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="form-group">
                      <label>m (Attach Edges):</label>
                      <div className="range-val-container">
                        <input 
                          type="range" min="1" max="8" step="1"
                          value={config.topology_params.m}
                          onChange={(e) => setConfig({ 
                            topology_params: { ...config.topology_params, m: parseInt(e.target.value) } 
                          })}
                        />
                        <span className="value-badge">{config.topology_params.m}</span>
                      </div>
                    </div>
                  )}

                  <div className="form-group">
                    <label>Random seed:</label>
                    <input 
                      type="number" 
                      value={config.seed || ''} 
                      onChange={(e) => setConfig({ seed: e.target.value ? parseInt(e.target.value) : null })}
                      className="rct-text-input"
                    />
                  </div>
                </div>
              )}

              {activeTab === 'dynamics' && (
                <div className="form-group-list">
                  <div className="form-group">
                    <label>Weight (Political):</label>
                    <div className="range-val-container">
                      <input 
                        type="range" min="0.0" max="1.0" step="0.05"
                        value={config.w_pol}
                        onChange={(e) => setConfig({ w_pol: parseFloat(e.target.value) })}
                      />
                      <span className="value-badge">{config.w_pol}</span>
                    </div>
                  </div>

                  <div className="form-group">
                    <label>Weight (Economic):</label>
                    <div className="range-val-container">
                      <input 
                        type="range" min="0.0" max="1.0" step="0.05"
                        value={config.w_econ}
                        onChange={(e) => setConfig({ w_econ: parseFloat(e.target.value) })}
                      />
                      <span className="value-badge">{config.w_econ}</span>
                    </div>
                  </div>

                  <div className="form-group">
                    <label>Weight (Religious):</label>
                    <div className="range-val-container">
                      <input 
                        type="range" min="0.0" max="1.0" step="0.05"
                        value={config.w_rel}
                        onChange={(e) => setConfig({ w_rel: parseFloat(e.target.value) })}
                      />
                      <span className="value-badge">{config.w_rel}</span>
                    </div>
                  </div>

                  <div className="form-group">
                    <label>Bounded Tolerance (Deffuant):</label>
                    <div className="range-val-container">
                      <input 
                        type="range" min="0.1" max="1.5" step="0.05"
                        value={config.d_tolerance}
                        onChange={(e) => setConfig({ d_tolerance: parseFloat(e.target.value) })}
                      />
                      <span className="value-badge">{config.d_tolerance}</span>
                    </div>
                  </div>

                  <div className="form-group">
                    <label>Backfire Repulsion (γ):</label>
                    <div className="range-val-container">
                      <input 
                        type="range" min="0.01" max="0.5" step="0.01"
                        value={config.gamma}
                        onChange={(e) => setConfig({ gamma: parseFloat(e.target.value) })}
                      />
                      <span className="value-badge">{config.gamma}</span>
                    </div>
                  </div>

                  <div className="form-group">
                    <label>Sever Fatigue Limit:</label>
                    <div className="range-val-container">
                      <input 
                        type="range" min="2" max="15" step="1"
                        value={config.fatigue_limit}
                        onChange={(e) => setConfig({ fatigue_limit: parseInt(e.target.value) })}
                      />
                      <span className="value-badge">{config.fatigue_limit}</span>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'prompts' && (
                <div className="form-group-list" style={{ flexGrow: 1, display: 'flex', flexDirection: 'column', gap: '8px', minHeight: 0 }}>
                  <div style={{ fontSize: '10px', color: '#555', borderBottom: '1px dotted #999', paddingBottom: '6px', lineHeight: '1.3' }}>
                    <strong>Placeholders:</strong> <code>{"{baseline_belief}"}</code>, <code>{"{current_belief}"}</code>, <code>{"{stubbornness}"}</code>. JSON rules are appended automatically.
                  </div>
                  
                  <div className="form-group" style={{ display: 'flex', flexDirection: 'column', flexGrow: 1, minHeight: 0 }}>
                    <label style={{ fontWeight: 'bold', fontSize: '11px', marginBottom: '3px' }}>Narrative Mutation System:</label>
                    <textarea
                      value={localReaction}
                      onChange={(e) => setLocalReaction(e.target.value)}
                      style={{ 
                        flexGrow: 1,
                        minHeight: '100px',
                        fontSize: '10px', 
                        fontFamily: 'monospace', 
                        padding: '4px',
                        border: '1px solid #7f9db9',
                        backgroundColor: '#fff',
                        color: '#000',
                        resize: 'none',
                        lineHeight: '1.3'
                      }}
                    />
                  </div>

                  <div className="form-group" style={{ display: 'flex', flexDirection: 'column', flexGrow: 1, minHeight: 0 }}>
                    <label style={{ fontWeight: 'bold', fontSize: '11px', marginBottom: '3px' }}>Patient Zero Injection:</label>
                    <textarea
                      value={localInjection}
                      onChange={(e) => setLocalInjection(e.target.value)}
                      style={{ 
                        flexGrow: 1,
                        minHeight: '80px',
                        fontSize: '10px', 
                        fontFamily: 'monospace', 
                        padding: '4px',
                        border: '1px solid #7f9db9',
                        backgroundColor: '#fff',
                        color: '#000',
                        resize: 'none',
                        lineHeight: '1.3'
                      }}
                    />
                  </div>

                  <div style={{ display: 'flex', gap: '6px', marginTop: '2px', paddingBottom: '8px' }}>
                    <button 
                      className="rct-button primary" 
                      style={{ flex: 1, padding: '4px', height: '24px', fontSize: '11px' }}
                      onClick={() => {
                        updatePrompts(localReaction, localInjection);
                        alert('Prompts updated and applied to the engine!');
                      }}
                    >
                      Save & Apply
                    </button>
                    <button 
                      className="rct-button" 
                      style={{ padding: '4px', height: '24px', fontSize: '11px' }}
                      onClick={() => {
                        if (window.confirm('Reset templates to default?')) {
                          setLocalReaction(defaultReactionTemplate);
                          setLocalInjection(defaultInjectionTemplate);
                          updatePrompts(defaultReactionTemplate, defaultInjectionTemplate);
                        }
                      }}
                    >
                      Reset
                    </button>
                  </div>
                </div>
              )}

              <div className="form-group" style={{ marginTop: '12px', marginBottom: '8px' }}>
                <label style={{ fontWeight: 'bold', fontSize: '11px' }}>Global Simulation Topic / Seed:</label>
                <input 
                  type="text" 
                  value={narrativeInput} 
                  onChange={(e) => setNarrativeInput(e.target.value)}
                  className="rct-text-input"
                  style={{ width: '100%', marginTop: '3px', height: '24px' }}
                />
              </div>

              <button className="rct-button primary block-btn" onClick={initializeSimulation}>
                <RefreshCw className="btn-icon" />
                Initialize Simulation
              </button>
            </div>
          </div>

          {/* Action Bar */}
          <div className="rct-window" style={{ marginTop: '12px' }}>
            <div className="rct-titlebar">
              <Activity className="title-icon" />
              <span>Playback Control</span>
            </div>
            <div className="rct-panel playback-panel">
              <button 
                className={`rct-button ${isPlaying ? 'pressed' : ''}`}
                onClick={togglePlay}
                disabled={!isInitialized}
              >
                {isPlaying ? <Pause className="btn-icon" /> : <Play className="btn-icon" />}
                {isPlaying ? 'Pause' : 'Auto Play'}
              </button>
              
              <button 
                className="rct-button" 
                onClick={stepSimulation}
                disabled={!isInitialized || isPlaying}
              >
                <SkipForward className="btn-icon" />
                Step Tick
              </button>
              
              <button 
                className="rct-button" 
                onClick={resetSimulation}
                disabled={!isInitialized && currentTick === 0}
              >
                <RotateCcw className="btn-icon" />
                Reset
              </button>
              
              <div style={{ marginLeft: 'auto', display: 'flex', gap: '4px' }}>
                <input 
                  type="file" 
                  accept=".json" 
                  id="session-upload" 
                  style={{ display: 'none' }} 
                  onChange={handleFileUpload}
                />
                <label 
                  htmlFor="session-upload" 
                  className="rct-button" 
                  style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center' }}
                >
                  <Upload className="btn-icon" />
                  Load
                </label>
                
                <button 
                  className="rct-button" 
                  onClick={exportSession}
                  disabled={!isInitialized}
                >
                  <Download className="btn-icon" />
                  Export
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* Center 3D Voxel Playfield */}
        <section className="rct-canvas-section">
          <VoxelCanvas />
        </section>

        {/* Right Side Inspector & Details Panel */}
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
                        <td className="value-col">{selectedAgent.neighbors?.length || 0}</td>
                      </tr>
                    </tbody>
                  </table>

                  {/* Patient Zero Narrative Injector */}
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
      </main>

      {/* Bottom Panel containing Telemetry Charts & Logs */}
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
                    <div 
                      key={infId} 
                      className={`influencer-item ${selectedAgentId === infId ? 'selected' : ''}`}
                      onClick={() => selectAgent(infId)}
                    >
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
          <div className="rct-titlebar">
            <MessageSquare className="title-icon" />
            <span>Mutated Narratives Log</span>
          </div>
          <div className="rct-panel telemetry-body list-body">
            {mutatedNarratives.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {[...mutatedNarratives].reverse().map((log, idx) => (
                  <div 
                    key={idx} 
                    style={{ 
                      padding: '4px 6px', 
                      borderBottom: '1px dotted #ccc', 
                      fontSize: '11px',
                      lineHeight: '1.3'
                    }}
                  >
                    <span style={{ color: '#000080', fontWeight: 'bold' }}>T[{log.tick}] </span>
                    <span 
                      style={{ textDecoration: 'underline', cursor: 'pointer', color: '#8b4513', fontWeight: 'bold' }}
                      onClick={() => selectAgent(log.agent_id)}
                    >
                      Agent {log.agent_id}
                    </span>:{" "}
                    <span style={{ color: '#333' }}>"{log.message}"</span>{" "}
                    <span style={{ 
                      fontSize: '9px', 
                      backgroundColor: log.provider === 'groq' ? '#e6ffe6' : log.provider === 'gemini' ? '#e6f2ff' : log.provider === 'manual' ? '#ffe6e6' : '#f5f5f5',
                      color: log.provider === 'groq' ? '#006600' : log.provider === 'gemini' ? '#003366' : log.provider === 'manual' ? '#990000' : '#555',
                      padding: '0px 3px',
                      borderRadius: '2px',
                      float: 'right',
                      textTransform: 'uppercase',
                      marginLeft: '6px',
                      marginTop: '2px'
                    }}>
                      {log.provider}
                    </span>
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
    </div>
  );
}
