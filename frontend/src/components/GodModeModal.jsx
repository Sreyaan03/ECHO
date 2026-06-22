import React, { useState } from 'react';
import { ShieldAlert } from 'lucide-react';
import { useSimulationStore } from '../store/useSimulationStore';

export default function GodModeModal({ onClose }) {
  const { injectAlgorithm, wireEdge } = useSimulationStore();
  const [customAlgoCode, setCustomAlgoCode] = useState(`def custom_update(opinions, adjacency):
    # opinions: 1D array of floats
    # adjacency: 2D array of edges
    new_opinions = opinions.copy()
    # Write custom physics here
    return new_opinions`);
  const [wireSource, setWireSource] = useState('');
  const [wireTarget, setWireTarget] = useState('');

  return (
    <div className="rct-modal-overlay" style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.8)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="rct-modal-content god-mode-modal" style={{ width: '80%', maxWidth: '800px', backgroundColor: '#1a1a1a', border: '1px solid #444' }}>
        <div className="rct-titlebar danger-titlebar" style={{ backgroundColor: '#ff4444', color: '#fff', padding: '5px 10px', display: 'flex', alignItems: 'center' }}>
          <ShieldAlert className="title-icon" style={{marginRight: '10px'}} />
          <span style={{fontWeight: 'bold', letterSpacing: '1px'}}>GOD MODE: ALGORITHM INJECTION SANDBOX</span>
          <button className="rct-close-sm" onClick={onClose} style={{marginLeft: 'auto', background: 'none', border: 'none', color: '#fff', cursor: 'pointer', fontWeight: 'bold'}}>X</button>
        </div>
        
        <div className="rct-panel" style={{ display: 'flex', flexDirection: 'column', gap: '15px', padding: '15px' }}>
          <div className="form-group">
            <label style={{ color: '#ff4444', fontWeight: 'bold' }}>Inject Custom Physics (Python):</label>
            <textarea 
              value={customAlgoCode}
              onChange={(e) => setCustomAlgoCode(e.target.value)}
              style={{
                width: '100%', height: '250px', backgroundColor: '#1e1e1e', color: '#d4d4d4',
                fontFamily: 'monospace', padding: '10px', border: '1px solid #555', marginTop: '5px'
              }}
            />
            <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
              <button className="rct-button primary" onClick={() => injectAlgorithm(customAlgoCode)}>
                Compile & Inject
              </button>
              <button className="rct-button danger" onClick={() => { setCustomAlgoCode(""); injectAlgorithm(""); }}>
                Clear Custom Logic
              </button>
            </div>
          </div>

          <div className="form-group rct-inset" style={{ padding: '10px', border: '1px solid #333', backgroundColor: '#222' }}>
            <label style={{ fontWeight: 'bold', color: '#ccc' }}>Manual Network Rewiring:</label>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginTop: '5px' }}>
              <input type="number" placeholder="Source Agent ID" value={wireSource} onChange={(e)=>setWireSource(e.target.value)} className="rct-text-input" style={{flex: 1}} />
              <span style={{color: '#888'}}>&rarr;</span>
              <input type="number" placeholder="Target Agent ID" value={wireTarget} onChange={(e)=>setWireTarget(e.target.value)} className="rct-text-input" style={{flex: 1}} />
              <button className="rct-button danger" onClick={() => { if(wireSource && wireTarget) wireEdge(wireSource, wireTarget); }}>
                Force Edge
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
