import ctypes
import os
import sys

# Locate the compiled library
lib_name = "c_algorithms.dll" if sys.platform == "win32" else "libc_algorithms.so"
lib_path = os.path.join(os.path.dirname(__file__), lib_name)

c_lib = None
if os.path.exists(lib_path):
    try:
        c_lib = ctypes.CDLL(lib_path)
    except Exception as e:
        print(f"Failed to load C algorithms library: {e}")

# Define function signatures if loaded
if c_lib:
    # Common signature types
    INT_PTR = ctypes.POINTER(ctypes.c_int)
    FLOAT_PTR = ctypes.POINTER(ctypes.c_float)
    
    # void dijkstra_c(...)
    c_lib.dijkstra_c.argtypes = [
        ctypes.c_int, ctypes.c_int, 
        INT_PTR, INT_PTR, FLOAT_PTR, 
        ctypes.c_int, ctypes.c_int,
        INT_PTR, INT_PTR, INT_PTR, INT_PTR, INT_PTR, FLOAT_PTR
    ]
    
    c_lib.bfs_c.argtypes = c_lib.dijkstra_c.argtypes
    c_lib.dfs_c.argtypes = c_lib.dijkstra_c.argtypes
    
    # topo_sort_c has an extra out_is_dag parameter
    c_lib.topo_sort_c.argtypes = [
        ctypes.c_int, ctypes.c_int, 
        INT_PTR, INT_PTR, FLOAT_PTR, 
        ctypes.c_int, ctypes.c_int,
        INT_PTR, INT_PTR, INT_PTR, INT_PTR, INT_PTR, FLOAT_PTR, INT_PTR
    ]


class CAlgorithmsWrapper:
    def __init__(self, nodes, edges):
        self.available = c_lib is not None
        if not self.available:
            return
            
        self.nodes = nodes
        self.edges = edges
        
        # Mapping dictionaries
        self.node_to_idx = {n.id: i for i, n in enumerate(nodes)}
        self.idx_to_node = {i: n.id for i, n in enumerate(nodes)}
        
        self.edge_to_idx = {e.id: i for i, e in enumerate(edges)}
        self.idx_to_edge = {i: e.id for i, e in enumerate(edges)}
        
        self.num_nodes = len(nodes)
        self.num_edges = len(edges)
        
        # Prepare C arrays
        edge_from_list = [self.node_to_idx[e.from_node] for e in edges]
        edge_to_list = [self.node_to_idx[e.to_node] for e in edges]
        edge_weights_list = [e.weight for e in edges]
        
        self.c_edge_from = (ctypes.c_int * self.num_edges)(*edge_from_list)
        self.c_edge_to = (ctypes.c_int * self.num_edges)(*edge_to_list)
        self.c_edge_weights = (ctypes.c_float * self.num_edges)(*edge_weights_list)

    def _call_c_algo(self, algo_func, start_id, end_id, is_topo=False):
        if start_id not in self.node_to_idx or end_id not in self.node_to_idx:
            return None
            
        start_idx = self.node_to_idx[start_id]
        end_idx = self.node_to_idx[end_id]
        
        # Output arrays
        out_path_nodes = (ctypes.c_int * self.num_nodes)()
        out_path_length = ctypes.c_int(0)
        out_path_edges = (ctypes.c_int * self.num_nodes)()
        out_visited = (ctypes.c_int * self.num_nodes)()
        out_visited_length = ctypes.c_int(0)
        out_total_cost = ctypes.c_float(0.0)
        out_is_dag = ctypes.c_int(1)
        
        if is_topo:
            algo_func(
                self.num_nodes, self.num_edges,
                self.c_edge_from, self.c_edge_to, self.c_edge_weights,
                start_idx, end_idx,
                out_path_nodes, ctypes.byref(out_path_length), out_path_edges,
                out_visited, ctypes.byref(out_visited_length), ctypes.byref(out_total_cost), ctypes.byref(out_is_dag)
            )
            if out_is_dag.value == 0:
                # Not a DAG, fallback needed
                return None
        else:
            algo_func(
                self.num_nodes, self.num_edges,
                self.c_edge_from, self.c_edge_to, self.c_edge_weights,
                start_idx, end_idx,
                out_path_nodes, ctypes.byref(out_path_length), out_path_edges,
                out_visited, ctypes.byref(out_visited_length), ctypes.byref(out_total_cost)
            )
            
        p_len = out_path_length.value
        v_len = out_visited_length.value
        
        path_nodes = [self.idx_to_node[out_path_nodes[i]] for i in range(p_len)]
        path_edges = [self.idx_to_edge[out_path_edges[i]] for i in range(p_len - 1)] if p_len > 0 else []
        visited_order = [self.idx_to_node[out_visited[i]] for i in range(v_len)]
        
        # Format consistent with python algorithms
        res = {
            "path_nodes": path_nodes,
            "path_edges": path_edges,
            "visited_order": visited_order,
            "total_cost": float(out_total_cost.value) if p_len > 0 else -1
        }
        
        if is_topo:
            res["topo_order"] = visited_order
            
        return res

    def run_dijkstra(self, start_id, end_id):
        return self._call_c_algo(c_lib.dijkstra_c, start_id, end_id)

    def run_bfs(self, start_id, end_id):
        return self._call_c_algo(c_lib.bfs_c, start_id, end_id)

    def run_dfs(self, start_id, end_id):
        return self._call_c_algo(c_lib.dfs_c, start_id, end_id)

    def run_topo_sort(self, start_id, end_id):
        return self._call_c_algo(c_lib.topo_sort_c, start_id, end_id, is_topo=True)
