import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import networkx as nx
import numpy as np

from opinion_engine.opinion_engine import OpinionEngine, Topology, TopologyParams
from opinion_engine.llm_client import EchoLLMClient, DEFAULT_REACTION_TEMPLATE, DEFAULT_INJECTION_TEMPLATE

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

# Initialize LLM client
llm_client = EchoLLMClient()

class TopologyParamsModel(BaseModel):
    m: int = 3
    k: int = 6
    p: float = 0.3

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
    custom_edges: Optional[List[List[int]]] = None
    p_fact_checkers: float = 0.05

class InjectRequest(BaseModel):
    agent_id: int
    belief_score: float
    message: Optional[str] = None

def get_active_edges(opinion_graph: nx.Graph) -> List[List[int]]:
    """Convert NetworkX graph edges to a simple list of lists."""
    return [[int(u), int(v)] for u, v in opinion_graph.edges()]

@app.post("/api/initialize")
def initialize_simulation(req: InitializeRequest):
    global engine, static_positions, narrative_logs
    try:
        topo = Topology.SCALE_FREE if req.topology == "scale_free" else Topology.SMALL_WORLD
        
        t_params = TopologyParams()
        if req.topology_params:
            t_params.m = req.topology_params.m
            t_params.k = req.topology_params.k
            t_params.p = req.topology_params.p

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
            custom_edges=req.custom_edges,
        )

        # Clear narrative logs
        narrative_logs = []
        
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
                    "provider": injection.provider.value
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
            "success": True,
            "agents": agents_data,
            "edges": get_active_edges(engine.get_graph()),
            "positions": static_positions,
            "telemetry": engine.get_telemetry(),
            "narrative_logs": narrative_logs
        }
    except Exception as e:
        logger.exception("Failed to initialize simulation")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/step")
def step_simulation():
    global engine, narrative_logs
    if not engine:
        raise HTTPException(status_code=400, detail="Simulation not initialized. Call /api/initialize first.")
    
    try:
        # 1. Run physical dynamics tick
        result = engine.step()
        
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
                
                try:
                    response = llm_client.evaluate_message(
                        baseline_belief=baseline_belief,
                        current_belief=current_belief,
                        stubbornness=stubbornness,
                        incoming_message_text=incoming["message"],
                        incoming_message_bias=incoming["bias"]
                    )
                    
                    if response.will_engage:
                        # Update belief in engine
                        engine.inject_narrative(influencer_id, response.new_belief_score)
                        
                        # Log the mutated message
                        narrative_logs.append({
                            "tick": result["tick"],
                            "agent_id": int(influencer_id),
                            "message": response.mutated_message,
                            "bias": response.new_belief_score,
                            "provider": response.provider.value
                        })
                except Exception as ex:
                    logger.warning(f"Failed to run LLM evaluation for agent {influencer_id}: {ex}")

        states = engine.get_agent_states()
        
        # Extract dynamic beliefs and arousals
        beliefs = states[:, 3].tolist() # COL_BELIEF
        arousals = states[:, 5].tolist() # COL_AROUSAL
        
        return {
            "tick": result["tick"],
            "polarization": result["polarization"],
            "avg_belief": result["avg_belief"],
            "edges_severed": result["edges_severed"],
            "edges_formed": result["edges_formed"],
            "active_influencers": result["active_influencers"],
            "beliefs": beliefs,
            "arousals": arousals,
            "edges": get_active_edges(engine.get_graph()),
            "narrative_logs": narrative_logs
        }
    except Exception as e:
        logger.exception("Failed to advance simulation step")
        raise HTTPException(status_code=500, detail=str(e))

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
    return {
        "success": True,
        "n_agents": engine.n_agents,
        "total_ticks": engine.tick,
        "history": telemetry.get("history", []),
        "narrative_logs": narrative_logs,
        "final_polarization": telemetry.get("polarization", 0),
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
