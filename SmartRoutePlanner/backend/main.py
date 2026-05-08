from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict
import os

app = FastAPI(title="Smart Route Planner API")


# --- Pydantic Models ---
class Node(BaseModel):
    id: int
    x: float
    y: float


class Edge(BaseModel):
    id: str
    from_node: int = Field(alias="from")
    to_node: int = Field(alias="to")
    weight: float


class PathRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    nodes: List[Node]
    edges: List[Edge]
    algorithm: str
    preference: str
    start_node: Optional[int] = None
    end_node: Optional[int] = None
    waypoints: Optional[List[int]] = None            # AO* mandatory stops
    traffic_multipliers: Optional[Dict[str, float]] = None  # edge_id -> multiplier


from algorithms import PathfindingAlgorithms


# --- AI Decision Engine ---
def ai_select_algorithm(nodes, edges, preference: str, waypoints) -> tuple:
    num_nodes = len(nodes)
    num_edges = len(edges)
    max_possible = num_nodes * (num_nodes - 1) / 2 if num_nodes > 1 else 1
    density = num_edges / max_possible if max_possible > 0 else 0

    weights = [e.weight for e in edges]
    avg_w = sum(weights) / len(weights) if weights else 1
    variance = sum((w - avg_w) ** 2 for w in weights) / len(weights) if weights else 0

    # AO*: waypoints present → must visit all AND nodes
    if waypoints:
        return "ao_star", (
            f"Mandatory waypoints detected — AO* (AND-OR search) ensures all "
            f"{len(waypoints)} waypoint(s) are visited in optimal order."
        )

    # Dijkstra: small dense graph, guaranteed optimal
    if num_nodes <= 8 and density > 0.5:
        return "dijkstra", (
            f"Small dense graph ({num_nodes} cities, {density:.0%} density) — "
            f"Dijkstra guarantees optimal cost with full exploration."
        )

    # Binary Search: traffic mode with varied weights → minimise bottleneck
    if preference == "traffic" and variance > (avg_w ** 2):
        return "binary_search", (
            f"Traffic mode + high weight variance (σ²={variance:.1f}) — "
            f"Binary Search finds the path with the smallest traffic bottleneck."
        )

    # Greedy: very large graph, speed matters
    if num_nodes > 20:
        return "greedy", (
            f"Large graph ({num_nodes} cities) — Greedy Best-First finds a fast "
            f"solution; may not be globally optimal."
        )

    # A*: default balanced
    return "astar", (
        f"Balanced graph — A* provides the best trade-off between "
        f"speed and optimality using geometric heuristic."
    )


# --- API Endpoints ---
@app.get("/api/status")
def status():
    return {"status": "Backend is running smoothly!"}


@app.post("/api/find-path")
def find_path(request: PathRequest):
    if len(request.nodes) < 2:
        raise HTTPException(status_code=400, detail="Graph must have at least 2 cities.")

    start_id = request.start_node if request.start_node is not None else request.nodes[0].id
    end_id   = request.end_node   if request.end_node   is not None else request.nodes[-1].id

    node_ids = {n.id for n in request.nodes}
    if start_id not in node_ids:
        raise HTTPException(status_code=400, detail=f"Start node {start_id} not found.")
    if end_id not in node_ids:
        raise HTTPException(status_code=400, detail=f"End node {end_id} not found.")
    if start_id == end_id:
        raise HTTPException(status_code=400, detail="Start and end cities must be different.")

    # Apply traffic multipliers when preference is "traffic"
    if request.preference == "traffic" and request.traffic_multipliers:
        for edge in request.edges:
            mult = request.traffic_multipliers.get(edge.id, 1.0)
            edge.weight = round(edge.weight * mult, 1)

    # AI Auto-Select
    ai_reason = None
    algo_to_run = request.algorithm
    if algo_to_run == "auto":
        algo_to_run, ai_reason = ai_select_algorithm(
            request.nodes, request.edges, request.preference, request.waypoints or []
        )

    # Validate waypoints
    waypoints = request.waypoints or []
    if algo_to_run == "ao_star":
        invalid_wps = [w for w in waypoints if w not in node_ids]
        if invalid_wps:
            raise HTTPException(status_code=400, detail=f"Invalid waypoints: {invalid_wps}")
        # Remove start/end from waypoints if accidentally included
        waypoints = [w for w in waypoints if w not in (start_id, end_id)]

    # Run algorithm
    runner = PathfindingAlgorithms(request.nodes, request.edges)
    result = runner.run(algo_to_run, start_id, end_id, waypoints=waypoints)

    algo_labels = {
        "dijkstra":     "Dijkstra's Algorithm",
        "astar":        "A* (A-Star)",
        "greedy":       "Greedy",
        "binary_search":"Binary Search (Bottleneck)",
        "ao_star":      "AO* (AND-OR Search)",
        "dfs":          "Depth-First Search",
        "bfs":          "Breadth-First Search",
        "topo_sort":    "Topological Sort (DAG)",
    }

    return {
        "message": "Path found successfully!",
        "nodes_count":        len(request.nodes),
        "edges_count":        len(request.edges),
        "algorithm_requested": request.algorithm,
        "algorithm_used":     algo_to_run,
        "algorithm_label":    algo_labels.get(algo_to_run, algo_to_run),
        "ai_reason":          ai_reason,
        "preference":         request.preference,
        "start_node":         start_id,
        "end_node":           end_id,
        "path_data":          result,
    }


# --- Serve Frontend (must be last) ---
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
else:
    @app.get("/")
    def read_root():
        return {"message": "Frontend directory not found."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8002, reload=True)
