import React from 'react';
import { Download, FileText, Table, Settings2, MessageSquare } from 'lucide-react';
import { useSimulationStore } from '../store/useSimulationStore';

export default function ExportPanel() {
  const {
    isInitialized,
    currentTick,
    exportTelemetryCSV,
    exportBeliefsCSV,
    exportConfig,
    exportSession,
    mutatedNarratives,
  } = useSimulationStore();

  const canExport = isInitialized && currentTick > 0;

  const downloadNarratives = () => {
    if (!mutatedNarratives || mutatedNarratives.length === 0) {
      alert('No narratives to download yet.');
      return;
    }
    const blob = new Blob([JSON.stringify(mutatedNarratives, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `echo_narratives_tick${currentTick}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="rct-window" style={{ marginTop: '12px' }}>
      <div className="rct-titlebar">
        <Download className="title-icon" />
        <span>Export Experiment Data</span>
      </div>
      <div className="rct-panel" style={{ display: 'flex', flexDirection: 'column', gap: '5px', padding: '8px' }}>

        {!canExport && (
          <p style={{ fontSize: '10px', color: '#888', textAlign: 'center', margin: '4px 0 6px' }}>
            Initialize & run at least 1 tick to unlock exports.
          </p>
        )}

        <button
          className="rct-button block-btn"
          onClick={exportTelemetryCSV}
          disabled={!canExport}
          title="Per-tick aggregate metrics: polarization, avg belief, edge counts"
        >
          <Table className="btn-icon" size={12} />
          Telemetry CSV
        </button>

        <button
          className="rct-button block-btn"
          onClick={exportBeliefsCSV}
          disabled={!canExport}
          title="Full N×T belief trajectory matrix — one row per tick, one column per agent"
        >
          <FileText className="btn-icon" size={12} />
          Beliefs Matrix CSV
        </button>

        <button
          className="rct-button block-btn"
          onClick={exportConfig}
          disabled={!isInitialized}
          title="Reproducible experiment parameters for replication"
        >
          <Settings2 className="btn-icon" size={12} />
          Config JSON
        </button>

        <button
          className="rct-button block-btn"
          onClick={downloadNarratives}
          disabled={mutatedNarratives.length === 0}
          title="All LLM-generated narrative mutations with timestamps"
        >
          <MessageSquare className="btn-icon" size={12} />
          Narratives JSON
        </button>

        <div style={{ borderTop: '1px dotted #aaa', marginTop: '4px', paddingTop: '5px' }}>
          <button
            className="rct-button block-btn"
            onClick={exportSession}
            disabled={!canExport}
            title="Full snapshot: agents, edges, history, narratives"
            style={{ fontSize: '10px', opacity: 0.8 }}
          >
            <Download className="btn-icon" size={11} />
            Full Session JSON
          </button>
        </div>
      </div>
    </div>
  );
}
