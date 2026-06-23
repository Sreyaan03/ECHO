import React from 'react';
import { useSimulationStore } from '../store/useSimulationStore';

const ReligionPanel = () => {
  const narrativeProfile = useSimulationStore(state => state.narrativeProfile);

  if (!narrativeProfile) {
    return null;
  }

  // Find max sensitivity for bar scaling
  const maxSens = Math.max(...Object.values(narrativeProfile.group_sensitivity || {}));

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 mt-4 shadow-sm text-sm">
      <h3 className="text-gray-300 font-semibold mb-3 border-b border-gray-700 pb-2">
        Sociological Profile
      </h3>
      
      <div className="mb-3">
        <div className="flex justify-between items-center mb-1">
          <span className="text-gray-400">Classified Topic:</span>
          <span className="bg-blue-900/50 text-blue-300 px-2 py-0.5 rounded text-xs font-mono border border-blue-800">
            {narrativeProfile.topic_name}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-gray-400">Inherent Bias (Valence):</span>
          <span className={`font-mono ${narrativeProfile.initial_belief_valence > 0 ? 'text-green-400' : narrativeProfile.initial_belief_valence < 0 ? 'text-red-400' : 'text-gray-400'}`}>
            {narrativeProfile.initial_belief_valence.toFixed(2)}
          </span>
        </div>
        <div className="flex justify-between items-center mt-1">
          <span className="text-gray-400">Virality (Arousal Spike):</span>
          <span className="text-purple-400 font-mono">
            {(narrativeProfile.initial_arousal_spike * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      <div className="mt-4">
        <h4 className="text-gray-400 text-xs uppercase tracking-wider mb-2 font-semibold">Group Sensitivity Matrix</h4>
        <div className="space-y-2">
          {Object.entries(narrativeProfile.group_sensitivity || {}).map(([group, val]) => (
            <div key={group} className="flex items-center">
              <span className="w-20 text-gray-300 text-xs truncate">{group}</span>
              <div className="flex-1 bg-gray-900 h-2.5 rounded-full overflow-hidden mx-2 relative">
                <div 
                  className={`absolute top-0 left-0 h-full rounded-full ${val > 0.7 ? 'bg-red-500' : val > 0.4 ? 'bg-orange-400' : 'bg-green-500'}`}
                  style={{ width: `${Math.max(5, val * 100)}%` }}
                />
              </div>
              <span className="w-8 text-right font-mono text-xs text-gray-500">
                {val.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-gray-500 mt-2 italic">
          Higher sensitivity drastically shrinks the group's open-mindedness (d_tolerance) on this topic.
        </p>
      </div>
    </div>
  );
};

export default ReligionPanel;
