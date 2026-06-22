import React, { useRef, useMemo, useEffect, useState, useCallback } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, OrthographicCamera } from '@react-three/drei';
import { EffectComposer, Noise, Pixelation } from '@react-three/postprocessing';
import * as THREE from 'three';
import { quadtree } from 'd3-quadtree';
import { useSimulationStore } from '../store/useSimulationStore';

// Checkerboard grass texture creator
const createCheckerboardTexture = () => {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext('2d');

  // RCT Checkered Grass colors
  const size = 64;
  ctx.fillStyle = '#76a035'; // light green
  ctx.fillRect(0, 0, size, size);
  ctx.fillRect(size, size, size, size);

  ctx.fillStyle = '#688e2e'; // dark green
  ctx.fillRect(size, 0, size, size);
  ctx.fillRect(0, size, size, size);

  // Add subtle borders between squares for a grid-map editor look
  ctx.strokeStyle = '#5e8128';
  ctx.lineWidth = 2;
  ctx.strokeRect(0, 0, 128, 128);
  ctx.strokeRect(64, 0, 64, 64);
  ctx.strokeRect(0, 64, 64, 64);

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(40, 40);
  texture.minFilter = THREE.NearestFilter;
  texture.magFilter = THREE.NearestFilter;
  return texture;
};

// Shared Aesthetic Color constants
const COLOR_LEFT = new THREE.Color('#9A8B9E');   // Muted Lavender
const COLOR_NEUTRAL = new THREE.Color('#8BA88E'); // Sage Green
const COLOR_RIGHT = new THREE.Color('#8B4513');   // Saddle Brown
const COLOR_PULSE = new THREE.Color('#B22222');   // Deep Brick Red
const COLOR_HOVER = new THREE.Color('#FFE4B5');   // Moccasin highlight
const COLOR_FACT_CHECKER = new THREE.Color('#FFFFFF'); // Bright White

// ============================================================================
// Force-Directed Physics Constants
// ============================================================================
const REPULSION_STRENGTH = 20.0;     // Coulomb repulsion constant (Reduced by 4x to compensate for un-skipping)
const ATTRACTION_STRENGTH = 0.01;    // Hooke spring constant
const GRAVITY_STRENGTH = 0.008;      // Central pull toward origin
const DAMPING = 0.85;                // Velocity friction per frame
const MAX_VELOCITY = 2.0;            // Velocity clamp to prevent explosion
const REST_LENGTH = 3.0;             // Natural rest length of springs
const EPSILON = 0.01;                // Prevent division-by-zero

