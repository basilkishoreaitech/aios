/**
 * Renders the Dynamic SVG Dependency Graph.
 */
import apiFetch from '../utils/api.js';

const NODE_POSITIONS = {
  "api-gateway": { x: 200, y: 30 },
  "auth-service": { x: 70, y: 120 },
  "payment-service": { x: 200, y: 120 },
  "order-service": { x: 330, y: 120 },
  "recommendation-engine": { x: 460, y: 120 },
  "inventory-service": { x: 330, y: 210 },
  "db-service": { x: 200, y: 300 }
};

const DependencyGraph = {
  async draw(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = `<div style="font-size:0.8rem; color:var(--text-muted); text-align:center;">Drawing service topology map...</div>`;

    try {
      const data = await apiFetch('/topology');
      const nodes = data.nodes || [];
      const links = data.links || [];

      // Create SVG structure
      let svgHtml = `
        <svg width="100%" height="220" viewBox="0 0 530 340" style="background:rgba(10, 15, 30, 0.8); border:1px solid var(--border-color); border-radius: var(--radius-sm);">
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="18" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 1 L 10 5 L 0 9 z" fill="var(--text-muted)" />
            </marker>
          </defs>
      `;

      // 1. Draw Links
      links.forEach(link => {
        const sourcePos = NODE_POSITIONS[link.source] || { x: 50, y: 50 };
        const targetPos = NODE_POSITIONS[link.target] || { x: 100, y: 100 };
        
        // Check if either end of the link is unhealthy or in blast radius
        const sourceNode = nodes.find(n => n.id === link.source);
        const targetNode = nodes.find(n => n.id === link.target);
        
        let strokeColor = link.is_critical ? 'var(--text-muted)' : '#cbd5e1';
        let strokeWidth = 1.5;
        
        if (sourceNode && targetNode) {
          const isSourceAffected = sourceNode.status !== 'healthy';
          const isTargetAffected = targetNode.status !== 'healthy';
          if (isSourceAffected && isTargetAffected) {
            strokeColor = 'var(--danger)';
            strokeWidth = 2;
          } else if (isSourceAffected || isTargetAffected) {
            strokeColor = '#f97316'; // Coral warning color for blast path
            strokeWidth = 1.8;
          }
        }
        
        const strokeDash = link.relationship_type === 'grpc' ? 'stroke-dasharray="4"' : '';
        
        svgHtml += `
          <line x1="${sourcePos.x}" y1="${sourcePos.y}" x2="${targetPos.x}" y2="${targetPos.y}" 
                stroke="${strokeColor}" stroke-width="${strokeWidth}" ${strokeDash} marker-end="url(#arrow)" />
        `;
      });

      // 2. Draw Nodes
      nodes.forEach(node => {
        const pos = NODE_POSITIONS[node.id] || { x: 50, y: 50 };
        let nodeColor = 'var(--success)';
        let textColor = '#ffffff';
        let isBlastRadius = false;
        
        if (node.status === 'down') {
          nodeColor = 'var(--danger)';
        } else if (node.status === 'degraded') {
          nodeColor = 'var(--warning)';
        } else if (node.status === 'blast_radius') {
          nodeColor = '#f97316'; // Coral warning color for blast radius
          isBlastRadius = true;
        }

        svgHtml += `
          <g style="cursor: pointer;" title="Service: ${node.id} (${node.status.replace('_', ' ')})">
            <circle cx="${pos.x}" cy="${pos.y}" r="14" fill="${nodeColor}" stroke="#ffffff" stroke-width="2" />
            ${isBlastRadius ? `
              <circle cx="${pos.x}" cy="${pos.y}" r="18" fill="none" stroke="#f97316" stroke-width="1.5" stroke-dasharray="3" />
            ` : ''}
            <text x="${pos.x}" y="${pos.y + 4}" fill="${textColor}" font-size="8" font-weight="700" text-anchor="middle">
              ${node.id[0].toUpperCase()}
            </text>
            <text x="${pos.x}" y="${pos.y + 24}" fill="var(--text-primary)" font-size="8" font-weight="600" text-anchor="middle">
              ${node.id}
            </text>
          </g>
        `;
      });

      svgHtml += `</svg>`;
      container.innerHTML = svgHtml;
    } catch (e) {
      container.innerHTML = `<div style="font-size:0.8rem; color:var(--danger); text-align:center;">Topology map failed: ${e.message}</div>`;
    }
  }
};

export default DependencyGraph;
