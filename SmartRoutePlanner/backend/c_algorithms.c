#include <stdio.h>
#include <stdlib.h>
#include <float.h>
#include <stdbool.h>

// --- Data Structures ---

typedef struct {
    int to;
    float weight;
    int edge_idx;
} AdjEdge;

typedef struct {
    AdjEdge* edges;
    int count;
    int capacity;
} AdjList;

// --- Helper Functions ---

AdjList* build_graph(int num_nodes, int num_edges, int* edge_from, int* edge_to, float* edge_weights, bool directed) {
    AdjList* graph = (AdjList*)malloc(num_nodes * sizeof(AdjList));
    for (int i = 0; i < num_nodes; i++) {
        graph[i].count = 0;
        graph[i].capacity = 4;
        graph[i].edges = (AdjEdge*)malloc(graph[i].capacity * sizeof(AdjEdge));
    }

    for (int i = 0; i < num_edges; i++) {
        int u = edge_from[i];
        int v = edge_to[i];
        float w = edge_weights[i];

        // Add u -> v
        if (graph[u].count == graph[u].capacity) {
            graph[u].capacity *= 2;
            graph[u].edges = (AdjEdge*)realloc(graph[u].edges, graph[u].capacity * sizeof(AdjEdge));
        }
        graph[u].edges[graph[u].count].to = v;
        graph[u].edges[graph[u].count].weight = w;
        graph[u].edges[graph[u].count].edge_idx = i;
        graph[u].count++;

        // Add v -> u if undirected
        if (!directed) {
            if (graph[v].count == graph[v].capacity) {
                graph[v].capacity *= 2;
                graph[v].edges = (AdjEdge*)realloc(graph[v].edges, graph[v].capacity * sizeof(AdjEdge));
            }
            graph[v].edges[graph[v].count].to = u;
            graph[v].edges[graph[v].count].weight = w;
            graph[v].edges[graph[v].count].edge_idx = i;
            graph[v].count++;
        }
    }
    return graph;
}

void free_graph(AdjList* graph, int num_nodes) {
    for (int i = 0; i < num_nodes; i++) {
        free(graph[i].edges);
    }
    free(graph);
}

// Priority Queue for Dijkstra
typedef struct {
    float priority;
    int node;
} PQElement;

typedef struct {
    PQElement* data;
    int size;
    int capacity;
} MinHeap;

MinHeap* create_heap(int capacity) {
    MinHeap* heap = (MinHeap*)malloc(sizeof(MinHeap));
    heap->capacity = capacity;
    heap->size = 0;
    heap->data = (PQElement*)malloc(capacity * sizeof(PQElement));
    return heap;
}

void swap_pq(PQElement* a, PQElement* b) {
    PQElement temp = *a;
    *a = *b;
    *b = temp;
}

void heap_push(MinHeap* heap, float priority, int node) {
    if (heap->size == heap->capacity) return; // Should not happen if sized properly
    int i = heap->size++;
    heap->data[i].priority = priority;
    heap->data[i].node = node;
    
    while (i != 0 && heap->data[(i - 1) / 2].priority > heap->data[i].priority) {
        swap_pq(&heap->data[i], &heap->data[(i - 1) / 2]);
        i = (i - 1) / 2;
    }
}

PQElement heap_pop(MinHeap* heap) {
    if (heap->size <= 0) return (PQElement){-1, -1};
    if (heap->size == 1) {
        heap->size--;
        return heap->data[0];
    }

    PQElement root = heap->data[0];
    heap->data[0] = heap->data[heap->size - 1];
    heap->size--;

    int i = 0;
    while (true) {
        int l = 2 * i + 1;
        int r = 2 * i + 2;
        int smallest = i;

        if (l < heap->size && heap->data[l].priority < heap->data[smallest].priority) smallest = l;
        if (r < heap->size && heap->data[r].priority < heap->data[smallest].priority) smallest = r;

        if (smallest != i) {
            swap_pq(&heap->data[i], &heap->data[smallest]);
            i = smallest;
        } else {
            break;
        }
    }
    return root;
}

