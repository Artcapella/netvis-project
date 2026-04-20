import { useState, useMemo } from 'react';
import { formatTime, computeLayout, edgePath, MAP_W, MAP_H } from '../lib/constants.js';
import { utilColor, confToAlpha, interpStops, REDS } from '../lib/colorscales.js';

const mono  = '"Menlo","Consolas",monospace';
const MISSING_COLOR = '#999';

function TopologyPanel({ data, t, showConfidence, title }) {
  const { nodes, links, nLinks, util, conf, isMissing } = data;
  const uMax = data.uMax || 0.32;
  const cLo  = data.cLo  || 0.6;
  const cHi  = data.cHi  || 1.0;

  const pos = useMemo(() => {
    const nodeMap = {};
    for (const n of nodes) nodeMap[n.id] = { lat: n.lat, lng: n.lng };
    return computeLayout(nodeMap, {}, MAP_W, MAP_H);
  }, [nodes]);

  const frame = useMemo(() => {
    const u = new Float32Array(nLinks);
    const c = new Float32Array(nLinks).fill(0.85);
    const m = new Uint8Array(nLinks);
    for (let l = 0; l < nLinks; l++) {
      const idx = t * nLinks + l;
      u[l] = isFinite(util[idx]) ? util[idx] : 0;
      if (conf) c[l] = conf[idx] ?? 0.85;
      if (isMissing && isMissing[idx]) m[l] = 1;
    }
    return { u, c, m };
  }, [util, conf, isMissing, t, nLinks]);

  // Stats
  const maxUtil = Math.max(...frame.u);
  const meanConf = frame.c.reduce((a,b)=>a+b,0) / nLinks;
  const missingCount = Array.from(frame.m).filter(Boolean).length;

  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ fontSize: 12, fontWeight: 'bold', marginBottom: 4, fontFamily: mono }}>{title}</div>
      <svg width="100%" viewBox={`0 0 ${MAP_W} ${MAP_H}`}
           style={{ display: 'block', background: '#fafafa', border: '1px solid #ddd' }}>

        {links.map((lk, idx) => {
          const a = pos[lk.src], b = pos[lk.dst];
          if (!a || !b) return null;
          const u = frame.u[idx];
          const c = frame.c[idx];
          const missing = frame.m[idx] === 1;
          const forward = lk.src < lk.dst ? 1 : -1;
          const g = edgePath(a, b, 3.5 * forward);
          const width = Math.max(1, 1.2 + (u / (uMax || 0.32)) * 5.5);

          let stroke, opacity, dash;
          if (showConfidence && missing) {
            stroke = MISSING_COLOR; opacity = 0.55; dash = '5 3';
          } else {
            stroke  = utilColor(u, uMax);
            opacity = showConfidence ? confToAlpha(c, cLo, cHi) : 0.88;
            dash    = '0';
          }

          return (
            <g key={lk.i}>
              <line
                x1={g.x1} y1={g.y1} x2={g.x2} y2={g.y2}
                stroke={stroke} strokeWidth={Math.min(width, 10)}
                opacity={opacity} strokeDasharray={dash} strokeLinecap="round"
              />
            </g>
          );
        })}

        {nodes.map(n => {
          const p = pos[n.id];
          if (!p) return null;
          return (
            <g key={n.id}>
              <circle cx={p.x} cy={p.y} r={4} fill="#fff" stroke="#333" strokeWidth={1.2} />
              <text x={p.x+7} y={p.y-5} fontSize={9} fontFamily="monospace" fill="#222">
                {n.id.replace('ng','').replace('-M5','·M5')}
              </text>
            </g>
          );
        })}

        {/* Colorbar */}
        <g transform={`translate(${MAP_W-170}, ${MAP_H-46})`}>
          <rect x={-4} y={-12} width={168} height={44} fill="#fff" stroke="#ccc" strokeWidth={0.8}/>
          <text x={0} y={0} fontSize={9} fontFamily="monospace" fill="#444">utilization</text>
          {Array.from({length:24},(_,i)=>{
            const f=i/23;
            const [r,g,b]=interpStops(REDS,f);
            return <rect key={i} x={i*6} y={4} width={6} height={10} fill={`rgb(${r|0},${g|0},${b|0})`}/>;
          })}
          <text x={0}   y={26} fontSize={8} fontFamily="monospace" fill="#555">0</text>
          <text x={140} y={26} fontSize={8} fontFamily="monospace" fill="#555" textAnchor="end">≥{uMax.toFixed(2)}</text>
        </g>

        {/* Confidence legend */}
        {showConfidence && (
          <g transform={`translate(8, ${MAP_H-70})`}>
            <rect x={-4} y={-2} width={130} height={44} fill="#fff" stroke="#ccc" strokeWidth={0.8}/>
            <text x={0} y={10} fontSize={9} fontFamily="monospace" fill="#444">opacity = confidence</text>
            <line x1={0} y1={22} x2={40} y2={22} stroke="#a63603" strokeWidth={3} opacity={1.0}/>
            <text x={45} y={26} fontSize={8} fontFamily="monospace" fill="#444">high conf</text>
            <line x1={0} y1={34} x2={40} y2={34} stroke="#a63603" strokeWidth={3} opacity={0.2}/>
            <text x={45} y={38} fontSize={8} fontFamily="monospace" fill="#444">low conf</text>
          </g>
        )}
      </svg>
      <div style={{ fontSize: 11, color: '#666', marginTop: 4, fontFamily: mono }}>
        max util={maxUtil.toFixed(4)} &nbsp;|&nbsp;
        mean conf={meanConf.toFixed(3)} &nbsp;|&nbsp;
        missing={missingCount}/{nLinks}
      </div>
    </div>
  );
}

