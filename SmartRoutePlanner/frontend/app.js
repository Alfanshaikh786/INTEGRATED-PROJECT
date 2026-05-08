document.addEventListener("DOMContentLoaded", () => {
    // =============================================
    // ===         STATE MANAGEMENT             ===
    // =============================================
    let nodes = [];
    let edges = [];
    let nextNodeId = 1;

    // Designated start/end nodes
    let startNodeId = null;
    let endNodeId = null;
    let waypointIds = new Set();  // AO* mandatory waypoints

    // Edge dragging state
    let isDraggingEdge = false;
    let dragStartNode = null;
    let currentMousePos = { x: 0, y: 0 };
    
    // Node dragging state
    let isDraggingNode = false;
    let dragTargetNode = null;
    
    const NODE_RADIUS = 22;

    // Visualization state (Phase 6)
    let vizVisited = [];       // ordered list of node IDs visited by algorithm
    let vizPathNodes = [];     // final path node IDs
    let vizPathEdges = [];     // final path edge IDs
    let vizCurrentStep = -1;   // which exploration step we're animating
    let vizTimer = null;       // interval handle
    let vizHighlightedNodes = new Set(); // nodes colored as "exploring"
    let vizFinalActive = false;         // true once full path is shown

    // =============================================
    // ===         CANVAS SETUP                 ===
    // =============================================
    const canvas = document.getElementById('graph-canvas');
    const ctx = canvas.getContext('2d');

    function resizeCanvas() {
        const container = canvas.parentElement;
        canvas.width = container.clientWidth;
        canvas.height = container.clientHeight;
        draw();
    }
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    function getMousePos(evt) {
        const rect = canvas.getBoundingClientRect();
        return {
            x: evt.clientX - rect.left,
            y: evt.clientY - rect.top
        };
    }

    function getNodeAt(x, y) {
        return nodes.find(n => {
            const dx = n.x - x;
            const dy = n.y - y;
            return Math.sqrt(dx * dx + dy * dy) <= NODE_RADIUS;
        });
    }

    // =============================================
    // ===         RADIO BUTTON UI              ===
    // =============================================
    const radioLabels = document.querySelectorAll('.radio-btn');
    const hintOverlay = document.getElementById('hint-overlay');

    const hints = {
        add_node: "Click anywhere on the canvas to add a city",
        add_edge: "Click & drag between two cities to draw a road • Double-click weight to edit",
        move_node: "Click & drag a city to reposition it",
        set_start: "Click a city to set it as the START point 🟢",
        set_end: "Click a city to set it as the END point 🔴",
        set_waypoint: "Click a city to toggle it as a WAYPOINT 📌 (used by AO*)"
    };

    radioLabels.forEach(label => {
        const input = label.querySelector('input[type="radio"]');
        input.addEventListener('change', () => {
            // Clear all active states on same-group buttons
            const name = input.name;
            document.querySelectorAll(`input[name="${name}"]`).forEach(inp => {
                inp.parentElement.classList.remove('active', 'start-active', 'end-active', 'waypoint-active');
            });

            if (input.value === 'set_start') {
                label.classList.add('start-active');
            } else if (input.value === 'set_end') {
                label.classList.add('end-active');
            } else if (input.value === 'set_waypoint') {
                label.classList.add('waypoint-active');
            } else {
                label.classList.add('active');
            }

            hintOverlay.textContent = hints[input.value] || "";
        });
    });

    function getMode() {
        return document.querySelector('input[name="mode"]:checked').value;
    }

    // =============================================
    // ===         CANVAS EVENTS                ===
    // =============================================
    canvas.addEventListener('mousedown', (e) => {
        const mode = getMode();
        const pos = getMousePos(e);
        const clickedNode = getNodeAt(pos.x, pos.y);

        if (mode === 'add_node') {
            if (!clickedNode) {
                // Clear visualization on graph change
                clearViz();
                nodes.push({ id: nextNodeId++, x: pos.x, y: pos.y });
                draw();
            }
        } else if (mode === 'add_edge') {
            if (clickedNode) {
                isDraggingEdge = true;
                dragStartNode = clickedNode;
                currentMousePos = pos;
            }
        } else if (mode === 'move_node') {
            if (clickedNode) {
                isDraggingNode = true;
                dragTargetNode = clickedNode;
            }
        } else if (mode === 'set_start') {
            if (clickedNode) {
                startNodeId = clickedNode.id;
                clearViz();
                draw();
            }
        } else if (mode === 'set_end') {
            if (clickedNode) {
                endNodeId = clickedNode.id;
                clearViz();
                draw();
            }
        } else if (mode === 'set_waypoint') {
            if (clickedNode) {
                if (waypointIds.has(clickedNode.id)) {
                    waypointIds.delete(clickedNode.id);
                } else {
                    waypointIds.add(clickedNode.id);
                }
                clearViz();
                draw();
            }
        }
    });

    canvas.addEventListener('mousemove', (e) => {
        if (isDraggingNode && dragTargetNode) {
            clearViz();
            const pos = getMousePos(e);
            dragTargetNode.x = pos.x;
            dragTargetNode.y = pos.y;
            draw();
        } else if (isDraggingEdge) {
            currentMousePos = getMousePos(e);
            draw();
        }
    });

    canvas.addEventListener('mouseup', (e) => {
        if (isDraggingNode) {
            isDraggingNode = false;
            dragTargetNode = null;
        }

        if (isDraggingEdge) {
            const pos = getMousePos(e);
            const endNode = getNodeAt(pos.x, pos.y);

            if (endNode && endNode !== dragStartNode) {
                const exists = edges.find(ed =>
                    (ed.from === dragStartNode.id && ed.to === endNode.id) ||
                    (ed.from === endNode.id && ed.to === dragStartNode.id)
                );

                if (!exists) {
                    clearViz();
                    const dx = dragStartNode.x - endNode.x;
                    const dy = dragStartNode.y - endNode.y;
                    const weight = Math.max(1, Math.round(Math.sqrt(dx * dx + dy * dy) / 10));

                    edges.push({
                        id: `${dragStartNode.id}-${endNode.id}`,
                        from: dragStartNode.id,
                        to: endNode.id,
                        weight: weight
                    });
                }
            }

            isDraggingEdge = false;
            dragStartNode = null;
            draw();
        }
    });

    canvas.addEventListener('dblclick', (e) => {
        const pos = getMousePos(e);
        for (let i = 0; i < edges.length; i++) {
            const edge = edges[i];
            const n1 = nodes.find(n => n.id === edge.from);
            const n2 = nodes.find(n => n.id === edge.to);
            if (n1 && n2) {
                const midX = (n1.x + n2.x) / 2;
                const midY = (n1.y + n2.y) / 2;
                const dx = pos.x - midX;
                const dy = pos.y - midY;
                if (Math.sqrt(dx * dx + dy * dy) <= 16) {
                    const newWeightStr = prompt(
                        `Edit weight for the road between City ${edge.from} → City ${edge.to}:`,
                        edge.weight
                    );
                    if (newWeightStr !== null) {
                        const newWeight = parseInt(newWeightStr, 10);
                        if (!isNaN(newWeight) && newWeight > 0) {
                            edge.weight = newWeight;
                            clearViz();
                            draw();
                        } else {
                            alert("Please enter a valid positive integer for the weight.");
                        }
                    }
                    break;
                }
            }
        }
    });

    // =============================================
    // ===         DRAW ENGINE                  ===
    // =============================================
    function getNodeColor(node) {
        // Final path takes priority
        if (vizFinalActive && vizPathNodes.includes(node.id)) {
            if (node.id === startNodeId) return { fill: '#15803d', stroke: '#22c55e', glow: '#22c55e' };
            if (node.id === endNodeId)   return { fill: '#991b1b', stroke: '#ef4444', glow: '#ef4444' };
            return { fill: '#065f46', stroke: '#10b981', glow: '#10b981' };
        }
        // Start / End designation
        if (node.id === startNodeId) return { fill: '#166534', stroke: '#22c55e', glow: '#22c55e' };
        if (node.id === endNodeId)   return { fill: '#991b1b', stroke: '#ef4444', glow: '#ef4444' };
        // Waypoint nodes (AO*)
        if (waypointIds.has(node.id)) {
            if (vizHighlightedNodes.has(node.id)) return { fill: '#581c87', stroke: '#c084fc', glow: '#c084fc' };
            return { fill: '#4c1d95', stroke: '#a855f7', glow: '#a855f7' };
        }
        // Visited during exploration
        if (vizHighlightedNodes.has(node.id)) return { fill: '#78350f', stroke: '#f59e0b', glow: '#f59e0b' };
        // Default
        return { fill: '#1e293b', stroke: '#3b82f6', glow: '#3b82f6' };
    }

    function getEdgeStyle(edge) {
        if (vizFinalActive && vizPathEdges.includes(edge.id)) {
            return { color: '#10b981', width: 5, glow: '#10b981' };
        }
        return { color: '#475569', width: 2.5, glow: null };
    }

    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw subtle grid
        ctx.strokeStyle = "rgba(255, 255, 255, 0.025)";
        ctx.lineWidth = 1;
        const gridSize = 40;
        for (let x = 0; x < canvas.width; x += gridSize) {
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
        }
        for (let y = 0; y < canvas.height; y += gridSize) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
        }

        // Draw edges
        edges.forEach(edge => {
            const n1 = nodes.find(n => n.id === edge.from);
            const n2 = nodes.find(n => n.id === edge.to);
            if (!n1 || !n2) return;

            const style = getEdgeStyle(edge);

            ctx.save();
            if (style.glow) {
                ctx.shadowColor = style.glow;
                ctx.shadowBlur = 12;
            }
            ctx.beginPath();
            ctx.moveTo(n1.x, n1.y);
            ctx.lineTo(n2.x, n2.y);
            ctx.strokeStyle = style.color;
            ctx.lineWidth = style.width;
            ctx.stroke();
            ctx.restore();

            // Weight badge
            const midX = (n1.x + n2.x) / 2;
            const midY = (n1.y + n2.y) / 2;
            const isPathEdge = vizFinalActive && vizPathEdges.includes(edge.id);

            ctx.beginPath();
            ctx.arc(midX, midY, 14, 0, Math.PI * 2);
            ctx.fillStyle = isPathEdge ? 'rgba(6, 95, 70, 0.95)' : 'rgba(15, 23, 42, 0.9)';
            ctx.fill();
            ctx.strokeStyle = isPathEdge ? '#10b981' : 'rgba(255,255,255,0.15)';
            ctx.lineWidth = 1.5;
            ctx.stroke();

            ctx.fillStyle = isPathEdge ? '#6ee7b7' : '#94a3b8';
            ctx.font = "bold 11px Inter";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(edge.weight, midX, midY);
        });

        // Draw dragging edge
        if (isDraggingEdge && dragStartNode) {
            ctx.save();
            ctx.setLineDash([6, 5]);
            ctx.strokeStyle = 'rgba(59, 130, 246, 0.6)';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(dragStartNode.x, dragStartNode.y);
            ctx.lineTo(currentMousePos.x, currentMousePos.y);
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.restore();
        }

        // Draw nodes
        nodes.forEach(node => {
            const colors = getNodeColor(node);

            ctx.save();
            ctx.shadowColor = colors.glow;
            ctx.shadowBlur = 18;

            ctx.beginPath();
            ctx.arc(node.x, node.y, NODE_RADIUS, 0, Math.PI * 2);
            ctx.fillStyle = colors.fill;
            ctx.fill();
            ctx.lineWidth = 2.5;
            ctx.strokeStyle = colors.stroke;
            ctx.stroke();

            ctx.shadowBlur = 0;

            // Node label
            ctx.fillStyle = '#f8fafc';
            ctx.font = "bold 13px Inter";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(node.id, node.x, node.y);

            // Start / End / Waypoint label badges
            if (node.id === startNodeId) {
                drawBadge(ctx, node.x, node.y - NODE_RADIUS - 12, 'START', '#22c55e');
            }
            if (node.id === endNodeId) {
                drawBadge(ctx, node.x, node.y - NODE_RADIUS - 12, 'END', '#ef4444');
            }
            if (waypointIds.has(node.id)) {
                drawBadge(ctx, node.x, node.y + NODE_RADIUS + 12, 'WP', '#a855f7');
            }

            ctx.restore();
        });
    }

    function drawBadge(ctx, x, y, text, color) {
        ctx.save();
        ctx.font = "bold 9px Inter";
        const w = ctx.measureText(text).width + 10;
        const h = 16;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.roundRect(x - w / 2, y - h / 2, w, h, 4);
        ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(text, x, y);
        ctx.restore();
    }

    // =============================================
    // ===         VISUALIZATION ENGINE         ===
    // =============================================
    function clearViz() {
        if (vizTimer) clearInterval(vizTimer);
        vizTimer = null;
        vizVisited = [];
        vizPathNodes = [];
        vizPathEdges = [];
        vizCurrentStep = -1;
        vizHighlightedNodes = new Set();
        vizFinalActive = false;
    }

    function getAnimDelay() {
        // Slider value is 50–800. Invert: high slider = fast = low delay.
        const sliderVal = parseInt(document.getElementById('speed-slider').value, 10);
        return 850 - sliderVal;  // range: 50ms (fast) to 800ms (slow)
    }

    function runVisualization(visitedOrder, pathNodes, pathEdges) {
        clearViz();
        vizVisited = visitedOrder;
        vizPathNodes = pathNodes;
        vizPathEdges = pathEdges;
        vizCurrentStep = 0;

        if (visitedOrder.length === 0) {
            vizFinalActive = true;
            draw();
            return;
        }

        const btn = document.getElementById('btn-find');
        btn.disabled = true;

        vizTimer = setInterval(() => {
            if (vizCurrentStep < vizVisited.length) {
                vizHighlightedNodes.add(vizVisited[vizCurrentStep]);
                vizCurrentStep++;
                draw();
            } else {
                // All exploration steps done → show final path
                clearInterval(vizTimer);
                vizTimer = null;
                vizFinalActive = true;
                draw();
                btn.disabled = false;
            }
        }, getAnimDelay());
    }

    // =============================================
    // ===         BUTTONS                      ===
    // =============================================
    document.getElementById('btn-find').addEventListener('click', async () => {
        const statsPanel = document.getElementById('stats-content');

        if (nodes.length < 2) {
            statsPanel.innerHTML = `<p style="color: #ef4444;">⚠️ Need at least 2 cities to find a path!</p>`;
            return;
        }

        // Determine start/end IDs
        const resolvedStart = startNodeId !== null ? startNodeId : nodes[0].id;
        const resolvedEnd   = endNodeId   !== null ? endNodeId   : nodes[nodes.length - 1].id;

        if (resolvedStart === resolvedEnd) {
            statsPanel.innerHTML = `<p style="color: #ef4444;">⚠️ Start and End cities must be different!</p>`;
            return;
        }

        statsPanel.innerHTML = `<p class="loading-pulse" style="color: #3b82f6;">🔄 Computing route...</p>`;
        clearViz();
        draw();

        const algo = document.getElementById('algo-select').value;
        const pref = document.querySelector('input[name="pref"]:checked').value;

        // Generate random traffic multipliers when Traffic preference is selected
        let trafficMultipliers = null;
        if (pref === 'traffic') {
            trafficMultipliers = {};
            edges.forEach(e => {
                trafficMultipliers[e.id] = parseFloat((1.0 + Math.random() * 2.0).toFixed(2));
            });
        }

        try {
            const response = await fetch('/api/find-path', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    nodes: nodes,
                    edges: edges,
                    algorithm: algo,
                    preference: pref,
                    start_node: resolvedStart,
                    end_node: resolvedEnd,
                    waypoints: Array.from(waypointIds),
                    traffic_multipliers: trafficMultipliers
                })
            });

            const data = await response.json();

            if (!response.ok) {
                statsPanel.innerHTML = `<p style="color: #ef4444;">❌ Error: ${data.detail || 'API Error'}</p>`;
                return;
            }

            const pathData = data.path_data;
            const pathFound = pathData.path_nodes.length > 0;
            const cost = pathData.total_cost;
            const pathStr = pathData.path_nodes.join(' → ');

            // Build stats card
            let statsHtml = `
                <div class="stat-row">
                    <span class="stat-label">Algorithm</span>
                    <span class="stat-value accent">${data.algorithm_label}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Status</span>
                    <span class="stat-value ${pathFound ? 'path-color' : ''}" style="${!pathFound ? 'color:#ef4444' : ''}">
                        ${pathFound ? '✅ Path Found' : '❌ No Path'}
                    </span>
                </div>
            `;

            if (pathFound) {
                statsHtml += `
                <div class="stat-row">
                    <span class="stat-label">Total Cost</span>
                    <span class="stat-value path-color">${cost >= 0 ? cost : '∞'}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Nodes Explored</span>
                    <span class="stat-value">${pathData.visited_order.length}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Path Length</span>
                    <span class="stat-value">${pathData.path_nodes.length} cities</span>
                </div>
                <div class="stat-row" style="flex-direction:column;align-items:flex-start;gap:4px;">
                    <span class="stat-label">Route</span>
                    <span class="path-nodes-list">${pathStr}</span>
                </div>
                `;
            }

            if (data.ai_reason) {
                statsHtml += `
                <div class="stat-row">
                    <span class="stat-label">AI Picked</span>
                    <span class="stat-value ai-color">${data.algorithm_label}</span>
                </div>
                <div class="ai-reason-box">🧠 ${data.ai_reason}</div>
                `;
            }

            statsPanel.innerHTML = statsHtml;

            // Kick off Phase 6 visualization
            if (pathFound) {
                runVisualization(
                    pathData.visited_order,
                    pathData.path_nodes,
                    pathData.path_edges
                );
            }

        } catch (error) {
            console.error("Failed to connect to backend:", error);
            statsPanel.innerHTML = `<p style="color: #ef4444;">❌ Failed to connect to backend. Is the server running?</p>`;
        }
    });

    document.getElementById('btn-clear').addEventListener('click', () => {
        nodes = [];
        edges = [];
        nextNodeId = 1;
        startNodeId = null;
        endNodeId = null;
        waypointIds = new Set();
        clearViz();
        draw();
        document.getElementById('stats-content').innerHTML = `<p class="placeholder">Waiting for map data...</p>`;
    });

    document.getElementById('btn-random').addEventListener('click', () => {
        nodes = [];
        edges = [];
        clearViz();
        document.getElementById('stats-content').innerHTML = `<p class="placeholder">Waiting for map data...</p>`;
        
        const numNodes = 12;
        const padding = 50;
        const width = canvas.width - padding * 2;
        const height = canvas.height - padding * 2;
        
        for (let i = 0; i < numNodes; i++) {
            nodes.push({
                id: i + 1,
                x: padding + Math.random() * width,
                y: padding + Math.random() * height
            });
        }
        nextNodeId = numNodes + 1;
        
        // Connect each node to 2-3 closest neighbors
        for (let i = 0; i < numNodes; i++) {
            const node = nodes[i];
            const distances = nodes.map(n => {
                const dx = n.x - node.x;
                const dy = n.y - node.y;
                return { id: n.id, dist: Math.sqrt(dx*dx + dy*dy) };
            }).filter(n => n.id !== node.id).sort((a, b) => a.dist - b.dist);
            
            const numEdges = 2 + Math.floor(Math.random() * 2);
            for (let j = 0; j < numEdges; j++) {
                const target = distances[j];
                const exists = edges.find(e => 
                    (e.from === node.id && e.to === target.id) ||
                    (e.from === target.id && e.to === node.id)
                );
                if (!exists) {
                    edges.push({
                        id: `${node.id}-${target.id}`,
                        from: node.id,
                        to: target.id,
                        weight: Math.max(1, Math.round(target.dist / 10))
                    });
                }
            }
        }
        
        startNodeId = nodes[0].id;
        endNodeId = nodes[nodes.length - 1].id;
        draw();
    });

    document.getElementById('btn-save').addEventListener('click', () => {
        const data = { nodes, edges, startNodeId, endNodeId, nextNodeId };
        localStorage.setItem('smartRouteMap', JSON.stringify(data));
        alert('Map saved successfully!');
    });

    document.getElementById('btn-load').addEventListener('click', () => {
        const dataStr = localStorage.getItem('smartRouteMap');
        if (dataStr) {
            try {
                const data = JSON.parse(dataStr);
                nodes = data.nodes || [];
                edges = data.edges || [];
                startNodeId = data.startNodeId || null;
                endNodeId = data.endNodeId || null;
                nextNodeId = data.nextNodeId || 1;
                clearViz();
                draw();
                document.getElementById('stats-content').innerHTML = `<p class="placeholder">Waiting for map data...</p>`;
            } catch (e) {
                alert('Failed to load map data.');
            }
        } else {
            alert('No saved map found.');
        }
    });

    // Initial draw
    draw();
});
