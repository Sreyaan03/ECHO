import React, { useState } from 'react';
import { ShieldAlert } from 'lucide-react';
import { useSimulationStore } from '../store/useSimulationStore';

export default function DoomsdayModal({ onClose }) {
  const { globalBroadcast } = useSimulationStore();
  const [doomsdayMsg, setDoomsdayMsg] = useState("Market Crash");
  const [doomsdayBeliefShift, setDoomsdayBeliefShift] = useState(0.0);
  const [doomsdayArousalShift, setDoomsdayArousalShift] = useState(0.5);

  const executeDoomsday = async () => {
    if (window.confirm("WARNING: This will instantly mutate the entire network. Proceed?")) {
      await globalBroadcast(doomsdayBeliefShift, doomsdayArousalShift, doomsdayMsg);
      onClose();
    }
  };

  return (
    <div 
      onClick={onClose}
      style={{
        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
        backgroundColor: 'rgba(0,0,0,0.8)', zIndex: 9999,
        display: 'flex', alignItems: 'center', justifyContent: 'center'
      }}
    >
      <div 
        onClick={(e) => e.stopPropagation()}
        style={{
          backgroundColor: '#1a1a1a', border: '4px solid #ff0000',
          borderRadius: '10px', padding: '30px', width: '400px',
          color: '#fff', textAlign: 'center',
          boxShadow: '0 0 30px rgba(255,0,0,0.5)',
          position: 'relative'
        }}
      >
        <button 
          onClick={onClose}
          style={{ position: 'absolute', top: '10px', right: '15px', background: 'transparent', border: 'none', color: '#ff0000', fontSize: '20px', cursor: 'pointer', fontWeight: 'bold' }}
        >
          ×
        </button>
        <ShieldAlert color="#ff0000" size={50} style={{ marginBottom: '15px' }} />
        <h2 style={{ color: '#ff0000', margin: '0 0 20px 0', textTransform: 'uppercase', letterSpacing: '2px' }}>
          Global Exogenous Shock
        </h2>
        <p style={{ fontSize: '12px', color: '#ccc', marginBottom: '20px' }}>
          Warning: This will broadcast an event to the entire network instantly, overwriting standard peer-to-peer propagation.
        </p>
        
        <div className="form-group" style={{ textAlign: 'left', marginBottom: '15px' }}>
          <label style={{ color: '#aaa' }}>Event Message / Narrative:</label>
          <input 
            type="text" 
            value={doomsdayMsg} 
            onChange={(e) => setDoomsdayMsg(e.target.value)}
            style={{ width: '100%', padding: '8px', backgroundColor: '#333', border: '1px solid #555', color: '#fff', borderRadius: '4px' }}
          />
        </div>
        
        <div className="form-group" style={{ textAlign: 'left', marginBottom: '15px' }}>
          <label style={{ color: '#aaa' }}>Belief Shift (-1.0 to 1.0):</label>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <input 
              type="range" min="-1.0" max="1.0" step="0.05"
              value={doomsdayBeliefShift}
              onChange={(e) => setDoomsdayBeliefShift(parseFloat(e.target.value))}
              style={{ flex: 1, accentColor: '#ff0000' }}
            />
            <span style={{ minWidth: '40px', textAlign: 'right' }}>{doomsdayBeliefShift.toFixed(2)}</span>
          </div>
        </div>

        <div className="form-group" style={{ textAlign: 'left', marginBottom: '25px' }}>
          <label style={{ color: '#aaa' }}>Arousal / Panic Spike (0.0 to 1.0):</label>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <input 
              type="range" min="0.0" max="1.0" step="0.05"
              value={doomsdayArousalShift}
              onChange={(e) => setDoomsdayArousalShift(parseFloat(e.target.value))}
              style={{ flex: 1, accentColor: '#ff0000' }}
            />
            <span style={{ minWidth: '40px', textAlign: 'right' }}>{doomsdayArousalShift.toFixed(2)}</span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
          <button 
            type="button"
            onClick={(e) => { e.stopPropagation(); onClose(); }}
            style={{ padding: '10px 20px', backgroundColor: '#333', border: 'none', color: '#fff', borderRadius: '4px', cursor: 'pointer' }}
          >
            ABORT
          </button>
          <button 
            type="button"
            onClick={(e) => { e.stopPropagation(); executeDoomsday(); }}
            style={{ 
              padding: '10px 20px', backgroundColor: '#ff0000', border: '2px solid #8b0000', 
              color: '#fff', fontWeight: 'bold', borderRadius: '4px', cursor: 'pointer',
              textTransform: 'uppercase'
            }}
          >
            EXECUTE SHOCK
          </button>
        </div>
      </div>
    </div>
  );
}
