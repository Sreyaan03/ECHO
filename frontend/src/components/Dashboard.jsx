import React, { useState, useEffect } from 'react';
import { useSimulationStore } from '../store/useSimulationStore';
import VoxelCanvas from './VoxelCanvas';
import SimulationControls from './SimulationControls';
import TelemetryPanel from './TelemetryPanel';
import AgentInspector from './AgentInspector';
import DoomsdayModal from './DoomsdayModal';
import GodModeModal from './GodModeModal';
import { Zap, ShieldAlert, MoreVertical } from 'lucide-react';

export default function Dashboard() {
  const { currentTick, edgesSevered, edgesFormed, initializeSimulation, fetchPrompts } = useSimulationStore();
  const [showDoomsday, setShowDoomsday] = useState(false);
  const [showGodMode, setShowGodMode] = useState(false);

  // Auto initialize on first load
  useEffect(() => {
    initializeSimulation();
    fetchPrompts();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
            Edges Formed: <span style={{ color: '#228B22', fontWeight: 'bold' }}>{edgesFormed}</span>
          </div>
          <div className="rct-status-badge" style={{ cursor: 'pointer', padding: '0 4px' }} onClick={() => setShowGodMode(true)} title="God Mode">
            <MoreVertical className="btn-icon" size={16} />
          </div>
        </div>
      </header>

      {/* Main Sandbox Grid Workspace */}
      <main className="rct-grid">
        <SimulationControls />

        {/* Center 3D Voxel Playfield */}
        <section className="rct-canvas-section">
          <VoxelCanvas />
        </section>

        <AgentInspector />
      </main>

      <TelemetryPanel />

      {/* Floating Doomsday Button */}
      <div style={{ position: 'fixed', bottom: '20px', right: '20px', zIndex: 1000 }}>
        <button 
          onClick={() => setShowDoomsday(true)}
          style={{
            width: '60px', height: '60px', borderRadius: '50%',
            backgroundColor: '#ff0000', border: '3px solid #8b0000',
            boxShadow: '0 0 15px rgba(255,0,0,0.8), inset 0 0 10px rgba(0,0,0,0.5)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', animation: 'pulse 2s infinite'
          }}
          title="Global Exogenous Shock"
        >
          <ShieldAlert color="white" size={30} />
        </button>
      </div>

      {showDoomsday && <DoomsdayModal onClose={() => setShowDoomsday(false)} />}
      {showGodMode && <GodModeModal onClose={() => setShowGodMode(false)} />}
    </div>
  );
}
