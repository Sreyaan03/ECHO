import React, { useState, useEffect } from 'react';
import { useSimulationStore } from '../store/useSimulationStore';
import { Settings, RefreshCw, Upload, Activity, Play, Pause, SkipForward, RotateCcw, Zap, Download } from 'lucide-react';
import ExportPanel from './ExportPanel';
import ReligionPanel from './ReligionPanel';
import TopicsPanel from './TopicsPanel';

export default function SimulationControls() {
  const {
    config, setConfig, isInitialized, isPlaying, currentTick,
    narrativeInput, setNarrativeInput,
    secondaryTopicInput, setSecondaryTopicInput,
    initializeSimulation, stepSimulation, togglePlay, resetSimulation,
    algorithmActive, toggleAlgorithm, exportSession, uploadTopology, loadSession,
    reactionTemplate, injectionTemplate, defaultReactionTemplate, defaultInjectionTemplate,
    updatePrompts
  } = useSimulationStore();

  const [activeTab, setActiveTab] = useState('topology');
  const [localReaction, setLocalReaction] = useState('');
  const [localInjection, setLocalInjection] = useState('');

  useEffect(() => {
    setLocalReaction(reactionTemplate);
  }, [reactionTemplate]);

  useEffect(() => {
    setLocalInjection(injectionTemplate);
  }, [injectionTemplate]);

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
    e.target.value = '';
  };

  return (
    <section className="rct-sidebar-left">
      <div className="rct-window" style={{ minHeight: '420px' }}>
        <div className="rct-titlebar">
          <Settings className="title-icon" />
          <span>Simulation Controls</span>
        </div>
        
        <div className="rct-tabs">
          <button className={`rct-tab-btn ${activeTab === 'topology' ? 'active' : ''}`} onClick={() => setActiveTab('topology')}>Topology</button>
          <button className={`rct-tab-btn ${activeTab === 'dynamics' ? 'active' : ''}`} onClick={() => setActiveTab('dynamics')}>Dynamics</button>
          <button className={`rct-tab-btn ${activeTab === 'prompts' ? 'active' : ''}`} onClick={() => setActiveTab('prompts')}>Prompts</button>
        </div>

        <div className="rct-panel form-panel">
          {activeTab === 'topology' && (
            <div className="form-group-list">
              <div className="form-group">
                <label>Agent count:</label>
                <div className="range-val-container">
                  <input type="range" min="50" max="500" step="50" value={config.n_agents} onChange={(e) => setConfig({ n_agents: parseInt(e.target.value) })} />
                  <span className="value-badge">{config.n_agents}</span>
                </div>
              </div>

              <div className="form-group">
                <label>Belief Distribution:</label>
                <select value={config.belief_dist || 'uniform'} onChange={(e) => setConfig({ belief_dist: e.target.value })}>
                  <option value="uniform">Uniform (Random Spread)</option>
                  <option value="normal">Normal (Moderate Bell Curve)</option>
                  <option value="bimodal">Bimodal (Polarized Extremes)</option>
                </select>
              </div>

              <div className="form-group">
                <label>Topology Archetype:</label>
                <select value={config.topology} onChange={(e) => setConfig({ topology: e.target.value })}>
                  <option value="small_world">Watts-Strogatz (Small World)</option>
                  <option value="scale_free">Barabási-Albert (Scale Free)</option>
                  <option value="stochastic_block">Stochastic Block Model</option>
                </select>
              </div>

              {config.topology === 'small_world' ? (
                <>
                  <div className="form-group">
                    <label>k (Neighbors):</label>
                    <div className="range-val-container">
                      <input type="range" min="2" max="16" step="2" value={config.topology_params.k} onChange={(e) => setConfig({ topology_params: { ...config.topology_params, k: parseInt(e.target.value) } })} />
                      <span className="value-badge">{config.topology_params.k}</span>
                    </div>
                  </div>
                  <div className="form-group">
                    <label>p (Rewire Prob):</label>
                    <div className="range-val-container">
                      <input type="range" min="0.0" max="1.0" step="0.05" value={config.topology_params.p} onChange={(e) => setConfig({ topology_params: { ...config.topology_params, p: parseFloat(e.target.value) } })} />
                      <span className="value-badge">{config.topology_params.p}</span>
                    </div>
                  </div>
                </>
              ) : config.topology === 'scale_free' ? (
                <div className="form-group">
                  <label>m (Attach Edges):</label>
                  <div className="range-val-container">
                    <input type="range" min="1" max="8" step="1" value={config.topology_params.m} onChange={(e) => setConfig({ topology_params: { ...config.topology_params, m: parseInt(e.target.value) } })} />
                    <span className="value-badge">{config.topology_params.m}</span>
                  </div>
                </div>
              ) : (
                <>
                  <div className="form-group">
                    <label>Blocks (Communities):</label>
                    <div className="range-val-container">
                      <input type="range" min="2" max="6" step="1" value={config.topology_params.sbm_blocks || 3} onChange={(e) => setConfig({ topology_params: { ...config.topology_params, sbm_blocks: parseInt(e.target.value) } })} />
                      <span className="value-badge">{config.topology_params.sbm_blocks || 3}</span>
                    </div>
                  </div>
                  <div className="form-group">
                    <label>p_in (In-Block Prob):</label>
                    <div className="range-val-container">
                      <input type="range" min="0.0" max="1.0" step="0.05" value={config.topology_params.sbm_p_in || 0.3} onChange={(e) => setConfig({ topology_params: { ...config.topology_params, sbm_p_in: parseFloat(e.target.value) } })} />
                      <span className="value-badge">{config.topology_params.sbm_p_in || 0.3}</span>
                    </div>
                  </div>
                  <div className="form-group">
                    <label>p_out (Out-Block Prob):</label>
                    <div className="range-val-container">
                      <input type="range" min="0.0" max="0.5" step="0.01" value={config.topology_params.sbm_p_out || 0.01} onChange={(e) => setConfig({ topology_params: { ...config.topology_params, sbm_p_out: parseFloat(e.target.value) } })} />
                      <span className="value-badge">{config.topology_params.sbm_p_out || 0.01}</span>
                    </div>
                  </div>
                </>
              )}

              <div className="form-group">
                <label>Random seed:</label>
                <input type="number" value={config.seed || ''} onChange={(e) => setConfig({ seed: e.target.value ? parseInt(e.target.value) : null })} className="rct-text-input" />
              </div>
              <div className="form-group">
                <label>Bot Farm Injection (%):</label>
                <div className="range-val-container">
                  <input type="range" min="0.0" max="0.2" step="0.01" value={config.p_bots} onChange={(e) => setConfig({ p_bots: parseFloat(e.target.value) })} />
                  <span className="value-badge">{(config.p_bots * 100).toFixed(0)}%</span>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'dynamics' && (
            <div className="form-group-list">
              <div className="form-group">
                <label>Weight (Political):</label>
                <div className="range-val-container">
                  <input type="range" min="0.0" max="1.0" step="0.05" value={config.w_pol} onChange={(e) => setConfig({ w_pol: parseFloat(e.target.value) })} />
                  <span className="value-badge">{config.w_pol}</span>
                </div>
              </div>

              <div className="form-group">
                <label>Weight (Economic):</label>
                <div className="range-val-container">
                  <input type="range" min="0.0" max="1.0" step="0.05" value={config.w_econ} onChange={(e) => setConfig({ w_econ: parseFloat(e.target.value) })} />
                  <span className="value-badge">{config.w_econ}</span>
                </div>
              </div>

              <div className="form-group">
                <label>Weight (Religious):</label>
                <div className="range-val-container">
                  <input type="range" min="0.0" max="1.0" step="0.05" value={config.w_rel} onChange={(e) => setConfig({ w_rel: parseFloat(e.target.value) })} />
                  <span className="value-badge">{config.w_rel}</span>
                </div>
              </div>

              <div className="form-group">
                <label>Bounded Tolerance (Deffuant):</label>
                <div className="range-val-container">
                  <input type="range" min="0.1" max="1.5" step="0.05" value={config.d_tolerance} onChange={(e) => setConfig({ d_tolerance: parseFloat(e.target.value) })} />
                  <span className="value-badge">{config.d_tolerance}</span>
                </div>
              </div>

              <div className="form-group">
                <label>Backfire Repulsion (γ):</label>
                <div className="range-val-container">
                  <input type="range" min="0.01" max="0.5" step="0.01" value={config.gamma} onChange={(e) => setConfig({ gamma: parseFloat(e.target.value) })} />
                  <span className="value-badge">{config.gamma}</span>
                </div>
              </div>

              <div className="form-group">
                <label>Sever Fatigue Limit:</label>
                <div className="range-val-container">
                  <input type="range" min="2" max="15" step="1" value={config.fatigue_limit} onChange={(e) => setConfig({ fatigue_limit: parseInt(e.target.value) })} />
                  <span className="value-badge">{config.fatigue_limit}</span>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'prompts' && (
            <div className="form-group-list" style={{ flexGrow: 1, display: 'flex', flexDirection: 'column', gap: '8px', minHeight: 0 }}>
              <div style={{ fontSize: '10px', color: '#555', borderBottom: '1px dotted #999', paddingBottom: '6px', lineHeight: '1.3' }}>
                <strong>Placeholders:</strong> <code>{"{topic}"}</code>, <code>{"{secondary_topic}"}</code>, <code>{"{baseline_belief}"}</code>, <code>{"{current_belief}"}</code>. JSON rules are appended automatically.
              </div>
              
              <div className="form-group" style={{ display: 'flex', flexDirection: 'column', flexGrow: 1, minHeight: 0 }}>
                <label style={{ fontWeight: 'bold', fontSize: '11px', marginBottom: '3px' }}>Narrative Mutation System:</label>
                <textarea
                  value={localReaction}
                  onChange={(e) => setLocalReaction(e.target.value)}
                  style={{ flexGrow: 1, minHeight: '100px', fontSize: '10px', fontFamily: 'monospace', padding: '4px', border: '1px solid #7f9db9', backgroundColor: '#fff', color: '#000', resize: 'none', lineHeight: '1.3' }}
                />
              </div>

              <div className="form-group" style={{ display: 'flex', flexDirection: 'column', flexGrow: 1, minHeight: 0 }}>
                <label style={{ fontWeight: 'bold', fontSize: '11px', marginBottom: '3px' }}>Patient Zero Injection:</label>
                <textarea
                  value={localInjection}
                  onChange={(e) => setLocalInjection(e.target.value)}
                  style={{ flexGrow: 1, minHeight: '80px', fontSize: '10px', fontFamily: 'monospace', padding: '4px', border: '1px solid #7f9db9', backgroundColor: '#fff', color: '#000', resize: 'none', lineHeight: '1.3' }}
                />
              </div>

              <div style={{ display: 'flex', gap: '6px', marginTop: '2px', paddingBottom: '8px' }}>
                <button className="rct-button primary" style={{ flex: 1, padding: '4px', height: '24px', fontSize: '11px' }} onClick={() => { updatePrompts(localReaction, localInjection); alert('Prompts updated and applied to the engine!'); }}>Save & Apply</button>
                <button className="rct-button" style={{ padding: '4px', height: '24px', fontSize: '11px' }} onClick={() => { if (window.confirm('Reset templates to default?')) { setLocalReaction(defaultReactionTemplate); setLocalInjection(defaultInjectionTemplate); updatePrompts(defaultReactionTemplate, defaultInjectionTemplate); } }}>Reset</button>
              </div>
            </div>
          )}

          <div className="form-group" style={{ marginTop: '12px', marginBottom: '8px' }}>
            <label style={{ fontWeight: 'bold', fontSize: '11px' }}>Primary Topic / Seed:</label>
            <input type="text" value={narrativeInput} onChange={(e) => setNarrativeInput(e.target.value)} className="rct-text-input" style={{ width: '100%', marginTop: '3px', height: '24px' }} />
          </div>
          
          <div className="form-group" style={{ marginBottom: '8px' }}>
            <label style={{ fontWeight: 'bold', fontSize: '11px' }}>Secondary Topic (Optional):</label>
            <input type="text" value={secondaryTopicInput || ''} onChange={(e) => setSecondaryTopicInput(e.target.value)} className="rct-text-input" style={{ width: '100%', marginTop: '3px', height: '24px' }} placeholder="Leave blank for single topic" />
          </div>

          <div style={{ display: 'flex', gap: '8px', flexDirection: 'column' }}>
            <button className="rct-button primary block-btn" onClick={initializeSimulation}>
              <RefreshCw className="btn-icon" />
              Initialize Simulation
            </button>
            <div style={{ position: 'relative' }}>
              <input type="file" accept=".json" id="osint-upload" style={{ display: 'none' }} onChange={(e) => { if (e.target.files && e.target.files.length > 0) { uploadTopology(e.target.files[0]); e.target.value = null; } }} />
              <label htmlFor="osint-upload" className="rct-button block-btn" style={{ textAlign: 'center', cursor: 'pointer', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                <Upload className="btn-icon" />
                Upload OSINT Topology
              </label>
            </div>
          </div>
        </div>
      </div>

      <div className="rct-window" style={{ marginTop: '12px' }}>
        <div className="rct-titlebar">
          <Activity className="title-icon" />
          <span>Playback Control</span>
        </div>
        <div className="rct-panel playback-panel">
          <button className={`rct-button ${isPlaying ? 'pressed' : ''}`} onClick={togglePlay} disabled={!isInitialized}>
            {isPlaying ? <Pause className="btn-icon" /> : <Play className="btn-icon" />}
            {isPlaying ? 'Pause' : 'Auto Play'}
          </button>
          
          <button className="rct-button" onClick={stepSimulation} disabled={!isInitialized || isPlaying}>
            <SkipForward className="btn-icon" />
            Step Tick
          </button>
          
          <button className="rct-button" onClick={resetSimulation} disabled={!isInitialized && currentTick === 0}>
            <RotateCcw className="btn-icon" />
            Reset
          </button>

          <button className={`rct-button ${algorithmActive ? 'danger' : ''}`} onClick={toggleAlgorithm} disabled={!isInitialized}>
            <Zap className="btn-icon" />
            {algorithmActive ? 'Alg Feed: ON' : 'Alg Feed: OFF'}
          </button>
          
          <div style={{ marginLeft: 'auto', display: 'flex', gap: '4px' }}>
            <input type="file" accept=".json" id="session-upload" style={{ display: 'none' }} onChange={handleFileUpload} />
            <label htmlFor="session-upload" className="rct-button" style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center' }}>
              <Upload className="btn-icon" />
              Load
            </label>
            
            <button className="rct-button" onClick={exportSession} disabled={!isInitialized}>
              <Download className="btn-icon" />
              Export
            </button>
          </div>
        </div>
      </div>

      <ReligionPanel />
      <TopicsPanel />
      <ExportPanel />
    </section>
  );
}
