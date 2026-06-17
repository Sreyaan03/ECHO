import { create } from 'zustand';

const API_BASE_URL = 'http://127.0.0.1:8000/api';

export const useSimulationStore = create((set, get) => ({
  // Simulation Configuration
  config: {
    n_agents: 500,
    topology: 'small_world',
    w_pol: 0.4,
    w_econ: 0.3,
    w_rel: 0.3,
    d_tolerance: 0.5,
    gamma: 0.1,
    n_religious_groups: 3,
    seed: 42,
    fatigue_limit: 5,
    topology_params: {
      m: 3,
      k: 8,
      p: 0.2
    }
  },

  // State
  isInitialized: false,
  isPlaying: false,
  currentTick: 0,
  agents: [],
  edges: [],
  positions: {},
  activeInfluencers: [],
  edgesSevered: 0,
  edgesFormed: 0,
  selectedAgentId: null,
  narrativeInput: 'The new water plant is poisoning the river',
  customRumor: 'I heard the local tap water tastes like metal...',
  mutatedNarratives: [],
  reactionTemplate: '',
  injectionTemplate: '',
  defaultReactionTemplate: '',
  defaultInjectionTemplate: '',
  telemetry: {
    current_tick: 0,
    polarization: 0,
    avg_belief: 0,
    edges_severed: 0,
    edges_formed: 0,
    history: []
  },
  
  // Animation / Interval reference for auto-playing
  playInterval: null,

  // Actions
  setConfig: (newConfig) => set((state) => ({ config: { ...state.config, ...newConfig } })),
  setNarrativeInput: (val) => set({ narrativeInput: val }),
  setCustomRumor: (val) => set({ customRumor: val }),
  selectAgent: (agentId) => set({ selectedAgentId: agentId }),

  initializeSimulation: async () => {
    const { config, playInterval } = get();
    
    // Stop any existing intervals
    if (playInterval) {
      clearInterval(playInterval);
      set({ playInterval: null, isPlaying: false });
    }

    try {
      const response = await fetch(`${API_BASE_URL}/initialize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...config, topic: get().narrativeInput })
      });
      
      if (!response.ok) throw new Error('Failed to initialize simulation backend');
      
      const data = await response.json();
      
      set({
        isInitialized: true,
        currentTick: 0,
        agents: data.agents,
        edges: data.edges,
        positions: data.positions,
        activeInfluencers: [],
        edgesSevered: 0,
        edgesFormed: 0,
        selectedAgentId: null,
        telemetry: data.telemetry,
        mutatedNarratives: data.narrative_logs || []
      });
    } catch (error) {
      console.error('Initialization error:', error);
      alert('Error initializing simulation. Make sure the Python backend is running on port 8000.');
    }
  },

  stepSimulation: async () => {
    const { isInitialized } = get();
    if (!isInitialized) return false;

    try {
      const response = await fetch(`${API_BASE_URL}/step`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!response.ok) throw new Error('Failed to compute tick');

      const data = await response.json();

      // Update the agents array with new beliefs and arousals
      const updatedAgents = get().agents.map((agent, index) => ({
        ...agent,
        belief: data.beliefs[index],
        arousal: data.arousals[index]
      }));

      // Fetch fresh telemetry from server
      const telRes = await fetch(`${API_BASE_URL}/telemetry`);
      const telemetryData = telRes.ok ? await telRes.json() : get().telemetry;

      set({
        currentTick: data.tick,
        agents: updatedAgents,
        edges: data.edges,
        edgesSevered: data.edges_severed,
        edgesFormed: data.edges_formed,
        activeInfluencers: data.active_influencers,
        telemetry: telemetryData,
        mutatedNarratives: data.narrative_logs || []
      });

      // Return true if simulation is still moving (optional check)
      return true;
    } catch (error) {
      console.error('Step error:', error);
      get().pauseSimulation();
      return false;
    }
  },

  injectNarrative: async (agentId, beliefScore, message) => {
    try {
      const response = await fetch(`${API_BASE_URL}/inject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: agentId, belief_score: beliefScore, message: message })
      });

      if (!response.ok) throw new Error('Failed to inject narrative');

      const data = await response.json();
      
      // Update local agent
      const updatedAgents = get().agents.map((agent) => 
        agent.agent_id === agentId ? { ...agent, belief: data.agent.belief } : agent
      );

      set({ 
        agents: updatedAgents,
        mutatedNarratives: data.narrative_logs || []
      });
      
      if (get().selectedAgentId === agentId) {
        // Refresh selected agent detail
        set({ selectedAgentId: agentId });
      }
    } catch (error) {
      console.error('Injection error:', error);
    }
  },

  startSimulationLoop: () => {
    const { isPlaying, playInterval } = get();
    if (isPlaying || playInterval) return;

    const interval = setInterval(async () => {
      await get().stepSimulation();
    }, 1000); // Step every 1 second

    set({ isPlaying: true, playInterval: interval });
  },

  pauseSimulation: () => {
    const { playInterval } = get();
    if (playInterval) {
      clearInterval(playInterval);
    }
    set({ isPlaying: false, playInterval: null });
  },

  togglePlay: () => {
    const { isPlaying } = get();
    if (isPlaying) {
      get().pauseSimulation();
    } else {
      get().startSimulationLoop();
    }
  },

  fetchPrompts: async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/prompts`);
      if (response.ok) {
        const data = await response.json();
        set({
          reactionTemplate: data.reaction_template,
          injectionTemplate: data.injection_template,
          defaultReactionTemplate: data.default_reaction_template,
          defaultInjectionTemplate: data.default_injection_template
        });
      }
    } catch (error) {
      console.error('Failed to fetch prompts:', error);
    }
  },

  updatePrompts: async (reaction, injection) => {
    try {
      const response = await fetch(`${API_BASE_URL}/prompts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reaction_template: reaction,
          injection_template: injection
        })
      });
      if (response.ok) {
        set({
          reactionTemplate: reaction,
          injectionTemplate: injection
        });
      }
    } catch (error) {
      console.error('Failed to update prompts:', error);
    }
  },

  exportSession: async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/export`);
      if (!response.ok) throw new Error('Failed to export session');
      
      const data = await response.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      
      const a = document.createElement('a');
      a.href = url;
      a.download = `echo_session_export_tick_${data.total_ticks}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export error:', error);
      alert('Failed to export session data.');
    }
  }
}));
