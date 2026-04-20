import { useMemo } from 'react';
import { computeLayout, edgePath, MAP_W, MAP_H, NODES, NODE_OFFSETS } from '../lib/constants.js';
import { utilColor, confColor, confToAlpha, interpStops, REDS, BLUES } from '../lib/colorscales.js';

const MISSING_COLOR = '#999';

export default function TopologyMap({
  data,           // AppData object
  t,              // current time index
  colorBy = 'util', // 'util' | 'conf'
  showConfidence = false, // true → opacity encodes confidence (Figure B mode)
  trustFilter = 0,        // minimum confidence to show normally
  selected = null,        // selected link i (1-based)
  hover = null,
  onLinkClick,
  onLinkHover,
  width = '100%',
  uMax,
}) {
  const { nodes, links, nLinks, nFrames, util, conf, isMissing } = data;

  const pos = useMemo(() => {
    // Build a nodes object with lat/lng for computeLayout
    const nodeMap = {};
    for (const n of nodes) nodeMap[n.id] = { lat: n.lat, lng: n.lng };
    return computeLayout(nodeMap, {}, MAP_W, MAP_H);
  }, [nodes]);

  const effectiveUMax = uMax || data.uMax || 0.32;
  const cLo = data.cLo || 0.6;
  const cHi = data.cHi || 1.0;

  const frame = useMemo(() => {
    const u = new Float32Array(nLinks);
    const c = new Float32Array(nLinks).fill(0.8);
    const m = new Uint8Array(nLinks);
    for (let l = 0; l < nLinks; l++) {
      const idx = t * nLinks + l;
      u[l] = isFinite(util[idx]) ? util[idx] : 0;
      if (conf && conf[idx] !== undefined) c[l] = conf[idx];
      if (isMissing && isMissing[idx]) m[l] = 1;
    }
    return { u, c, m };
  }, [util, conf, isMissing, t, nLinks]);

  const legendStops = colorBy === 'util' ? REDS : BLUES;

  return (
    <svg
      width={width}
      viewBox={`0 0 ${MAP_W} ${MAP_H}`}
      style={{ display: 'block', background: '#fafafa' }}
    >
      <defs>
        <marker id="arrow-sm" markerWidth="5" markerHeight="5"
          refX="4" refY="2.5" orient="auto">
          <path d="M0,0 L0,5 L5,2.5 Z" fill="#555" opacity="0.5" />
        </marker>
      </defs>

      {/* Links */}
      {links.map((lk, idx) => {
        const a = pos[lk.src];
        const b = pos[lk.dst];
        if (!a || !b) return null;

        const u = frame.u[idx];
        const c = frame.c[idx];
        const missing = frame.m[idx] === 1;

        const hidden = trustFilter > 0 && c < trustFilter;
        const forward = lk.src < lk.dst ? 1 : -1;
        const g = edgePath(a, b, 3.5 * forward);

        let stroke, opacity, dasharray;

        if (showConfidence && missing) {
          stroke   = MISSING_COLOR;
          opacity  = 0.5;
          dasharray = '4 3';
        } else {
          if (colorBy === 'util') {
            stroke = utilColor(u, effectiveUMax);
          } else {
            stroke = confColor(c, cLo, cHi);
          }
          opacity   = hidden ? 0.06 : (showConfidence ? confToAlpha(c, cLo, cHi) : 0.88);
          dasharray = '0';
        }

        const width = Math.max(1.2, 1.2 + (u / (effectiveUMax || 0.32)) * 5);
        const isSel = selected === lk.i;
        const isHov = hover === lk.i;

        return (
          <g key={lk.i}>
            <line
              x1={g.x1} y1={g.y1} x2={g.x2} y2={g.y2}
              stroke={stroke}
              strokeWidth={Math.min(width, 10)}
              opacity={opacity}
              strokeDasharray={dasharray}
              strokeLinecap="round"
            />
            {/* invisible hit target */}
            <line
              x1={g.x1} y1={g.y1} x2={g.x2} y2={g.y2}
              stroke="transparent" strokeWidth={13}
              style={{ cursor: 'pointer' }}
              onClick={() => onLinkClick?.(lk.i)}
              onMouseEnter={() => onLinkHover?.(lk.i)}
              onMouseLeave={() => onLinkHover?.(null)}
            />
            {(isSel || isHov) && (
              <line
                x1={g.x1} y1={g.y1} x2={g.x2} y2={g.y2}
                stroke="#000" strokeWidth={1.2} opacity={0.9}
                strokeDasharray={isSel ? '0' : '4 3'}
                pointerEvents="none"
              />
            )}
          </g>
        );
      })}

      {/* Nodes */}
      {nodes.map(n => {
        const p = pos[n.id];
        if (!p) return null;
        const label = n.id.replace('ng', '').replace('-M5', '·M5');
        return (
          <g key={n.id}>
            <circle cx={p.x} cy={p.y} r={4} fill="#fff" stroke="#333" strokeWidth={1.2} />
            <text x={p.x + 7} y={p.y - 5} fontSize={9.5} fontFamily="monospace" fill="#222">
              {label}
            </text>
          </g>
        );
      })}

      {/* Legend */}
      <g transform={`translate(${MAP_W - 176}, ${MAP_H - 58})`}>
        <rect x={-6} y={-14} width={176} height={56} fill="#fff" stroke="#ccc" strokeWidth={0.8} />
        <text x={0} y={0} fontSize={9.5} fontFamily="monospace" fill="#333">
          {colorBy === 'util' ? 'utilization' : 'confidence'}
        </text>
        {Array.from({ length: 24 }, (_, i) => {
          const f = i / 23;
          const [r, g, b] = interpStops(legendStops, f);
          return <rect key={i} x={i * 6} y={6} width={6} height={10}
                       fill={`rgb(${r|0},${g|0},${b|0})`} />;
        })}
        <text x={0} y={28} fontSize={8.5} fontFamily="monospace" fill="#444">
          {colorBy === 'util' ? '0' : (data.cLo || 0.6).toFixed(2)}
        </text>
        <text x={144} y={28} fontSize={8.5} fontFamily="monospace" fill="#444" textAnchor="end">
          {colorBy === 'util' ? `≥${effectiveUMax.toFixed(2)}` : (data.cHi || 1.0).toFixed(2)}
        </text>
        {showConfidence && (
          <text x={0} y={40} fontSize={8.5} fontFamily="monospace" fill="#888">
            opacity = confidence
          </text>
        )}
      </g>
    </svg>
  );
}
