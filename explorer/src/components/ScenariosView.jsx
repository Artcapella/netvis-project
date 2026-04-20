import { useMemo } from 'react';
import { formatTime, computeLayout, edgePath, MAP_W, MAP_H } from '../lib/constants.js';
import { utilColor, confToAlpha } from '../lib/colorscales.js';

const mono = '"Menlo","Consolas",monospace';
const WINDOW = 100;

const SCENARIO_DEFS = [
  {
    id: 1,
    name: 'Clean Congestion Spike',
    desc: 'High utilization combined with high confidence — genuine congestion, trustworthy data.',
    color: '#c0392b',
    score: ({ meanUtil, meanConf, missingRate }) =>
      meanUtil > 0.3 && meanConf > 0.7
        ? meanUtil * meanConf * (1 - missingRate * 2)
        : -1,
  },
  {
    id: 2,
    name: 'Noisy Hotspot',
    desc: 'High utilization with low confidence — apparent congestion may be measurement artifact.',
    color: '#8e44ad',
    score: ({ meanUtil, meanConf, missingRate }) =>
      meanUtil > 0.15
        ? meanUtil * (1 - meanConf)
        : -1,
  },
  {
    id: 3,
    name: 'Missing Data Gap',
    desc: 'High missingness rate — significant portion of telemetry absent from this window.',
    color: '#2980b9',
    score: ({ missingRate }) => missingRate,
  },
  {
    id: 4,
    name: 'Stable Healthy Link',
    desc: 'Low utilization with high confidence — link is well below capacity with reliable measurements.',
    color: '#27ae60',
    score: ({ meanUtil, meanConf, missingRate }) =>
      meanUtil < 0.1 && meanConf > 0.7
        ? (1 - meanUtil) * meanConf * (1 - missingRate)
        : -1,
  },
];

function detectScenarios(data) {
  const { nFrames, nLinks, links, util, conf, isMissing } = data;
  const results = [];

  for (const def of SCENARIO_DEFS) {
    let bestScore = -Infinity, bestT = 0, bestLink = 0;

    for (let l = 0; l < nLinks; l++) {
      for (let tStart = 0; tStart + WINDOW <= nFrames; tStart += Math.max(1, Math.floor(WINDOW / 2))) {
        let sumUtil = 0, sumConf = 0, missingCnt = 0, validCnt = 0;
        for (let di = 0; di < WINDOW; di++) {
          const idx = (tStart + di) * nLinks + l;
          const u   = util[idx];
          const c   = conf ? conf[idx] : 0.85;
          const m   = isMissing ? isMissing[idx] : 0;
          if (m) { missingCnt++; } else if (isFinite(u)) {
            sumUtil += u; sumConf += c ?? 0.85; validCnt++;
          }
        }
        const total = WINDOW;
        const meanUtil    = validCnt ? sumUtil / validCnt : 0;
        const meanConf    = validCnt ? sumConf / validCnt : 0.85;
        const missingRate = missingCnt / total;
        const s = def.score({ meanUtil, meanConf, missingRate });
        if (s > bestScore) { bestScore = s; bestT = tStart; bestLink = l; }
      }
    }

    results.push({
      ...def,
      tStart:   bestT,
      linkIdx:  bestLink,
      score:    bestScore,
    });
  }
  return results;
}

function MiniTopology({ data, t }) {
  const { nodes, links, nLinks, util, conf } = data;
  const W = 300, H = 180;
  const uMax = data.uMax || 0.32;
  const cLo  = data.cLo  || 0.6;
  const cHi  = data.cHi  || 1.0;

  const pos = useMemo(() => {
    const nm = {};
    for (const n of nodes) nm[n.id] = { lat: n.lat, lng: n.lng };
    return computeLayout(nm, {}, W, H, 22);
  }, [nodes]);

  const frame = useMemo(() => {
    const u = new Float32Array(nLinks);
    const c = new Float32Array(nLinks).fill(0.85);
    for (let l = 0; l < nLinks; l++) {
      const idx = t * nLinks + l;
      u[l] = isFinite(util[idx]) ? util[idx] : 0;
      if (conf && conf[idx] !== undefined) c[l] = conf[idx];
    }
    return { u, c };
  }, [util, conf, t, nLinks]);

  return (
    <svg width={W} height={H} style={{ display: 'block', background: '#fafafa', border: '1px solid #e0e0e0' }}>
      {links.map((lk, idx) => {
        const a = pos[lk.src], b = pos[lk.dst];
        if (!a || !b) return null;
        const u = frame.u[idx];
        const c = frame.c[idx];
        const fwd = lk.src < lk.dst ? 1 : -1;
        const g = edgePath(a, b, 2.5 * fwd);
        return (
          <line key={lk.i}
            x1={g.x1} y1={g.y1} x2={g.x2} y2={g.y2}
            stroke={utilColor(u, uMax)}
            strokeWidth={Math.max(0.8, 0.8 + (u / (uMax||0.32)) * 4)}
            opacity={confToAlpha(c, cLo, cHi)}
            strokeLinecap="round"
          />
        );
      })}
      {nodes.map(n => {
        const p = pos[n.id];
        if (!p) return null;
        return (
          <g key={n.id}>
            <circle cx={p.x} cy={p.y} r={2.5} fill="#fff" stroke="#444" strokeWidth={0.8}/>
          </g>
        );
      })}
    </svg>
  );
}