// ============================================================================
// ForceDirectedSimulation — Core Physics Component
// ============================================================================
// This component runs the force-directed layout in useFrame and shares
// live positions via a shared mutable ref passed to child components.
function ForceDirectedSimulation({ livePositionsRef }) {
  const { agents, positions: storePositions, edges } = useSimulationStore();
  
  const velocitiesRef = useRef(null);
  const nodesRef = useRef([]);
  
  // Track the previous positions fingerprint to detect re-initialization
  const prevPositionsFingerprintRef = useRef(null);

  // Seed positions and velocities from store whenever the store positions change
  // (i.e., on initialize)
  useEffect(() => {
    const posKeys = Object.keys(storePositions);
    if (posKeys.length === 0) return;

    // Simple fingerprint to detect if positions actually changed
    const fingerprint = posKeys.length + '_' + (storePositions[0]?.x || 0).toFixed(3);
    if (fingerprint === prevPositionsFingerprintRef.current) return;
    prevPositionsFingerprintRef.current = fingerprint;

    const n = agents.length || posKeys.length;
    
    // Initialize position buffer: Float32Array [x0, z0, x1, z1, ...]
    const posArr = new Float32Array(n * 2);
    // Initialize velocity buffer: Float32Array [vx0, vz0, vx1, vz1, ...]
    const velArr = new Float32Array(n * 2);
    
    for (let i = 0; i < n; i++) {
      const sp = storePositions[i];
      if (sp) {
        posArr[i * 2] = sp.x;
        posArr[i * 2 + 1] = sp.z;
      }
      // Velocities start at zero
      velArr[i * 2] = 0;
      velArr[i * 2 + 1] = 0;
    }

    livePositionsRef.current = posArr;
    velocitiesRef.current = velArr;
  }, [storePositions, agents.length]);

  // Force-directed physics loop — runs every frame (~60fps)
  useFrame(() => {
    const posArr = livePositionsRef.current;
    const velArr = velocitiesRef.current;
    if (!posArr || !velArr) return;

    const n = posArr.length / 2;
    if (n < 2) return;

    // Temporary force accumulators
    const fx = new Float32Array(n);
    const fz = new Float32Array(n);

    // ────────────────────────────────────────────────────────────
    // 1. REPULSION FORCE (Barnes-Hut Quadtree O(N log N))
    // ────────────────────────────────────────────────────────────
    const nodes = nodesRef.current;
    if (nodes.length !== n) {
      nodes.length = 0;
      for (let i = 0; i < n; i++) nodes.push({ x: 0, y: 0, index: i });
    }

    for (let i = 0; i < n; i++) {
      nodes[i].x = posArr[i * 2];
      nodes[i].y = posArr[i * 2 + 1];
    }

    const tree = quadtree()
      .x(d => d.x)
      .y(d => d.y)
      .addAll(nodes);

    tree.visitAfter((quad) => {
      let weight = 0, x = 0, y = 0;
      if (quad.length) {
        for (let i = 0; i < 4; ++i) {
          const q = quad[i];
          if (q && q.value) {
            weight += q.value;
            x += q.x * q.value;
            y += q.y * q.value;
          }
        }
        quad.x = x / weight;
        quad.y = y / weight;
        quad.value = weight;
      } else {
        quad.x = quad.data.x;
        quad.y = quad.data.y;
        quad.value = 1;
      }
    });

    const theta2 = 0.81;
    for (let i = 0; i < n; i++) {
      const node = nodes[i];
      tree.visit((quad, x1, y1, x2, y2) => {
        if (!quad.value) return true;
        const dx = quad.x - node.x;
        const dz = quad.y - node.y;
        const w = x2 - x1;
        const l = dx * dx + dz * dz;

        if (w * w / theta2 < l) {
          const distSq = l + EPSILON;
          const dist = Math.sqrt(distSq);
          const force = (REPULSION_STRENGTH * quad.value) / distSq;
          fx[i] -= (dx / dist) * force;
          fz[i] -= (dz / dist) * force;
          return true;
        } else if (quad.length) {
          return false;
        }

        if (quad.data !== node) {
          const distSq = l + EPSILON;
          const dist = Math.sqrt(distSq);
          const force = REPULSION_STRENGTH / distSq;
          fx[i] -= (dx / dist) * force;
          fz[i] -= (dz / dist) * force;
        }
      });
    }

    // ────────────────────────────────────────────────────────────
    // 2. SPRING ATTRACTION FORCE (Hooke's Law) for active edges
    // ────────────────────────────────────────────────────────────
    for (let e = 0; e < edges.length; e++) {
      const u = edges[e][0];
      const v = edges[e][1];
      if (u >= n || v >= n) continue;

      const dx = posArr[v * 2] - posArr[u * 2];
      const dz = posArr[v * 2 + 1] - posArr[u * 2 + 1];
      const dist = Math.sqrt(dx * dx + dz * dz + EPSILON);
      
      // Hooke: F = C_att * (dist - restLength)  ·  direction
      const displacement = dist - REST_LENGTH;
      const force = ATTRACTION_STRENGTH * displacement;
      const forceX = (dx / dist) * force;
      const forceZ = (dz / dist) * force;
      
      fx[u] += forceX;
      fz[u] += forceZ;
      fx[v] -= forceX;
      fz[v] -= forceZ;
    }

    // ────────────────────────────────────────────────────────────
    // 3. CENTRAL GRAVITY (prevent drift off-screen)
    // ────────────────────────────────────────────────────────────
    for (let i = 0; i < n; i++) {
      fx[i] -= GRAVITY_STRENGTH * posArr[i * 2];
      fz[i] -= GRAVITY_STRENGTH * posArr[i * 2 + 1];
    }

    // ────────────────────────────────────────────────────────────
    // 4. INTEGRATION: forces → velocity → position
    // ────────────────────────────────────────────────────────────
    for (let i = 0; i < n; i++) {
      // Add force to velocity
      let vx = (velArr[i * 2] + fx[i]) * DAMPING;
      let vz = (velArr[i * 2 + 1] + fz[i]) * DAMPING;

      // Clamp velocity to prevent explosion
      const speed = Math.sqrt(vx * vx + vz * vz);
      if (speed > MAX_VELOCITY) {
        const scale = MAX_VELOCITY / speed;
        vx *= scale;
        vz *= scale;
      }

      // Store velocity
      velArr[i * 2] = vx;
      velArr[i * 2 + 1] = vz;

      // Update position
      posArr[i * 2] += vx;
      posArr[i * 2 + 1] += vz;
    }
  });

  return null; // This component has no visual output
}