void free_heap(MinHeap* heap) {
    free(heap->data);
    free(heap);
}


// --- Algorithms ---

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

EXPORT void dijkstra_c(
    int num_nodes, int num_edges, 
    int* edge_from, int* edge_to, float* edge_weights, 
    int start_node, int end_node,
    int* out_path_nodes, int* out_path_length,
    int* out_path_edges,
    int* out_visited, int* out_visited_length,
    float* out_total_cost
) {
    AdjList* graph = build_graph(num_nodes, num_edges, edge_from, edge_to, edge_weights, false);
    
    float* g_scores = (float*)malloc(num_nodes * sizeof(float));
    int* came_from_node = (int*)malloc(num_nodes * sizeof(int));
    int* came_from_edge = (int*)malloc(num_nodes * sizeof(int));
    bool* in_visited_array = (bool*)malloc(num_nodes * sizeof(bool));
    
    for (int i = 0; i < num_nodes; i++) {
        g_scores[i] = FLT_MAX;
        came_from_node[i] = -1;
        came_from_edge[i] = -1;
        in_visited_array[i] = false;
    }
    
    g_scores[start_node] = 0;
    MinHeap* pq = create_heap(num_edges * 2 + 10);
    heap_push(pq, 0, start_node);
    
    int visited_count = 0;
    
    while (pq->size > 0) {
        PQElement current = heap_pop(pq);
        int u = current.node;
        
        if (!in_visited_array[u]) {
            out_visited[visited_count++] = u;
            in_visited_array[u] = true;
        }
        
        if (u == end_node) break;
        if (current.priority > g_scores[u]) continue;
        
        for (int i = 0; i < graph[u].count; i++) {
            int v = graph[u].edges[i].to;
            float weight = graph[u].edges[i].weight;
            int e_idx = graph[u].edges[i].edge_idx;
            
            float tentative_g = g_scores[u] + weight;
            if (tentative_g < g_scores[v]) {
                came_from_node[v] = u;
                came_from_edge[v] = e_idx;
                g_scores[v] = tentative_g;
                heap_push(pq, tentative_g, v);
            }
        }
    }
    
    *out_visited_length = visited_count;
    
    // Reconstruct path
    int p_count = 0;
    if (came_from_node[end_node] != -1 || start_node == end_node) {
        int curr = end_node;
        // Count length
        while (curr != -1 && curr != start_node) {
            p_count++;
            curr = came_from_node[curr];
        }
        p_count++; // Include start_node
        
        *out_path_length = p_count;
        
        curr = end_node;
        int idx = p_count - 1;
        while (curr != -1 && curr != start_node) {
            out_path_nodes[idx] = curr;
            out_path_edges[idx - 1] = came_from_edge[curr];
            curr = came_from_node[curr];
            idx--;
        }
        out_path_nodes[0] = start_node;
        *out_total_cost = g_scores[end_node];
    } else {
        *out_path_length = 0;
        *out_total_cost = -1;
    }
    
    free_heap(pq);
    free(g_scores);
    free(came_from_node);
    free(came_from_edge);
    free(in_visited_array);
    free_graph(graph, num_nodes);
}


