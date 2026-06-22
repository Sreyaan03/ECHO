import { create } from 'zustand';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';
const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws');

// Web Audio API Synthesizer
let audioCtx = null;
const initAudio = () => {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
};

const playSound = (type, params = {}) => {
  if (!audioCtx) return;
  if (audioCtx.state === 'suspended') audioCtx.resume();
  
  const osc = audioCtx.createOscillator();
  const gainNode = audioCtx.createGain();
  
  osc.connect(gainNode);
  gainNode.connect(audioCtx.destination);
  
  const now = audioCtx.currentTime;
  
  if (type === 'tick') {
    // Soft low pop
    osc.type = 'sine';
    osc.frequency.setValueAtTime(150, now);
    osc.frequency.exponentialRampToValueAtTime(40, now + 0.1);
    gainNode.gain.setValueAtTime(0.05, now);
    gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.1);
    osc.start(now);
    osc.stop(now + 0.1);
  } else if (type === 'sever') {
    // Sharp snap, pitch based on count
    const count = params.count || 1;
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(400 + Math.min(count * 20, 400), now);
    osc.frequency.exponentialRampToValueAtTime(100, now + 0.1);
    gainNode.gain.setValueAtTime(0.1, now);
    gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.1);
    osc.start(now);
    osc.stop(now + 0.1);
  } else if (type === 'inject') {
    // Digital chime
    osc.type = 'sine';
    osc.frequency.setValueAtTime(600, now);
    osc.frequency.exponentialRampToValueAtTime(1200, now + 0.2);
    gainNode.gain.setValueAtTime(0.15, now);
    gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
    osc.start(now);
    osc.stop(now + 0.3);
  }
};

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
      p: 0.2,
      sbm_blocks: 3,
      sbm_p_in: 0.3,
      sbm_p_out: 0.01
    },
    p_bots: 0.0,
    belief_dist: 'uniform'
  },

  // State
  algorithmActive: false,
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
  socket: null,
  isInitializing: false,

  // Actions
  setConfig: (newConfig) => set((state) => ({ config: { ...state.config, ...newConfig } })),
  setNarrativeInput: (val) => set({ narrativeInput: val }),
  setCustomRumor: (val) => set({ customRumor: val }),
  selectAgent: (agentId) => set({ selectedAgentId: agentId }),

  initializeSimulation: async () => {
    const { config, socket } = get();
    
    if (socket) {
      socket.send(JSON.stringify({ action: 'pause' }));
      socket.close();
      set({ socket: null, isPlaying: false });
    }

    set({ isInitializing: true });
    initAudio();

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
      get().connectWebSocket();
    } catch (error) {
      console.error('Initialization error:', error);
      alert('Error initializing simulation. Make sure the Python backend is running on port 8000.');
    } finally {
      set({ isInitializing: false });
    }
  },

  uploadTopology: async (file) => {
    const { config, socket } = get();
    
    if (socket) {
      socket.send(JSON.stringify({ action: 'pause' }));
      socket.close();
      set({ socket: null, isPlaying: false });
    }

    set({ isInitializing: true });

    initAudio();

    try {
      const formData = new FormData();
      formData.append('file', file);
      
      // Append config params
      for (const [key, value] of Object.entries(config)) {
        if (typeof value === 'number' || typeof value === 'string') {
          formData.append(key, value);
        }
      }

      const response = await fetch(`${API_BASE_URL}/upload_topology`, {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) throw new Error('Failed to upload OSINT topology');
      
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
      get().connectWebSocket();
    } catch (error) {
      console.error('Upload error:', error);
      alert('Error uploading topology. Check backend connection and file format.');
    } finally {
      set({ isInitializing: false });
    }
  },

  connectWebSocket: () => {
    const ws = new WebSocket(`${WS_BASE_URL}/ws/simulation`);
    ws.onmessage = async (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'step_result') {
        const data = msg.data;
        
        // Update the agents array with new beliefs and arousals
        const updatedAgents = get().agents.map((agent, index) => ({
          ...agent,
          belief: data.beliefs[index],
          arousal: data.arousals[index]
        }));

        // Fetch fresh telemetry from server
        // To avoid spamming, we could let the WS send telemetry, but for now we fetch it if not provided.
        // Let's fetch since we know the telemetry endpoint exists.
        const telRes = await fetch(`${API_BASE_URL}/telemetry`);
        const telemetryData = telRes.ok ? await telRes.json() : get().telemetry;

        // Audio Feedback
        playSound('tick');
        const newlySevered = data.edges_severed - get().edgesSevered;
        if (newlySevered > 0) {
          playSound('sever', { count: newlySevered });
        }

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
      } else if (msg.type === 'error') {
        console.error('WebSocket Error:', msg.message);
        get().pauseSimulation();
      }
    };
    ws.onclose = () => set({ isPlaying: false, socket: null });
    set({ socket: ws });
  },

  stepSimulation: async () => {
    const { isInitialized, socket } = get();
    if (!isInitialized || !socket || socket.readyState !== WebSocket.OPEN) return false;
    socket.send(JSON.stringify({ action: 'step' }));
    return true;
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
      
      initAudio();
      playSound('inject');
      
      if (get().selectedAgentId === agentId) {
        // Refresh selected agent detail
        set({ selectedAgentId: agentId });
      }
    } catch (error) {
      console.error('Injection error:', error);
    }
  },

  globalBroadcast: async (beliefShift, arousalShift, message) => {
    try {
      const response = await fetch(`${API_BASE_URL}/broadcast`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ belief_shift: beliefShift, arousal_shift: arousalShift, message: message })
      });

      if (!response.ok) throw new Error('Failed to broadcast global shock');

      const data = await response.json();
      
      // Update local agents array
      const updatedAgents = get().agents.map((agent, index) => ({
        ...agent,
        belief: data.beliefs[index],
        arousal: data.arousals[index]
      }));

      set({ 
        agents: updatedAgents,
        mutatedNarratives: data.narrative_logs || []
      });
      
      initAudio();
      playSound('inject'); // Maybe add a new sound effect here later, for now reuse inject
      
    } catch (error) {
      console.error('Broadcast error:', error);
    }
  },

  injectAlgorithm: async (codeString) => {
    try {
      const response = await fetch(`${API_BASE_URL}/godmode/algorithm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code_string: codeString })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Failed to inject custom algorithm');
      alert(data.message);
    } catch (error) {
      console.error('Algorithm injection error:', error);
      alert('Error: ' + error.message);
    }
  },

  wireEdge: async (sourceId, targetId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/godmode/wire`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_id: parseInt(sourceId), target_id: parseInt(targetId) })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Failed to wire edge');
      set({ edges: data.edges });
      alert("Edge forced successfully.");
    } catch (error) {
      console.error('Wire edge error:', error);
      alert('Error: ' + error.message);
    }
  },

  startSimulationLoop: () => {
    const { isPlaying, socket } = get();
    if (isPlaying || !socket || socket.readyState !== WebSocket.OPEN) return;

    socket.send(JSON.stringify({ action: 'play' }));
    set({ isPlaying: true });
  },

  pauseSimulation: () => {
    const { socket } = get();
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ action: 'pause' }));
    }
    set({ isPlaying: false });
  },

  togglePlay: () => {
    const { isPlaying } = get();
    if (isPlaying) {
      get().pauseSimulation();
    } else {
      get().startSimulationLoop();
    }
  },

  toggleAlgorithm: async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/toggle_algorithm`, { method: 'POST' });
      if (response.ok) {
        const data = await response.json();
        set({ algorithmActive: data.algorithm_active });
      }
    } catch (error) {
      console.error('Failed to toggle algorithm:', error);
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
  },

  resetSimulation: () => {
    const { socket } = get();
    if (socket) {
      socket.send(JSON.stringify({ action: 'pause' }));
      socket.close();
    }
    
    set({
      isInitialized: false,
      isPlaying: false,
      socket: null,
      algorithmActive: false,
      currentTick: 0,
      agents: [],
      edges: [],
      activeInfluencers: [],
      edgesSevered: 0,
      edgesFormed: 0,
      selectedAgentId: null,
      telemetry: {
        current_tick: 0,
        polarization: 0,
        avg_belief: 0,
        edges_severed: 0,
        edges_formed: 0,
        history: []
      },
      mutatedNarratives: []
    });
  },

  loadSession: (sessionData) => {
    const { socket } = get();
    if (socket) {
      socket.send(JSON.stringify({ action: 'pause' }));
      socket.close();
    }
    
    if (!sessionData || !sessionData.agents || !sessionData.edges) {
      alert("Invalid session data. Cannot load.");
      return;
    }
    
    // Attempt to reconstruct history object
    const finalPol = sessionData.final_polarization || 0;
    
    set({
      isInitialized: true,
      isPlaying: false,
      playInterval: null,
      currentTick: sessionData.total_ticks || 0,
      agents: sessionData.agents,
      edges: sessionData.edges,
      telemetry: {
        current_tick: sessionData.total_ticks || 0,
        polarization: finalPol,
        avg_belief: 0,
        edges_severed: 0,
        edges_formed: 0,
        history: sessionData.history || []
      },
      mutatedNarratives: sessionData.narrative_logs || [],
      selectedAgentId: null
    });
    
    alert("Session loaded successfully! 3D Canvas updated.");
  }
}));
