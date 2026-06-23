import logging
import csv
import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import tempfile
import os
from pydantic import BaseModel
import networkx as nx
import numpy as np
from RestrictedPython import compile_restricted, safe_builtins

from opinion_engine.opinion_engine import OpinionEngine, Topology, TopologyParams
from opinion_engine.llm_client import EchoLLMClient, DEFAULT_REACTION_TEMPLATE, DEFAULT_INJECTION_TEMPLATE
from opinion_engine.data_pipeline import OSINTDataPipeline
from opinion_engine.religion_registry import ReligionRegistry
from opinion_engine.narrative_classifier import classify_narrative, NarrativeProfile
from opinion_engine.contagion_manager import ContagionManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("echo.server")

app = FastAPI(title="ECHO Simulation API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global simulation state
engine: Optional[OpinionEngine] = None
static_positions: Dict[int, Dict[str, float]] = {}
narrative_logs: List[Dict[str, Any]] = []
influencer_memory: Dict[int, List[str]] = {}
influencer_strategy: Dict[int, str] = {}
active_narrative_profile: Optional[NarrativeProfile] = None
contagion_manager: Optional[ContagionManager] = None

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.is_playing = False

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# Initialize LLM client
llm_client = EchoLLMClient()

class TopologyParamsModel(BaseModel):
    m: int = 3
    k: int = 6
    p: float = 0.3
    sbm_blocks: int = 3
    sbm_p_in: float = 0.3
    sbm_p_out: float = 0.01

class InitializeRequest(BaseModel):
    n_agents: int = 500
    topology: str = "small_world"
    w_pol: float = 0.4
    w_econ: float = 0.3
    w_rel: float = 0.3
    d_tolerance: float = 0.5
    gamma: float = 0.1
    n_religious_groups: int = 3
    seed: Optional[int] = 42
    topology_params: Optional[TopologyParamsModel] = None
    fatigue_limit: int = 5
    topic: Optional[str] = None
    secondary_topic: Optional[str] = None
    custom_edges: Optional[List[List[int]]] = None
    p_fact_checkers: float = 0.05
    p_bots: float = 0.0
    belief_dist: str = "uniform"

class InjectRequest(BaseModel):
    agent_id: int
    belief_score: float
    message: Optional[str] = None

class BroadcastRequest(BaseModel):
    belief_shift: float
    arousal_shift: float
    message: str

class AlgorithmRequest(BaseModel):
    code_string: str

class WireRequest(BaseModel):
    source_id: int
    target_id: int

def get_active_edges(opinion_graph: nx.Graph) -> List[List[int]]:
    """Convert NetworkX graph edges to a simple list of lists."""
    return [[int(u), int(v)] for u, v in opinion_graph.edges()]

@app.post("/api/initialize")
async def initialize_simulation(req: InitializeRequest):
    global engine, static_positions, narrative_logs, influencer_memory, influencer_strategy, active_narrative_profile, contagion_manager
    try:
        if req.topology == "scale_free":
            topo = Topology.SCALE_FREE
        elif req.topology == "stochastic_block":
            topo = Topology.STOCHASTIC_BLOCK
        else:
            topo = Topology.SMALL_WORLD
        
        t_params = TopologyParams()
        if req.topology_params:
            t_params.m = req.topology_params.m
            t_params.k = req.topology_params.k
            t_params.p = req.topology_params.p
            t_params.sbm_blocks = req.topology_params.sbm_blocks
            t_params.sbm_p_in = req.topology_params.sbm_p_in
            t_params.sbm_p_out = req.topology_params.sbm_p_out

        try:
            registry = ReligionRegistry.load(os.path.join(os.path.dirname(__file__), "opinion_engine/religions.json"))
            profile = await classify_narrative(req.topic, registry) if req.topic else None
            active_narrative_profile = profile
            
            engine = OpinionEngine(
                n_agents=req.n_agents,
                topology=topo,
                w_pol=req.w_pol,
                w_econ=req.w_econ,
                w_rel=req.w_rel,
                d_tolerance=req.d_tolerance,
                gamma=req.gamma,
                topology_params=t_params,
                n_religious_groups=req.n_religious_groups,
                seed=req.seed,
                fatigue_limit=req.fatigue_limit,
                p_fact_checkers=req.p_fact_checkers,
                p_bots=req.p_bots,
                belief_dist=req.belief_dist,
                religion_registry=registry,
                narrative_profile=profile
            )
            
            contagion_manager = None
            if req.secondary_topic:
                secondary_profile = await classify_narrative(req.secondary_topic, registry)
                contagion_manager = ContagionManager()
                contagion_manager.add_topic(
                    topic_id=1,
                    topic_name=req.secondary_topic,
                    narrative_profile=secondary_profile,
                    num_agents=req.n_agents,
                    belief_dist=req.belief_dist,
                    engine=engine,          # enables religion-aware belief seeding
                )
        except Exception as e:
            logger.error(f"Failed to load religion registry or classifier: {e}. Falling back.")
            engine = OpinionEngine(
                n_agents=req.n_agents,
                topology=topo,
                w_pol=req.w_pol,
                w_econ=req.w_econ,
                w_rel=req.w_rel,
                d_tolerance=req.d_tolerance,
                gamma=req.gamma,
                topology_params=t_params,
                n_religious_groups=req.n_religious_groups,
                seed=req.seed,
                fatigue_limit=req.fatigue_limit,
                p_fact_checkers=req.p_fact_checkers,
                p_bots=req.p_bots,
                belief_dist=req.belief_dist,
            )

        # Clear logs and memory
        narrative_logs = []
        influencer_memory.clear()
        influencer_strategy.clear()
        
        # If starting topic is provided, generate Patient Zero post via LLM
        if req.topic:
            try:
                injection = llm_client.generate_injection(req.topic)
                engine.inject_narrative(0, injection.encoded_bias)
                narrative_logs.append({
                    "tick": 0,
                    "agent_id": 0,
                    "message": injection.post_text,
                    "bias": injection.encoded_bias,
                    "provider": injection.provider.value,
                    "topic_id": 0
                })
            except Exception as ex:
                logger.warning(f"Failed to generate Patient Zero injection: {ex}")

        # Generate static spring layout coordinates for 3D visual canvas (X, Z plane)
        # Scale by 35 to give a nice spread centered at 0
        graph = engine.get_graph()
        pos = nx.spring_layout(graph, seed=req.seed)
        static_positions = {
            int(node_id): {
                "x": float(coord[0] * 35.0),
                "z": float(coord[1] * 35.0)
            }
            for node_id, coord in pos.items()
        }

        # Collect current agent states
        agents_data = []
        for i in range(req.n_agents):
            agents_data.append(engine.get_agent_detail(i))

        logger.info(f"Simulation initialized with {req.n_agents} agents and {req.topology} topology.")
        
        return {
            "message": "Simulation initialized successfully",
            "agents": agents_data,
            "edges": get_active_edges(graph),
            "positions": static_positions,
            "telemetry": engine.get_telemetry(),
            "narrative_logs": narrative_logs,
            "narrative_profile": get_narrative_profile().get("profile")
        }
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/narrative_profile")
def get_narrative_profile():
    if not active_narrative_profile:
        return {"profile": None}
    import dataclasses
    return {"profile": dataclasses.asdict(active_narrative_profile)}

from fastapi import Body

@app.get("/api/topics")
def get_topics():
    topics = []
    if active_narrative_profile:
        topics.append({
            "topic_id": 0,
            "name": active_narrative_profile.topic_name,
            "avg_belief": float(np.mean(engine._agents[:, 3])) if engine else 0.0
        })
    if contagion_manager:
        topic_b = contagion_manager.get_topic(1)
        if topic_b:
            topics.append({
                "topic_id": 1,
                "name": topic_b.topic_name,
                "avg_belief": float(np.mean(topic_b.beliefs))
            })
    return {"topics": topics}

@app.post("/api/inject_topic")
def inject_topic(agent_id: int = Body(...), topic_id: int = Body(...), belief_score: float = Body(...)):
    if topic_id == 0:
        if engine:
            engine.inject_narrative(agent_id, belief_score)
    elif topic_id == 1:
        if contagion_manager:
            contagion_manager.inject_topic(agent_id, topic_id, belief_score)
    return {"message": "Success"}

@app.post("/api/upload_topology")
async def upload_topology(
    file: UploadFile = File(...),
    w_pol: float = 0.4,
    w_econ: float = 0.3,
    w_rel: float = 0.3,
    d_tolerance: float = 0.5,
    gamma: float = 0.1,
    fatigue_limit: int = 5,
    arousal_decay: float = 0.8,
    extremism_threshold: float = 0.8,
    skepticism_threshold: float = 0.6,
    fatigue_cooldown: float = 0.2
):
    global engine, static_positions, narrative_logs, influencer_memory, influencer_strategy
    try:
        # Save uploaded file to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        pipeline = OSINTDataPipeline(llm_client=llm_client)
        agents_matrix, adj_matrix, edges_list, anchors = pipeline.load_topology(tmp_path)
        os.remove(tmp_path)

        engine = OpinionEngine(
            n_agents=len(agents_matrix),
            topology=Topology.CUSTOM,
            w_pol=w_pol,
            w_econ=w_econ,
            w_rel=w_rel,
            d_tolerance=d_tolerance,
            gamma=gamma,
            fatigue_limit=fatigue_limit,
            arousal_decay=arousal_decay,
            extremism_threshold=extremism_threshold,
            skepticism_threshold=skepticism_threshold,
            fatigue_cooldown=fatigue_cooldown,
            custom_agents_matrix=agents_matrix,
            custom_adjacency=adj_matrix,
            custom_anchors=anchors
        )

        narrative_logs = []
        influencer_memory.clear()
        influencer_strategy.clear()

        graph = engine.get_graph()
        pos = nx.spring_layout(graph, seed=42)
        static_positions = {
            int(node_id): {
                "x": float(coord[0] * 35.0),
                "z": float(coord[1] * 35.0)
            }
            for node_id, coord in pos.items()
        }

        agents_data = [engine.get_agent_detail(i) for i in range(engine.n_agents)]

        return {
            "message": "OSINT topology loaded successfully",
            "agents": agents_data,
            "edges": get_active_edges(graph),
            "positions": static_positions,
            "telemetry": engine.get_telemetry(),
            "narrative_logs": narrative_logs
        }
    except Exception as e:
        logger.error(f"OSINT upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def run_simulation_step():
    global engine, narrative_logs, influencer_memory, influencer_strategy, contagion_manager
    if not engine:
        raise ValueError("Simulation not initialized.")
    
    
    try:
        # 1. Run physical dynamics tick
        result = engine.step()
        
        # 1b. Run secondary topic dynamics if active
        if contagion_manager:
            contagion_manager.step(engine, topic_id=1)
            bridging_agents = contagion_manager.detect_bridging_agents(engine, topic_id_b=1)
        else:
            bridging_agents = []
        
        # 2. Run LLM Narrative Mutation Phase for active influencers
        active_influencers = result["active_influencers"]
        
        # Limit LLM execution to top 3 influencers of this tick to keep simulation fast/responsive
        for influencer_id in active_influencers[:3]:
            # Find an incoming message from the local neighborhood
            graph = engine.get_graph()
            try:
                neighbors = set(graph.neighbors(influencer_id))
            except nx.NetworkXError:
                neighbors = set()
                
            neighbor_msgs = [m for m in narrative_logs if m["agent_id"] in neighbors]
            
            if neighbor_msgs:
                incoming = neighbor_msgs[-1]
            elif narrative_logs:
                incoming = narrative_logs[0]
            else:
                incoming = None
                
            if incoming:
                current_belief = engine.get_agent_belief(influencer_id)
                baseline_belief = engine.get_agent_baseline_belief(influencer_id)
                stubbornness = engine.get_agent_stubbornness(influencer_id)
                
                # Arousal Entropy Shock: if stuck in loop
                memory = influencer_memory.get(influencer_id, [])
                if len(memory) > 3 and len(set(memory[-3:])) == 1:
                    engine._agents[influencer_id, 5] = 1.0 # Spike arousal (COL_AROUSAL=5)
                    
                # Format memory directly as past posts to ground the LLM
                memory_posts = ""
                if memory:
                    memory_posts = "- " + "\n- ".join(memory[-3:])
                    
                current_topic = active_narrative_profile.topic_name if active_narrative_profile else "Unknown"
                
                is_bridging = influencer_id in bridging_agents
                secondary_topic_str = None
                secondary_belief_val = None
                if is_bridging and contagion_manager and contagion_manager.get_topic(1):
                    secondary_topic_str = contagion_manager.get_topic(1).topic_name
                    secondary_belief_val = float(contagion_manager.get_topic(1).beliefs[influencer_id])
                
                try:
                    response = llm_client.evaluate_message(
                        baseline_belief=baseline_belief,
                        current_belief=current_belief,
                        stubbornness=stubbornness,
                        incoming_message_text=incoming["message"],
                        incoming_message_bias=incoming["bias"],
                        topic=current_topic,
                        secondary_topic=secondary_topic_str,
                        secondary_belief=secondary_belief_val,
                        memory_context=memory_posts
                    )
                    
                    if response.will_engage:
                        # Update belief in engine
                        engine.inject_narrative(influencer_id, response.new_belief_score)
                        
                        mutated = response.mutated_message
                        if influencer_id not in influencer_memory:
                            influencer_memory[influencer_id] = []
                        influencer_memory[influencer_id].append(mutated)
                        
                        # Compress if > 5
                        if len(influencer_memory[influencer_id]) > 5:
                            influencer_strategy[influencer_id] = llm_client.summarize_memory(influencer_memory[influencer_id])
                            influencer_memory[influencer_id] = influencer_memory[influencer_id][-2:]
                            
                        top_inf = result.get("top_influencers", [])
                        source_ids = [int(x) for x in top_inf[influencer_id]] if top_inf else []
                        
                        # Log the mutated message
                        topic_val = "bridge" if is_bridging else 0
                        narrative_logs.append({
                            "tick": result["tick"],
                            "agent_id": int(influencer_id),
                            "message": mutated,
                            "bias": response.new_belief_score,
                            "provider": response.provider.value,
                            "source_agent_ids": source_ids,
                            "topic_id": topic_val
                        })
                except Exception as ex:
                    logger.warning(f"Failed to run LLM evaluation for agent {influencer_id}: {ex}")

        states = engine.get_agent_states()
        
        # Extract dynamic beliefs and arousals
        beliefs = states[:, 3].tolist() # COL_BELIEF
        arousals = states[:, 5].tolist() # COL_AROUSAL
        
        beliefs_b = contagion_manager.get_topic(1).beliefs.tolist() if contagion_manager else []
        
        return {
            "tick": result["tick"],
            "polarization": result["polarization"],
            "avg_belief": result["avg_belief"],
            "edges_severed": result["edges_severed"],
            "edges_formed": result["edges_formed"],
            "active_influencers": result["active_influencers"],
            "beliefs": beliefs,
            "beliefs_b": beliefs_b,
            "arousals": arousals,
            "edges": get_active_edges(engine.get_graph()),
            "narrative_logs": narrative_logs
        }
    except Exception as e:
        logger.exception("Failed to advance simulation step")
        raise e

@app.post("/api/step")
def step_simulation():
    try:
        return run_simulation_step()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def simulation_loop():
    while True:
        if manager.is_playing and engine:
            try:
                res = await asyncio.to_thread(run_simulation_step)
                await manager.broadcast({"type": "step_result", "data": res})
            except Exception as e:
                logger.error(f"Simulation loop error: {e}")
                manager.is_playing = False
                await manager.broadcast({"type": "error", "message": str(e)})
        await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulation_loop())

@app.websocket("/api/ws/simulation")
async def websocket_simulation(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            if action == "play":
                manager.is_playing = True
            elif action == "pause":
                manager.is_playing = False
            elif action == "step":
                try:
                    res = await asyncio.to_thread(run_simulation_step)
                    await websocket.send_json({"type": "step_result", "data": res})
                except Exception as e:
                    await websocket.send_json({"type": "error", "message": str(e)})
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/inject")
def inject_narrative(req: InjectRequest):
    global engine, narrative_logs
    if not engine:
        raise HTTPException(status_code=400, detail="Simulation not initialized.")
    
    try:
        engine.inject_narrative(req.agent_id, req.belief_score)
        detail = engine.get_agent_detail(req.agent_id)
        
        # Also log the manual injection as a narrative event
        msg = req.message.strip() if req.message else ""
        if not msg:
            msg = f"[MANUAL INJECTION] Agent {req.agent_id} belief set to {req.belief_score:.2f}"
            
        narrative_logs.append({
            "tick": engine.tick,
            "agent_id": req.agent_id,
            "message": msg,
            "bias": req.belief_score,
            "provider": "manual"
        })
        
        return {"success": True, "agent": detail, "narrative_logs": narrative_logs}
    except IndexError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Failed to inject narrative")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/toggle_algorithm")
def toggle_algorithm():
    global engine
    if not engine:
        raise HTTPException(status_code=400, detail="Simulation not initialized.")
    
    engine.algorithm_active = not engine.algorithm_active
    return {"algorithm_active": engine.algorithm_active}

@app.post("/api/broadcast")
def global_broadcast(req: BroadcastRequest):
    global engine, narrative_logs
    if not engine:
        raise HTTPException(status_code=400, detail="Simulation not initialized.")
    
    try:
        engine.global_broadcast(req.belief_shift, req.arousal_shift)
        
        narrative_logs.append({
            "tick": engine.tick,
            "agent_id": -1,  # -1 implies global system event
            "message": f"[GLOBAL SHOCK] {req.message}",
            "bias": req.belief_shift,
            "provider": "system"
        })
        
        # Collect updated beliefs and arousals to return
        states = engine.get_agent_states()
        beliefs = states[:, 3].tolist() # COL_BELIEF
        arousals = states[:, 5].tolist() # COL_AROUSAL
        
        return {
            "success": True, 
            "beliefs": beliefs, 
            "arousals": arousals, 
            "narrative_logs": narrative_logs
        }
    except Exception as e:
        logger.exception("Failed to execute global broadcast")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/telemetry")
def get_telemetry():
    global engine
    if not engine:
        raise HTTPException(status_code=400, detail="Simulation not initialized.")
    return engine.get_telemetry()

@app.get("/api/export")
def export_session():
    global engine, narrative_logs
    if not engine:
        raise HTTPException(status_code=400, detail="Simulation not initialized.")
    
    # We reconstruct the history explicitly from get_telemetry() to get a nice dict format
    telemetry = engine.get_telemetry()
    
    # Collect current agent states
    agents_data = []
    for i in range(engine.n_agents):
        agents_data.append(engine.get_agent_detail(i))
        
    return {
        "success": True,
        "n_agents": engine.n_agents,
        "total_ticks": engine.tick,
        "history": telemetry.get("history", []),
        "narrative_logs": narrative_logs,
        "final_polarization": telemetry.get("polarization", 0),
        "agents": agents_data,
        "edges": get_active_edges(engine.get_graph())
    }


@app.get("/api/export/csv")
def export_telemetry_csv():
    """Stream per-tick aggregate metrics as a CSV file for research analysis."""
    if not engine or not engine._history:
        raise HTTPException(status_code=400, detail="No simulation data to export. Run at least one tick first.")

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "tick", "polarization", "avg_belief",
            "edges_severed", "edges_formed", "edge_count", "n_active_influencers"
        ])
        yield buf.getvalue()
        buf.truncate(0)
        buf.seek(0)

        for t in engine._history:
            writer.writerow([
                t.tick,
                round(t.polarization, 6),
                round(t.avg_belief, 6),
                t.edges_severed,
                t.edges_formed,
                t.edge_count,
                len(t.active_influencers),
            ])
            yield buf.getvalue()
            buf.truncate(0)
            buf.seek(0)

    filename = f"echo_telemetry_tick{engine._tick}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/export/beliefs_csv")