EXPORT void bfs_c(
    int num_nodes, int num_edges, 
    int* edge_from, int* edge_to, float* edge_weights, 
    int start_node, int end_node,
    int* out_path_nodes, int* out_path_length,
    int* out_path_edges,
    int* out_visited, int* out_visited_length,
    float* out_total_cost
) {
    AdjList* graph = build_graph(num_nodes, num_edges, edge_from, edge_to, edge_weights, false);
    
    int* queue = (int*)malloc(num_nodes * sizeof(int));
    int head = 0, tail = 0;
    
    int* came_from_node = (int*)malloc(num_nodes * sizeof(int));
    int* came_from_edge = (int*)malloc(num_nodes * sizeof(int));
    bool* visited = (bool*)malloc(num_nodes * sizeof(bool));
    
    for (int i = 0; i < num_nodes; i++) {
        came_from_node[i] = -1;
        came_from_edge[i] = -1;
        visited[i] = false;
    }
    
    queue[tail++] = start_node;
    visited[start_node] = true;
    
    int visited_count = 0;
    
    while (head < tail) {
        int u = queue[head++];
        out_visited[visited_count++] = u;
        
        if (u == end_node) break;
        
        for (int i = 0; i < graph[u].count; i++) {
            int v = graph[u].edges[i].to;
            int e_idx = graph[u].edges[i].edge_idx;
            
            if (!visited[v]) {
                visited[v] = true;
                came_from_node[v] = u;
                came_from_edge[v] = e_idx;
                queue[tail++] = v;
            }
        }
    }
    
    *out_visited_length = visited_count;
    
    int p_count = 0;
    float cost = 0;
    if (came_from_node[end_node] != -1 || start_node == end_node) {
        int curr = end_node;
        while (curr != -1 && curr != start_node) {
            p_count++;
            curr = came_from_node[curr];
        }
        p_count++;
        
        *out_path_length = p_count;
        
        curr = end_node;
        int idx = p_count - 1;
        while (curr != -1 && curr != start_node) {
            out_path_nodes[idx] = curr;
            int e_idx = came_from_edge[curr];
            out_path_edges[idx - 1] = e_idx;
            cost += edge_weights[e_idx];
            curr = came_from_node[curr];
            idx--;
        }
        out_path_nodes[0] = start_node;
        *out_total_cost = cost;
    } else {
        *out_path_length = 0;
        *out_total_cost = -1;
    }
    
    free(queue);
    free(came_from_node);
    free(came_from_edge);
    free(visited);
    free_graph(graph, num_nodes);
}


EXPORT void dfs_c(
    int num_nodes, int num_edges, 
    int* edge_from, int* edge_to, float* edge_weights, 
    int start_node, int end_node,
    int* out_path_nodes, int* out_path_length,
    int* out_path_edges,
    int* out_visited, int* out_visited_length,
    float* out_total_cost
) {
    AdjList* graph = build_graph(num_nodes, num_edges, edge_from, edge_to, edge_weights, false);
    
    // Stack items
    typedef struct { int node; int prev; int edge; } StackItem;
    StackItem* stack = (StackItem*)malloc((num_nodes + num_edges) * sizeof(StackItem));
    int top = 0;
    
    int* came_from_node = (int*)malloc(num_nodes * sizeof(int));
    int* came_from_edge = (int*)malloc(num_nodes * sizeof(int));
    bool* visited = (bool*)malloc(num_nodes * sizeof(bool));
    
    for (int i = 0; i < num_nodes; i++) {
        came_from_node[i] = -1;
        came_from_edge[i] = -1;
        visited[i] = false;
    }
    
    stack[top].node = start_node;
    stack[top].prev = -1;
    stack[top].edge = -1;
    top++;
    
    int visited_count = 0;
    
    while (top > 0) {
        top--;
        StackItem current = stack[top];
        int u = current.node;
        
        if (!visited[u]) {
            visited[u] = true;
            out_visited[visited_count++] = u;
            if (current.prev != -1) {
                came_from_node[u] = current.prev;
                came_from_edge[u] = current.edge;
            }
            if (u == end_node) break;
            
            // Push neighbors in reverse order to mimic Python's reversed() loop
            for (int i = graph[u].count - 1; i >= 0; i--) {
                int v = graph[u].edges[i].to;
                if (!visited[v]) {
                    stack[top].node = v;
                    stack[top].prev = u;
                    stack[top].edge = graph[u].edges[i].edge_idx;
                    top++;
                }
            }
        }
    }
    
    *out_visited_length = visited_count;
    
    int p_count = 0;
    float cost = 0;
    if (came_from_node[end_node] != -1 || start_node == end_node) {
        int curr = end_node;
        while (curr != -1 && curr != start_node) {
            p_count++;
            curr = came_from_node[curr];
        }
        p_count++;
        
        *out_path_length = p_count;
        curr = end_node;
        int idx = p_count - 1;
        while (curr != -1 && curr != start_node) {
            out_path_nodes[idx] = curr;
            int e_idx = came_from_edge[curr];
            out_path_edges[idx - 1] = e_idx;
            cost += edge_weights[e_idx];
            curr = came_from_node[curr];
            idx--;
        }
        out_path_nodes[0] = start_node;
        *out_total_cost = cost;
    } else {
        *out_path_length = 0;
        *out_total_cost = -1;
    }
    
    free(stack);
    free(came_from_node);
    free(came_from_edge);
    free(visited);
    free_graph(graph, num_nodes);
}