// ============================================================================
// Agent Nodes InstancedMesh Component (reads from livePositionsRef)
// ============================================================================
function AgentNodes({ livePositionsRef }) {
  const meshRef = useRef();
  const { agents, activeInfluencers, selectAgent, selectedAgentId } = useSimulationStore();
  const [hoveredId, setHoveredId] = useState(null);

  // Reusable Math objects to avoid garbage collection overhead in useFrame
  const tempObject = useMemo(() => new THREE.Object3D(), []);
  const tempColor = useMemo(() => new THREE.Color(), []);

  // Fix raycasting: disable frustum culling and set a large bounding sphere
  // so that clicks are never silently rejected when force-sim moves nodes
  useEffect(() => {
    if (meshRef.current) {
      meshRef.current.frustumCulled = false;
    }
  }, []);

  // Frame animation loop for dynamic pulsing, vibration, and position updates
  useFrame((state) => {
    if (!meshRef.current || agents.length === 0) return;
    const posArr = livePositionsRef.current;
    if (!posArr) return;

    const time = state.clock.getElapsedTime();
    const n = Math.min(agents.length, posArr.length / 2);

    // Clamp instance count so only valid agents are raycast-tested
    // (prevents invisible leftover instances at origin from stealing clicks)
    meshRef.current.count = n;

    for (let i = 0; i < n; i++) {
      const agent = agents[i];
      const arousal = agent.arousal || 0.0;
      const height = 1.0 + agent.economic * 6.0;

      // Read live force-directed position
      let posX = posArr[i * 2];
      let posZ = posArr[i * 2 + 1];

      // Vibrations / Throbs for high arousal (angry) nodes using sine wave
      let scaleX = 0.95;
      let scaleZ = 0.95;

      if (arousal > 0.1) {
        // High frequency vibration
        const vibe = Math.sin(time * 60.0) * 0.05 * arousal;
        posX += vibe;
        posZ += vibe;

        // Throb width
        const throb = 1.0 + Math.sin(time * 12.0) * 0.12 * arousal;
        scaleX *= throb;
        scaleZ *= throb;
      }

      tempObject.position.set(posX, height / 2, posZ);
      tempObject.scale.set(scaleX, height, scaleZ);
      tempObject.updateMatrix();
      meshRef.current.setMatrixAt(i, tempObject.matrix);

      // Dynamic Color calculation (Pulsing angry nodes brick red)
      let beliefColor = tempColor;
      const belief = agent.belief;
      const isFactChecker = agent.literacy === 1.0 && agent.gullibility <= 0.02;

      if (isFactChecker) {
        beliefColor.copy(COLOR_FACT_CHECKER);
      } else if (belief < 0) {
        beliefColor.lerpColors(COLOR_LEFT, COLOR_NEUTRAL, belief + 1.0);
      } else {
        beliefColor.lerpColors(COLOR_NEUTRAL, COLOR_RIGHT, belief);
      }

      // If selected or hovered, highlight
      if (selectedAgentId === i) {
        beliefColor = COLOR_HOVER;
      } else if (hoveredId === i) {
        beliefColor.lerp(COLOR_HOVER, 0.5);
      } else if (arousal > 0.7) {
        // Pulse angry nodes brick red
        const pulse = (Math.sin(time * 15.0) * 0.5 + 0.5) * arousal;
        beliefColor.lerp(COLOR_PULSE, pulse);
      }

      meshRef.current.setColorAt(i, beliefColor);
    }

    meshRef.current.instanceMatrix.needsUpdate = true;
    if (meshRef.current.instanceColor) {
      meshRef.current.instanceColor.needsUpdate = true;
    }

    // Recompute bounding sphere so raycasting tracks moving nodes
    meshRef.current.computeBoundingSphere();
  });

  return (
    <instancedMesh
      ref={meshRef}
      args={[null, null, 500]}
      castShadow
      receiveShadow
      onClick={(e) => {
        e.stopPropagation();
        if (e.instanceId !== undefined) {
          selectAgent(e.instanceId);
        }
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        if (e.instanceId !== undefined) {
          setHoveredId(e.instanceId);
          document.body.style.cursor = 'pointer';
        }
      }}
      onPointerOut={() => {
        setHoveredId(null);
        document.body.style.cursor = 'default';
      }}
    >
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial roughness={0.7} metalness={0.1} />
    </instancedMesh>
  );
}