def export_beliefs_csv():
    """Stream the full N-agent belief trajectory matrix as CSV (one row per tick)."""
    if not engine or not engine._history:
        raise HTTPException(status_code=400, detail="No simulation data to export. Run at least one tick first.")

    n = engine.n_agents

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        # Header: tick, agent_0_belief, agent_1_belief, ...
        header = ["tick"] + [f"agent_{i}_belief" for i in range(n)]
        writer.writerow(header)
        yield buf.getvalue()
        buf.truncate(0)
        buf.seek(0)

        for t in engine._history:
            row = [t.tick] + [round(b, 6) for b in t.belief_snapshot]
            writer.writerow(row)
            yield buf.getvalue()
            buf.truncate(0)
            buf.seek(0)

    filename = f"echo_beliefs_tick{engine._tick}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/export/config")
def export_config():
    """Return the full reproducible experiment configuration as a JSON object."""
    if not engine:
        raise HTTPException(status_code=400, detail="Simulation not initialized.")

    tp = engine.topology_params
    return {
        "echo_version": "1.0.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "seed": engine.seed,
        "n_agents": engine.n_agents,
        "topology": engine.topology_type.value,
        "topology_params": {
            "m": tp.m,
            "k": tp.k,
            "p": tp.p,
            "sbm_blocks": tp.sbm_blocks,
            "sbm_p_in": tp.sbm_p_in,
            "sbm_p_out": tp.sbm_p_out,
        },
        "w_pol": engine.w_pol,
        "w_econ": engine.w_econ,
        "w_rel": engine.w_rel,
        "d_tolerance": engine.d_tolerance,
        "gamma": engine.gamma,
        "fatigue_limit": engine.fatigue_limit,
        "arousal_decay": engine.arousal_decay,
        "extremism_threshold": engine.extremism_threshold,
        "skepticism_threshold": engine.skepticism_threshold,
        "p_fact_checkers": engine.p_fact_checkers,
        "p_bots": engine.p_bots,
        "belief_dist": engine.belief_dist,
        "n_religious_groups": engine.n_religious_groups,
        "total_ticks_run": engine._tick,
        "final_polarization": round(engine._history[-1].polarization, 6) if engine._history else None,
        "final_avg_belief": round(engine._history[-1].avg_belief, 6) if engine._history else None,
    }

