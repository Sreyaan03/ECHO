import React from 'react';
import { useSimulationStore } from '../store/useSimulationStore';
import { Layers, Zap } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';

export default function TopicsPanel() {
  const { isInitialized, topics, activeTopicFilter, setActiveTopicFilter } = useSimulationStore();

  if (!isInitialized || topics.length === 0) return null;

  const handleShock = async (topicId) => {
    try {
      // Pick a random agent and inject an extreme belief
      const randomAgent = Math.floor(Math.random() * 500);
      const randomBelief = Math.random() > 0.5 ? 1.0 : -1.0;
      await fetch(`${API_BASE_URL}/inject_topic`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: randomAgent,
          topic_id: topicId,
          belief_score: randomBelief
        })
      });
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="rct-window" style={{ marginTop: '12px' }}>
      <div className="rct-titlebar">
        <Layers className="title-icon" />
        <span>Active Contagion Topics</span>
      </div>
      <div className="rct-panel" style={{ padding: '8px' }}>
        
        {topics.map(topic => (
          <div key={topic.topic_id} style={{ 
            marginBottom: '8px', 
            padding: '6px', 
            border: '1px solid #7f9db9', 
            backgroundColor: '#fff' 
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong style={{ fontSize: '11px' }}>{topic.name}</strong>
              <button 
                className="rct-button" 
                style={{ height: '20px', padding: '0 6px', fontSize: '10px' }}
                onClick={() => handleShock(topic.topic_id)}
                title="Inject extreme narrative"
              >
                <Zap size={10} style={{ marginRight: '2px' }}/>
                Shock
              </button>
            </div>
            
            <div style={{ marginTop: '4px', fontSize: '10px' }}>
              Avg Belief: {topic.avg_belief.toFixed(2)}
            </div>
            <div style={{
              width: '100%',
              height: '4px',
              backgroundColor: '#ccc',
              marginTop: '4px',
              position: 'relative'
            }}>
              <div style={{
                position: 'absolute',
                left: `${(topic.avg_belief + 1.0) / 2.0 * 100}%`,
                width: '2px',
                height: '10px',
                top: '-3px',
                backgroundColor: 'red'
              }} />
            </div>
          </div>
        ))}

        {topics.length > 1 && (
          <div style={{ marginTop: '12px', borderTop: '1px solid #ccc', paddingTop: '8px' }}>
            <label style={{ fontSize: '11px', fontWeight: 'bold' }}>Canvas Overlay Mode:</label>
            <div style={{ display: 'flex', gap: '4px', marginTop: '4px' }}>
              <button 
                className={`rct-button ${activeTopicFilter === 0 ? 'active pressed' : ''}`}
                style={{ flex: 1, fontSize: '10px' }}
                onClick={() => setActiveTopicFilter(0)}
              >
                Topic A
              </button>
              <button 
                className={`rct-button ${activeTopicFilter === 1 ? 'active pressed' : ''}`}
                style={{ flex: 1, fontSize: '10px' }}
                onClick={() => setActiveTopicFilter(1)}
              >
                Topic B
              </button>
              <button 
                className={`rct-button ${activeTopicFilter === null ? 'active pressed' : ''}`}
                style={{ flex: 1, fontSize: '10px' }}
                onClick={() => setActiveTopicFilter(null)}
              >
                Blended
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
