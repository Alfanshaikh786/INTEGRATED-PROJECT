import math
import heapq
from typing import List, Dict, Any, Optional

try:
    from c_algorithms_wrapper import CAlgorithmsWrapper
except ImportError:
    CAlgorithmsWrapper = None


class PathfindingAlgorithms:
    def __init__(self, nodes, edges):
        self.nodes = {n.id: n for n in nodes}
        self.edges = edges
        self.graph = {n.id: [] for n in nodes}
        for e in edges:
            self.graph[e.from_node].append((e.to_node, e.weight, e.id))
            self.graph[e.to_node].append((e.from_node, e.weight, e.id))
            
        if CAlgorithmsWrapper:
            self.c_wrapper = CAlgorithmsWrapper(nodes, edges)
        else:
            self.c_wrapper = None

    def _heuristic(self, node_id: int, target_id: int) -> float:
        """
        Euclidean distance heuristic.
        FIXED: Divided by 10 to match edge weight scale (weights = pixel_dist / 10).
        This makes A* admissible — it never overestimates, guaranteeing optimal paths.
        """
        n1 = self.nodes[node_id]
        n2 = self.nodes[target_id]
        return math.sqrt((n1.x - n2.x) ** 2 + (n1.y - n2.y) ** 2) / 10

    def run(self, algo_name: str, start_id: int, end_id: int,
            waypoints: Optional[List[int]] = None) -> Dict[str, Any]:
        wps = [w for w in (waypoints or []) if w not in (start_id, end_id)]

        # AO* uses greedy waypoint ordering + A* segments
        if algo_name == "ao_star":
            return self._ao_star(start_id, end_id, wps)

        # For ALL other algorithms: if waypoints exist, route through them
        if wps:
            return self._route_through_waypoints(algo_name, start_id, end_id, wps)

        # No waypoints — run directly
        return self._run_single(algo_name, start_id, end_id)

    def _run_single(self, algo_name: str, start_id: int, end_id: int) -> Dict[str, Any]:
        """Run a single algorithm from start to end (no waypoints)."""
        if algo_name == "dijkstra":
            if getattr(self, "c_wrapper", None) and self.c_wrapper.available:
                res = self.c_wrapper.run_dijkstra(start_id, end_id)
                if res: return res
            return self._astar_variant(start_id, end_id, use_g=True, use_h=False)
        elif algo_name == "astar":
            return self._astar_variant(start_id, end_id, use_g=True, use_h=True)
        elif algo_name == "greedy":
            return self._astar_variant(start_id, end_id, use_g=False, use_h=True)
        elif algo_name == "binary_search":
            return self._binary_search_path(start_id, end_id)
        elif algo_name == "topo_sort":
            if getattr(self, "c_wrapper", None) and self.c_wrapper.available:
                res = self.c_wrapper.run_topo_sort(start_id, end_id)
                if res: return res
            return self._topological_sort(start_id, end_id)
        elif algo_name == "dfs":
            if getattr(self, "c_wrapper", None) and self.c_wrapper.available:
                res = self.c_wrapper.run_dfs(start_id, end_id)
                if res: return res
            return self._dfs(start_id, end_id)
        elif algo_name == "bfs":
            if getattr(self, "c_wrapper", None) and self.c_wrapper.available:
                res = self.c_wrapper.run_bfs(start_id, end_id)
                if res: return res
            return self._bfs(start_id, end_id)
        else:
            raise ValueError(f"Unknown algorithm: {algo_name}")

    def _route_through_waypoints(self, algo_name: str, start_id: int,
                                  end_id: int, waypoints: List[int]) -> Dict[str, Any]:
        """
        Route through ALL waypoints in the order given, using the
        selected algorithm for each segment.
        Every algorithm now respects waypoints — not just AO*.
        """
        all_visited: List[int] = []
        all_path_nodes: List[int] = []
        all_path_edges: List[str] = []
        total_cost = 0

        stops = waypoints + [end_id]
        current = start_id
        failed = False

        for stop in stops:
            seg = self._run_single(algo_name, current, stop)
            for n in seg["visited_order"]:
                if n not in all_visited:
                    all_visited.append(n)
            if not seg["path_nodes"]:
                failed = True
                break
            if all_path_nodes:
                all_path_nodes.extend(seg["path_nodes"][1:])
            else:
                all_path_nodes.extend(seg["path_nodes"])
            all_path_edges.extend(seg["path_edges"])
            if seg["total_cost"] >= 0:
                total_cost += seg["total_cost"]
            else:
                failed = True
                break
            current = stop

        if failed:
            total_cost = -1
            all_path_nodes = []
            all_path_edges = []

        return {
            "path_nodes": all_path_nodes,
            "path_edges": all_path_edges,
            "visited_order": all_visited,
            "total_cost": total_cost,
            "waypoint_order": waypoints,
        }

    # ------------------------------------------------------------------ #
    #  A* / Dijkstra / Greedy unified implementation                       #
    # ------------------------------------------------------------------ #
    def _astar_variant(self, start_id: int, end_id: int,
                       use_g: bool, use_h: bool) -> Dict[str, Any]:
        queue = [(0, 0, start_id)]
        came_from: Dict[int, tuple] = {}
        g_scores = {n_id: float('inf') for n_id in self.nodes}
        g_scores[start_id] = 0
        visited_order: List[int] = []

        while queue:
            priority, current_g, current_id = heapq.heappop(queue)

            if current_id not in visited_order:
                visited_order.append(current_id)

            if current_id == end_id:
                break

            if current_g > g_scores[current_id]:
                continue

            for neighbor_id, weight, edge_id in self.graph[current_id]:
                tentative_g = g_scores[current_id] + weight
                if not use_g or tentative_g < g_scores[neighbor_id]:
                    came_from[neighbor_id] = (current_id, edge_id)
                    g_scores[neighbor_id] = tentative_g
                    h = self._heuristic(neighbor_id, end_id) if use_h else 0
                    g = tentative_g if use_g else 0
                    heapq.heappush(queue, (g + h, tentative_g, neighbor_id))

        path_nodes, path_edges = [], []
        if end_id in came_from or start_id == end_id:
            curr = end_id
            while curr in came_from:
                path_nodes.insert(0, curr)
                prev, edge_id = came_from[curr]
                path_edges.insert(0, edge_id)
                curr = prev
            path_nodes.insert(0, start_id)

        return {
            "path_nodes": path_nodes,
            "path_edges": path_edges,
            "visited_order": visited_order,
            "total_cost": g_scores[end_id] if end_id in came_from else -1,
        }

    # ------------------------------------------------------------------ #
    #  Binary Search — Minimax / Bottleneck Path                           #
    # ------------------------------------------------------------------ #
    def _binary_search_path(self, start_id: int, end_id: int) -> Dict[str, Any]:
        """
        Uses Binary Search on sorted edge weights to find the path that
        MINIMISES the maximum single-edge weight (bottleneck / minimax path).

        Steps:
          1. Sort all unique edge weights.
          2. Binary-search for the minimum threshold T such that a path
             exists using only edges with weight <= T.
          3. Reconstruct that path.

        This is the classic "minimum bottleneck path" problem and is a
        textbook application of binary search in graph algorithms.
        """
        all_weights = sorted(set(e.weight for e in self.edges))
        visited_order: List[int] = []

        def bfs_under_threshold(threshold: float):
            """BFS restricted to edges whose weight <= threshold."""
            from collections import deque
            q = deque([start_id])
            seen = {start_id}
            cf: Dict[int, tuple] = {}
            local_vis: List[int] = []

            while q:
                curr = q.popleft()
                local_vis.append(curr)
                if curr == end_id:
                    return True, local_vis, cf
                for nb, w, eid in self.graph[curr]:
                    if nb not in seen and w <= threshold:
                        seen.add(nb)
                        cf[nb] = (curr, eid)
                        q.append(nb)
            return False, local_vis, cf

        # Binary search
        lo, hi = 0, len(all_weights) - 1
        best_threshold = all_weights[-1]
        best_cf: Dict[int, tuple] = {}

        while lo <= hi:
            mid = (lo + hi) // 2
            threshold = all_weights[mid]
            exists, local_vis, cf = bfs_under_threshold(threshold)
            for n in local_vis:
                if n not in visited_order:
                    visited_order.append(n)
            if exists:
                best_threshold = threshold
                best_cf = cf
                hi = mid - 1
            else:
                lo = mid + 1

        # Reconstruct path
        path_nodes, path_edges, total_cost = [], [], 0
        if end_id in best_cf:
            curr = end_id
            while curr in best_cf:
                path_nodes.insert(0, curr)
                prev, edge_id = best_cf[curr]
                path_edges.insert(0, edge_id)
                for nb, w, eid in self.graph[prev]:
                    if eid == edge_id:
                        total_cost += w
                        break
                curr = prev
            path_nodes.insert(0, start_id)
        else:
            total_cost = -1

        return {
            "path_nodes": path_nodes,
            "path_edges": path_edges,
            "visited_order": visited_order,
            "total_cost": total_cost,
            "bottleneck": best_threshold,
        }

    # ------------------------------------------------------------------ #
    #  AO* — AND-OR Graph Search (mandatory waypoints)                     #
    # ------------------------------------------------------------------ #
    def _ao_star(self, start_id: int, end_id: int,
                 waypoints: List[int]) -> Dict[str, Any]:
        """
        AO* for AND-OR navigation graphs.

        Waypoint nodes are AND-nodes: ALL of them MUST be visited.
        The choice of which edge to take between stops is an OR-node decision.

        Strategy:
          1. Greedily order waypoints by nearest A* cost from current position.
          2. Run A* for each segment: start -> wp1 -> wp2 -> ... -> end.
          3. Concatenate segments into a single path.

        The AND constraint (must visit every waypoint) is fully enforced.
        """
        all_visited: List[int] = []
        all_path_nodes: List[int] = []
        all_path_edges: List[str] = []
        total_cost = 0

        # Greedily order waypoints: always pick nearest unvisited from current pos
        remaining = list(waypoints)
        current = start_id
        ordered_stops: List[int] = []

        while remaining:
            best_cost = float('inf')
            best_wp = None
            for wp in remaining:
                r = self._astar_variant(current, wp, use_g=True, use_h=True)
                if 0 <= r["total_cost"] < best_cost:
                    best_cost = r["total_cost"]
                    best_wp = wp
            if best_wp is None:
                break
            ordered_stops.append(best_wp)
            remaining.remove(best_wp)
            current = best_wp

        ordered_stops.append(end_id)

        # Run A* for each segment
        current = start_id
        failed = False
        for stop in ordered_stops:
            seg = self._astar_variant(current, stop, use_g=True, use_h=True)
            for n in seg["visited_order"]:
                if n not in all_visited:
                    all_visited.append(n)
            if not seg["path_nodes"]:
                failed = True
                break
            if all_path_nodes:
                all_path_nodes.extend(seg["path_nodes"][1:])
            else:
                all_path_nodes.extend(seg["path_nodes"])
            all_path_edges.extend(seg["path_edges"])
            if seg["total_cost"] >= 0:
                total_cost += seg["total_cost"]
            else:
                failed = True
                break
            current = stop

        if failed:
            total_cost = -1
            all_path_nodes = []
            all_path_edges = []

        return {
            "path_nodes": all_path_nodes,
            "path_edges": all_path_edges,
            "visited_order": all_visited,
            "total_cost": total_cost,
            "waypoint_order": ordered_stops[:-1],
        }

    # ------------------------------------------------------------------ #
    #  DFS / BFS                                                           #
    # ------------------------------------------------------------------ #
    def _dfs(self, start_id: int, end_id: int) -> Dict[str, Any]:
        stack = [(start_id, None, None)]
        came_from: Dict[int, tuple] = {}
        visited_order: List[int] = []
        visited_set: set = set()

        while stack:
            current_id, prev_id, edge_id = stack.pop()
            if current_id not in visited_set:
                visited_set.add(current_id)
                visited_order.append(current_id)
                if prev_id is not None:
                    came_from[current_id] = (prev_id, edge_id)
                if current_id == end_id:
                    break
                for nb, w, eid in reversed(self.graph[current_id]):
                    if nb not in visited_set:
                        stack.append((nb, current_id, eid))

        return self._reconstruct(start_id, end_id, came_from, visited_order)

    def _bfs(self, start_id: int, end_id: int) -> Dict[str, Any]:
        from collections import deque
        queue = deque([start_id])
        came_from: Dict[int, tuple] = {}
        visited_order: List[int] = []
        visited_set = {start_id}

        while queue:
            current_id = queue.popleft()
            visited_order.append(current_id)
            if current_id == end_id:
                break
            for nb, w, eid in self.graph[current_id]:
                if nb not in visited_set:
                    visited_set.add(nb)
                    came_from[nb] = (current_id, eid)
                    queue.append(nb)

        return self._reconstruct(start_id, end_id, came_from, visited_order)

    # ------------------------------------------------------------------ #
    #  Topological Sort — DAG Shortest Path                              #
    # ------------------------------------------------------------------ #
    def _topological_sort(self, start_id: int, end_id: int) -> Dict[str, Any]:
        """
        Shortest path in a Directed Acyclic Graph (DAG) using topological ordering.

        Steps:
          1. Build a directed adjacency list from the edges.
          2. Compute in-degrees and run Kahn's algorithm (BFS) to get a
             topological order. If a cycle is detected (not all nodes are
             processed), fall back to Dijkstra.
          3. Walk the topological order, relaxing edges via dynamic programming,
             to find the shortest path from start to end in O(V + E).

        This is significantly faster than Dijkstra for DAGs because each node
        and edge is processed exactly once.
        """
        from collections import deque

        # --- 1. Build directed adjacency list & in-degree map ---
        directed: Dict[int, list] = {n_id: [] for n_id in self.nodes}
        in_degree: Dict[int, int] = {n_id: 0 for n_id in self.nodes}

        for e in self.edges:
            directed[e.from_node].append((e.to_node, e.weight, e.id))
            in_degree[e.to_node] = in_degree.get(e.to_node, 0) + 1

        # --- 2. Kahn's algorithm for topological ordering ---
        queue = deque([n for n in self.nodes if in_degree[n] == 0])
        topo_order: List[int] = []
        visited_order: List[int] = []

        while queue:
            node = queue.popleft()
            topo_order.append(node)
            visited_order.append(node)
            for neighbor, weight, eid in directed[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Cycle detection — topo sort is only valid for DAGs
        if len(topo_order) != len(self.nodes):
            # Graph has a cycle → fall back to Dijkstra
            return self._astar_variant(start_id, end_id, use_g=True, use_h=False)

        # --- 3. DP shortest path along topological order ---
        dist: Dict[int, float] = {n_id: float('inf') for n_id in self.nodes}
        came_from: Dict[int, tuple] = {}
        dist[start_id] = 0

        for node in topo_order:
            if dist[node] == float('inf'):
                continue
            for neighbor, weight, eid in directed[node]:
                new_dist = dist[node] + weight
                if new_dist < dist[neighbor]:
                    dist[neighbor] = new_dist
                    came_from[neighbor] = (node, eid)

        # --- 4. Reconstruct path ---
        path_nodes, path_edges, total_cost = [], [], 0
        if end_id in came_from or start_id == end_id:
            curr = end_id
            while curr in came_from:
                path_nodes.insert(0, curr)
                prev, edge_id = came_from[curr]
                path_edges.insert(0, edge_id)
                for nb, w, eid in directed[prev]:
                    if eid == edge_id:
                        total_cost += w
                        break
                curr = prev
            path_nodes.insert(0, start_id)
        else:
            total_cost = -1

        return {
            "path_nodes": path_nodes,
            "path_edges": path_edges,
            "visited_order": visited_order,
            "total_cost": total_cost,
            "topo_order": topo_order,
        }

    def _reconstruct(self, start_id: int, end_id: int,
                     came_from: Dict[int, Any],
                     visited_order: List[int]) -> Dict[str, Any]:
        path_nodes, path_edges, total_cost = [], [], 0
        if end_id in came_from or start_id == end_id:
            curr = end_id
            while curr in came_from:
                path_nodes.insert(0, curr)
                prev, edge_id = came_from[curr]
                path_edges.insert(0, edge_id)
                for nb, w, eid in self.graph[prev]:
                    if eid == edge_id:
                        total_cost += w
                        break
                curr = prev
            path_nodes.insert(0, start_id)
        else:
            total_cost = -1
        return {
            "path_nodes": path_nodes,
            "path_edges": path_edges,
            "visited_order": visited_order,
            "total_cost": total_cost,
        }