class UpdatePromptsRequest(BaseModel):
    reaction_template: str
    injection_template: str

@app.get("/api/prompts")
def get_prompts():
    return {
        "reaction_template": llm_client.reaction_system_prompt_template,
        "injection_template": llm_client.injection_system_prompt_template,
        "default_reaction_template": DEFAULT_REACTION_TEMPLATE,
        "default_injection_template": DEFAULT_INJECTION_TEMPLATE
    }

@app.post("/api/prompts")
def update_prompts(req: UpdatePromptsRequest):
    llm_client.reaction_system_prompt_template = req.reaction_template
    llm_client.injection_system_prompt_template = req.injection_template
    return {"success": True}

@app.post("/api/godmode/algorithm")
def inject_algorithm(req: AlgorithmRequest):
    global engine
    if not engine:
        raise HTTPException(status_code=400, detail="Simulation not initialized.")
    
    code = req.code_string.strip()
    if not code:
        engine.custom_update_logic = None
        return {"success": True, "message": "Custom logic cleared. Using default dynamics."}
    
    try:
        # Secure compilation
        byte_code = compile_restricted(code, '<inline>', 'exec')
        # Setup safe execution environment
        loc = {}
        safe_globals = {'__builtins__': safe_builtins, 'np': np}
        exec(byte_code, safe_globals, loc)
        
        # We expect a function named custom_update
        if "custom_update" not in loc or not callable(loc["custom_update"]):
            raise ValueError("Code must define a function named 'custom_update(opinions, adjacency)'")
            
        engine.custom_update_logic = loc["custom_update"]
        return {"success": True, "message": "Custom algorithm successfully injected and active."}
    except Exception as e:
        logger.error(f"Failed to inject custom algorithm: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/godmode/wire")
def wire_edge(req: WireRequest):
    global engine
    if not engine:
        raise HTTPException(status_code=400, detail="Simulation not initialized.")
    
    try:
        engine.force_edge(req.source_id, req.target_id)
        return {"success": True, "edges": get_active_edges(engine.get_graph())}
    except Exception as e:
        logger.error(f"Failed to force edge: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