// ============================================================================
// Network Connections (Edges) Component — reads from livePositionsRef
// ============================================================================
function NetworkEdges({ livePositionsRef }) {
  const { edges, agents } = useSimulationStore();
  const lineRef = useRef();
  const prevEdgeLenRef = useRef(0);

  // Rebuild edge geometry every frame to follow moving nodes
  useFrame(() => {
    if (!lineRef.current) return;
    const posArr = livePositionsRef.current;
    if (!posArr) return;

    const n = posArr.length / 2;
    const pts = [];
    const cls = [];

    const colorU = new THREE.Color();
    const colorV = new THREE.Color();

    for (let i = 0; i < edges.length; i++) {
      const [u, v] = edges[i];
      if (u >= n || v >= n) continue;

      const ux = posArr[u * 2];
      const uz = posArr[u * 2 + 1];
      const vx = posArr[v * 2];
      const vz = posArr[v * 2 + 1];

      // Draw slightly above grid plane to prevent z-fighting
      pts.push(ux, 0.05, uz);
      pts.push(vx, 0.05, vz);

      const agentU = agents[u];
      const agentV = agents[v];

      if (agentU && agentV) {
        const uBelief = agentU.belief;
        const vBelief = agentV.belief;

        // Check if there is extreme polarized conflict (opposite signs, high difference)
        if (Math.sign(uBelief) !== Math.sign(vBelief) && Math.abs(uBelief - vBelief) > 0.8) {
          // Hot orange/red for polarized conflict edges
          colorU.set('#ff4500');
          colorV.set('#ff4500');
        } else {
          // Soft gradient between the two node colors
          if (uBelief < 0) {
            colorU.lerpColors(COLOR_LEFT, COLOR_NEUTRAL, uBelief + 1.0);
          } else {
            colorU.lerpColors(COLOR_NEUTRAL, COLOR_RIGHT, uBelief);
          }

          if (vBelief < 0) {
            colorV.lerpColors(COLOR_LEFT, COLOR_NEUTRAL, vBelief + 1.0);
          } else {
            colorV.lerpColors(COLOR_NEUTRAL, COLOR_RIGHT, vBelief);
          }

          // Dim the connection lines slightly so the nodes remain primary
          colorU.multiplyScalar(0.7);
          colorV.multiplyScalar(0.7);
        }
      } else {
        colorU.set('#CDC0B0');
        colorV.set('#CDC0B0');
      }

      cls.push(colorU.r, colorU.g, colorU.b);
      cls.push(colorV.r, colorV.g, colorV.b);
    }

    const positionArray = new Float32Array(pts);
    const colorArray = new Float32Array(cls);

    lineRef.current.geometry.setAttribute(
      'position',
      new THREE.BufferAttribute(positionArray, 3)
    );
    lineRef.current.geometry.setAttribute(
      'color',
      new THREE.BufferAttribute(colorArray, 3)
    );
    lineRef.current.geometry.computeBoundingSphere();
  });

  return (
    <lineSegments ref={lineRef}>
      <bufferGeometry />
      <lineBasicMaterial vertexColors linewidth={1} opacity={0.35} transparent />
    </lineSegments>
  );
}