EXPORT void topo_sort_c(
    int num_nodes, int num_edges, 
    int* edge_from, int* edge_to, float* edge_weights, 
    int start_node, int end_node,
    int* out_path_nodes, int* out_path_length,
    int* out_path_edges,
    int* out_visited, int* out_visited_length,
    float* out_total_cost,
    int* out_is_dag
) {
    AdjList* graph = build_graph(num_nodes, num_edges, edge_from, edge_to, edge_weights, true); // directed graph
    
    int* in_degree = (int*)calloc(num_nodes, sizeof(int));
    for (int u = 0; u < num_nodes; u++) {
        for (int i = 0; i < graph[u].count; i++) {
            int v = graph[u].edges[i].to;
            in_degree[v]++;
        }
    }
    
    int* queue = (int*)malloc(num_nodes * sizeof(int));
    int head = 0, tail = 0;
    
    for (int i = 0; i < num_nodes; i++) {
        if (in_degree[i] == 0) queue[tail++] = i;
    }
    
    int* topo_order = (int*)malloc(num_nodes * sizeof(int));
    int topo_count = 0;
    
    while (head < tail) {
        int u = queue[head++];
        topo_order[topo_count++] = u;
        out_visited[topo_count - 1] = u; // visited order is topo order
        
        for (int i = 0; i < graph[u].count; i++) {
            int v = graph[u].edges[i].to;
            in_degree[v]--;
            if (in_degree[v] == 0) queue[tail++] = v;
        }
    }
    
    *out_visited_length = topo_count;
    
    if (topo_count != num_nodes) {
        // Cycle detected
        *out_is_dag = 0;
        free(in_degree); free(queue); free(topo_order); free_graph(graph, num_nodes);
        return;
    }
    *out_is_dag = 1;
    
    // DP for shortest path
    float* dist = (float*)malloc(num_nodes * sizeof(float));
    int* came_from_node = (int*)malloc(num_nodes * sizeof(int));
    int* came_from_edge = (int*)malloc(num_nodes * sizeof(int));
    
    for (int i = 0; i < num_nodes; i++) {
        dist[i] = FLT_MAX;
        came_from_node[i] = -1;
        came_from_edge[i] = -1;
    }
    dist[start_node] = 0;
    
    for (int i = 0; i < num_nodes; i++) {
        int u = topo_order[i];
        if (dist[u] == FLT_MAX) continue;
        
        for (int j = 0; j < graph[u].count; j++) {
            int v = graph[u].edges[j].to;
            float weight = graph[u].edges[j].weight;
            if (dist[u] + weight < dist[v]) {
                dist[v] = dist[u] + weight;
                came_from_node[v] = u;
                came_from_edge[v] = graph[u].edges[j].edge_idx;
            }
        }
    }
    
    int p_count = 0;
    if (came_from_node[end_node] != -1 || start_node == end_node) {
        int curr = end_node;
        while (curr != -1 && curr != start_node) {
            p_count++;
            curr = came_from_node[curr];
        }
        p_count++;
        
        *out_path_length = p_count;
        curr = end_node;
        int idx = p_count - 1;
        while (curr != -1 && curr != start_node) {
            out_path_nodes[idx] = curr;
            out_path_edges[idx - 1] = came_from_edge[curr];
            curr = came_from_node[curr];
            idx--;
        }
        out_path_nodes[0] = start_node;
        *out_total_cost = dist[end_node];
    } else {
        *out_path_length = 0;
        *out_total_cost = -1;
    }
    
    free(dist); free(came_from_node); free(came_from_edge);
    free(in_degree); free(queue); free(topo_order); free_graph(graph, num_nodes);
}