export default function TopologyCompareView({ data }) {
  const { nFrames, minPerFrame } = data;
  const [t, setT] = useState(() => {
    // Find most congested timestep
    let best = 0, bestVal = 0;
    for (let ti = 0; ti < nFrames; ti++) {
      for (let l = 0; l < data.nLinks; l++) {
        const v = data.util[ti * data.nLinks + l];
        if (isFinite(v) && v > bestVal) { bestVal = v; best = ti; }
      }
    }
    return best;
  });

  return (
    <div>
      {/* Timestep control */}
      <div style={{ border: '1px solid #ccc', padding: '8px 12px', background: '#fff', marginBottom: 10 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: '#555', textTransform: 'uppercase', letterSpacing: 0.5 }}>timestep</span>
          <input
            type="range" min={0} max={nFrames-1} value={t}
            onChange={e => setT(+e.target.value)}
            style={{ flex: 1 }}
          />
          <span style={{ fontFamily: mono, fontSize: 12, minWidth: 200 }}>
            t={String(t).padStart(4,'0')} / {nFrames-1} &nbsp; ({formatTime(t, minPerFrame)})
          </span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <TopologyPanel data={data} t={t} showConfidence={false}
          title="Figure A — Congestion only (uniform opacity, no confidence info)" />
        <TopologyPanel data={data} t={t} showConfidence={true}
          title="Figure B — Confidence-aware (opacity = data quality; dashed = missing)" />
      </div>

      <div style={{ fontSize: 11, color: '#666', marginTop: 10, padding: '8px 10px', background: '#f9f9f9', border: '1px solid #e0e0e0' }}>
        <strong>Reading Figure B:</strong> Links with full opacity have high measurement confidence.
        Faded links carry uncertain or noisy data — congestion shown there may not reflect ground truth.
        Dashed gray lines indicate timesteps where telemetry was completely missing.
        {!data.hasFullTelemetry && (
          <span style={{ color: '#a66a00' }}> &nbsp; Note: confidence information is limited in the default dataset.
          Upload a <code>telemetry_final.csv</code> for full missing-data markers.</span>
        )}
      </div>
    </div>
  );
}