// ============================================================================
// Provenance Streams (Causal Narrative Pulses) Component
// ============================================================================
function ProvenanceStreams({ livePositionsRef }) {
  const { mutatedNarratives } = useSimulationStore();
  const particlesRef = useRef();

  useFrame((state) => {
    if (!particlesRef.current || !mutatedNarratives || mutatedNarratives.length === 0) return;
    const posArr = livePositionsRef.current;
    if (!posArr) return;

    const time = state.clock.getElapsedTime();
    const pts = [];
    const cls = [];

    // Only visualize recent pulses (last 5 ticks)
    const currentTick = mutatedNarratives[mutatedNarratives.length - 1].tick;
    const recentLogs = mutatedNarratives.filter(log => currentTick - log.tick < 5);

    recentLogs.forEach(log => {
      const targetId = log.agent_id;
      const sourceIds = log.source_agent_ids || [];
      
      sourceIds.forEach(sourceId => {
        if (sourceId * 2 + 1 >= posArr.length || targetId * 2 + 1 >= posArr.length) return;

        const sx = posArr[sourceId * 2];
        const sz = posArr[sourceId * 2 + 1];
        const tx = posArr[targetId * 2];
        const tz = posArr[targetId * 2 + 1];

        // Particle moves from source to target, looping
        // The speed is slightly offset by sourceId to desync them
        const progress = (time * 1.5 + sourceId * 0.1) % 1.0;
        
        // Easing function to make it jump nicely
        const easeProgress = Math.pow(progress, 1.5);
        
        const px = sx + (tx - sx) * easeProgress;
        const pz = sz + (tz - sz) * easeProgress;
        
        // Arc up
        const py = 0.5 + Math.sin(easeProgress * Math.PI) * 2.0;

        pts.push(px, py, pz);

        // Color based on provider or default
        let color = new THREE.Color('#FFD700'); // Default gold
        if (log.provider === 'groq') color = new THREE.Color('#00FF00');
        else if (log.provider === 'gemini') color = new THREE.Color('#00FFFF');
        else if (log.provider === 'manual') color = new THREE.Color('#FF0000');

        cls.push(color.r, color.g, color.b);
      });
    });

    const positionArray = new Float32Array(pts);
    const colorArray = new Float32Array(cls);

    particlesRef.current.geometry.setAttribute(
      'position',
      new THREE.BufferAttribute(positionArray, 3)
    );
    particlesRef.current.geometry.setAttribute(
      'color',
      new THREE.BufferAttribute(colorArray, 3)
    );
    particlesRef.current.geometry.computeBoundingSphere();
  });

  return (
    <points ref={particlesRef}>
      <bufferGeometry />
      <pointsMaterial 
        size={0.6} 
        vertexColors 
        transparent 
        opacity={0.8} 
        sizeAttenuation={true} 
      />
    </points>
  );
}

// ============================================================================
// Floating Indicator Markers for selection and active influencers
// ============================================================================
function AgentMarkers({ livePositionsRef }) {
  const { agents, activeInfluencers, selectedAgentId } = useSimulationStore();
  const markerRef = useRef();

  useFrame((state) => {
    if (markerRef.current) {
      const time = state.clock.getElapsedTime();
      const posArr = livePositionsRef.current;
      if (!posArr) return;
      
      // Spin and bob the markers, and update positions from live coords
      markerRef.current.children.forEach((child) => {
        child.rotation.y = time * 2.0;
        const agentId = child.userData.agentId;
        const baseHeightFactor = child.userData.baseHeightFactor || 0;
        
        if (agentId !== undefined && posArr && agentId * 2 + 1 < posArr.length) {
          const liveX = posArr[agentId * 2];
          const liveZ = posArr[agentId * 2 + 1];
          child.position.x = liveX;
          child.position.z = liveZ;
          child.position.y = baseHeightFactor + Math.sin(time * 5.0) * 0.15;
        }
      });
    }
  });

  if (agents.length === 0) return null;

  const markers = [];

  // 0. Fact-Checker Markers: Floating white cubes
  agents.forEach((agent, i) => {
    if (agent.literacy === 1.0 && agent.gullibility <= 0.02 && i !== selectedAgentId) {
      const height = 1.0 + agent.economic * 6.0;
      const baseHeight = height + 0.5;
      markers.push(
        <mesh 
          key={`fc-${i}`} 
          position={[0, baseHeight, 0]}
          userData={{ agentId: i, baseHeightFactor: baseHeight }}
        >
          <boxGeometry args={[0.2, 0.2, 0.2]} />
          <meshStandardMaterial 
            color="#FFFFFF" 
            emissive="#FFFFFF" 
            emissiveIntensity={0.8}
          />
        </mesh>
      );
    }
  });

  // 0.5 Bot Markers: Floating red/black spikes
  agents.forEach((agent, i) => {
    if (agent.is_bot && i !== selectedAgentId) {
      const height = 1.0 + agent.economic * 6.0;
      const baseHeight = height + 0.6;
      markers.push(
        <mesh 
          key={`bot-${i}`} 
          position={[0, baseHeight, 0]}
          userData={{ agentId: i, baseHeightFactor: baseHeight }}
        >
          <cylinderGeometry args={[0, 0.15, 0.6, 4]} />
          <meshStandardMaterial 
            color="#8B0000" 
            emissive="#4B0082" 
            emissiveIntensity={0.8}
            roughness={0.2}
            metalness={0.8}
          />
        </mesh>
      );
    }
  });

  // 1. Selection Marker: Spinning Diamond (Octahedron)
  if (selectedAgentId !== null && selectedAgentId !== undefined) {
    const agent = agents[selectedAgentId];
    if (agent) {
      const height = 1.0 + agent.economic * 6.0;
      const baseHeight = height + 0.8;
      markers.push(
        <mesh 
          key={`select-${selectedAgentId}`} 
          position={[0, baseHeight, 0]}
          userData={{ agentId: selectedAgentId, baseHeightFactor: baseHeight }}
        >
          <octahedronGeometry args={[0.4, 0]} />
          <meshStandardMaterial 
            color="#FFE4B5" 
            emissive="#FFB90F" 
            emissiveIntensity={0.6}
            roughness={0.2}
            metalness={0.8}
          />
        </mesh>
      );
    }
  }

  // 2. Influencer Markers: Small Golden Cones (pointing down)
  activeInfluencers.forEach((infId) => {
    // Don't duplicate if it's already selected
    if (infId === selectedAgentId) return;

    const agent = agents[infId];
    if (agent) {
      const height = 1.0 + agent.economic * 6.0;
      const baseHeight = height + 0.7;
      markers.push(
        <mesh 
          key={`inf-${infId}`} 
          position={[0, baseHeight, 0]}
          rotation={[Math.PI, 0, 0]} // Invert cone to point down
          userData={{ agentId: infId, baseHeightFactor: baseHeight }}
        >
          <coneGeometry args={[0.22, 0.45, 4]} />
          <meshStandardMaterial 
            color="#FFD700" 
            emissive="#FF8C00" 
            emissiveIntensity={0.5}
            roughness={0.3}
            metalness={0.7}
          />
        </mesh>
      );
    }
  });

  return <group ref={markerRef}>{markers}</group>;
}