function MiniTimeSeries({ data, linkIdx, tStart, W = 300, H = 80 }) {
  const { nFrames, nLinks, util, conf, isMissing } = data;
  const end = Math.min(nFrames, tStart + WINDOW);
  const n   = end - tStart;
  const uMax = (data.uMax || 0.32) * 1.2;
  const pL = 8, pR = 4, pT = 8, pB = 8;
  const pw = W - pL - pR, ph = H - pT - pB;

  const xOf = (i) => pL + (i / (n - 1)) * pw;
  const yOf = (v) => isFinite(v) ? pT + (1 - Math.min(v, uMax) / uMax) * ph : null;

  let utilPath = '', penDown = false;
  const bandParts = [];
  let bu = [], bl = [];

  const flushBand = () => {
    if (bu.length > 1) {
      const up = bu.map(([x,y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L');
      const lo = [...bl].reverse().map(([x,y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L');
      bandParts.push(`M ${up} L ${lo} Z`);
    }
    bu = []; bl = [];
  };

  for (let i = 0; i < n; i++) {
    const idx = (tStart + i) * nLinks + linkIdx;
    const u   = util[idx];
    const c   = conf ? (conf[idx] ?? 0.85) : 0.85;
    const y   = yOf(u);
    const x   = xOf(i);
    if (y === null) { penDown = false; flushBand(); continue; }
    utilPath += penDown ? ` L${x.toFixed(1)},${y.toFixed(1)}` : ` M${x.toFixed(1)},${y.toFixed(1)}`;
    penDown = true;
    const bw = 0.10 * (1 - c);
    const yu = yOf(u + bw), yl = yOf(Math.max(0, u - bw));
    if (yu !== null && yl !== null) { bu.push([x,yu]); bl.push([x,yl]); }
  }
  flushBand();

  return (
    <svg width={W} height={H} style={{ display: 'block', background: '#fff', border: '1px solid #e0e0e0' }}>
      <rect x={pL} y={pT} width={pw} height={ph} fill="#fafafa"/>
      {bandParts.map((d,i) => <path key={i} d={d} fill="#3498db" opacity={0.2}/>)}
      <path d={utilPath} fill="none" stroke="#2c3e50" strokeWidth={1.2}/>
    </svg>
  );
}

export default function ScenariosView({ data }) {
  const scenarios = useMemo(() => detectScenarios(data), [data]);

  return (
    <div>
      <div style={{ fontSize: 12, color: '#555', marginBottom: 12, padding: '8px 10px', background: '#f9f9f9', border: '1px solid #e0e0e0' }}>
        The four canonical scenarios used in the evaluation framework. Each is auto-detected via a sliding window
        ({WINDOW} frames) search across all links — finding the most representative example in the dataset.
        Topology opacity encodes confidence (Figure B mode).
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        {scenarios.map(sc => {
          const lk = data.links[sc.linkIdx];
          const tMid = sc.tStart + Math.floor(WINDOW / 2);
          const stats = (() => {
            let su=0, sc2=0, mc=0, vc=0;
            for (let di=0; di<WINDOW; di++) {
              const idx = (sc.tStart+di)*data.nLinks+sc.linkIdx;
              const u=data.util[idx], c=data.conf?data.conf[idx]:0.85, m=data.isMissing?data.isMissing[idx]:0;
              if (m) mc++; else if(isFinite(u)){su+=u;sc2+=c;vc++;}
            }
            return { meanUtil:vc?su/vc:0, meanConf:vc?sc2/vc:0.85, missingPct:mc/WINDOW*100 };
          })();

          return (
            <div key={sc.id} style={{ border: '1px solid #ccc', padding: 12, background: '#fff' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span style={{
                  background: sc.color, color: '#fff',
                  padding: '1px 9px', fontSize: 11, fontWeight: 'bold',
                }}>
                  Scenario {sc.id}
                </span>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{sc.name}</span>
              </div>
              <p style={{ fontSize: 12, color: '#555', margin: '0 0 10px', lineHeight: 1.5 }}>{sc.desc}</p>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
                <div>
                  <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>
                    Topology at t={tMid} ({formatTime(tMid, data.minPerFrame)})
                  </div>
                  <MiniTopology data={data} t={tMid} />
                </div>
                <div>
                  <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>
                    {lk ? `${lk.src} → ${lk.dst}` : 'best link'} — {WINDOW} frames
                  </div>
                  <MiniTimeSeries data={data} linkIdx={sc.linkIdx} tStart={sc.tStart} />
                </div>
              </div>

              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11, fontFamily: mono }}>
                <tbody>
                  {[
                    ['Window start', `t=${sc.tStart} (${formatTime(sc.tStart, data.minPerFrame)})`],
                    ['Best link',    lk ? `#${lk.i} ${lk.src} → ${lk.dst}` : '—'],
                    ['Mean util',    stats.meanUtil.toFixed(5)],
                    ['Mean conf',    stats.meanConf.toFixed(3)],
                    ['Missing',      `${stats.missingPct.toFixed(1)}%`],
                  ].map(([k,v]) => (
                    <tr key={k}>
                      <td style={{ padding:'2px 6px', color:'#666' }}>{k}</td>
                      <td style={{ padding:'2px 6px', color:'#111' }}>{v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>
    </div>
  );
}