// Checkered Terrain Floor Plane
function TerrainFloor() {
  const texture = useMemo(() => createCheckerboardTexture(), []);

  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow position={[0, -0.01, 0]}>
      <planeGeometry args={[120, 120]} />
      <meshStandardMaterial map={texture} roughness={0.9} metalness={0.05} />
    </mesh>
  );
}

export default function VoxelCanvas() {
  const { isInitialized } = useSimulationStore();
  
  // Shared mutable ref for live force-directed positions
  // This is a Float32Array: [x0, z0, x1, z1, ...]
  // All child components read from this ref every frame.
  const livePositionsRef = useRef(null);

  return (
    <div className="canvas-container rct-inset">
      <Canvas shadows gl={{ antialias: true }}>
        <color attach="background" args={['#688e2e']} />
        
        <OrthographicCamera
          makeDefault
          position={[35, 35, 35]}
          zoom={12}
          near={0.1}
          far={1000}
        />

        <OrbitControls
          enableDamping
          dampingFactor={0.05}
          maxPolarAngle={Math.PI / 2 - 0.05}
          minZoom={4}
          maxZoom={30}
        />

        {/* RollerCoaster Tycoon soft volumetric top lighting */}
        <ambientLight intensity={1.2} color="#FFF8F0" />
        <directionalLight
          castShadow
          position={[30, 45, 15]}
          intensity={1.8}
          color="#FFEAA7"
          shadow-mapSize-width={2048}
          shadow-mapSize-height={2048}
          shadow-camera-left={-60}
          shadow-camera-right={60}
          shadow-camera-top={60}
          shadow-camera-bottom={-60}
          shadow-camera-near={0.1}
          shadow-camera-far={200}
        />

        {isInitialized && (
          <>
            {/* Force-directed physics engine (invisible, runs every frame) */}
            <ForceDirectedSimulation livePositionsRef={livePositionsRef} />
            
            <TerrainFloor />
            <AgentNodes livePositionsRef={livePositionsRef} />
            <NetworkEdges livePositionsRef={livePositionsRef} />
            <ProvenanceStreams livePositionsRef={livePositionsRef} />
            <AgentMarkers livePositionsRef={livePositionsRef} />
          </>
        )}

        <EffectComposer>
          <Pixelation granularity={2.0} />
          <Noise opacity={0.04} premultiply />
        </EffectComposer>
      </Canvas>
      
      {!isInitialized && (
        <div className="canvas-placeholder">
          <div className="rct-window" style={{ width: '320px' }}>
            <div className="rct-titlebar">
              <span>SYSTEM READY</span>
            </div>
            <div className="rct-panel" style={{ padding: '16px', textAlign: 'center' }}>
              <p>Simulation Sandbox Offline</p>
              <p style={{ fontSize: '11px', color: '#555', marginTop: '6px' }}>
                Use the control panel on the left to initialize the 500-node network.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
