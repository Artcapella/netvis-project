import { useState, useMemo, useRef } from 'react';

const mono  = '"Menlo","Consolas",monospace';
const BAND_SCALE = 0.15;

function LinkChart({ data, linkIdx, W = 720, H = 140, timeWindow }) {
  const { nFrames, nLinks, util, conf, isMissing, staleness, minPerFrame } = data;
  const lk = data.links[linkIdx];
  if (!lk) return null;

  const start = 0;
  const end   = Math.min(nFrames, start + timeWindow);
  const n     = end - start;

  const u = new Float32Array(n);
  const c = new Float32Array(n).fill(0.85);
  const mis = new Uint8Array(n);
  const sta = new Uint8Array(n);

  for (let i = 0; i < n; i++) {
    const idx = (start + i) * nLinks + linkIdx;
    u[i]   = util[idx];
    if (conf)      c[i]   = conf[idx]      ?? 0.85;
    if (isMissing) mis[i] = isMissing[idx] ?? 0;
    if (staleness) sta[i] = staleness[idx] ?? 0;
  }

  const uMax = data.uMax || 0.32;
  const pTop = 16, pBottom = 30, pLeft = 42, pRight = 8;
  const plotW = W - pLeft - pRight;
  const plotH = H - pTop - pBottom;

  const xOf = (i) => pLeft + (i / (n - 1)) * plotW;
  const yOf = (v) => isFinite(v) ? pTop + (1 - Math.min(v, uMax * 1.2) / (uMax * 1.2)) * plotH : null;

  // Confidence band
  const bandPaths = [];
  let bandUpper = [], bandLower = [], bandInGap = false;
  const flushBand = () => {
    if (bandUpper.length > 1) {
      const up = bandUpper.map(([x,y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L');
      const lo = [...bandLower].reverse().map(([x,y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L');
      bandPaths.push(`M ${up} L ${lo} Z`);
    }
    bandUpper = []; bandLower = [];
  };

  for (let i = 0; i < n; i++) {
    if (!isFinite(u[i])) { flushBand(); bandInGap = true; continue; }
    const bw = BAND_SCALE * (1 - c[i]);
    const yu = yOf(u[i] + bw);
    const yl = yOf(Math.max(0, u[i] - bw));
    const x  = xOf(i);
    if (yu !== null && yl !== null) {
      bandUpper.push([x, yu]);
      bandLower.push([x, yl]);
    }
    bandInGap = false;
  }
  flushBand();

  // Utilization path (break on NaN)
  let utilPath = '', penDown = false;
  for (let i = 0; i < n; i++) {
    const y = yOf(u[i]);
    if (y === null) { penDown = false; continue; }
    const x = xOf(i);
    utilPath += penDown ? ` L${x.toFixed(1)},${y.toFixed(1)}` : ` M${x.toFixed(1)},${y.toFixed(1)}`;
    penDown = true;
  }

  // Ref lines
  const yRef80 = yOf(0.8 * uMax);
  const yRef100 = yOf(uMax);

  // Missing markers
  const missingXs = [];
  for (let i = 0; i < n; i++) if (mis[i]) missingXs.push(xOf(i));

  // Stale markers
  const stalePoints = [];
  for (let i = 0; i < n; i++) if (sta[i] && isFinite(u[i])) stalePoints.push([xOf(i), yOf(u[i])]);

  // X-axis ticks (every ~100 frames or Day boundary)
  const tickEvery = Math.max(1, Math.round(n / 7));
  const ticks = [];
  for (let i = 0; i < n; i += tickEvery) {
    const mins = (start + i) * minPerFrame;
    const day  = Math.floor(mins / (24*60)) + 1;
    const hh   = Math.floor((mins % (24*60)) / 60);
    ticks.push({ x: xOf(i), label: `D${day} ${String(hh).padStart(2,'0')}:00` });
  }

  // Y-axis ticks
  const yTicks = [0, 0.25, 0.5, 0.75, 1.0].map(f => ({
    y: yOf(f * uMax),
    label: (f * uMax).toFixed(2),
  }));

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 11, fontFamily: mono, color: '#333', marginBottom: 2 }}>
        link {lk.i}: {lk.src} → {lk.dst}
        <span style={{ color: '#888', marginLeft: 10 }}>
          mean={(Array.from(u).filter(isFinite).reduce((a,b)=>a+b,0)/Math.max(1,n)).toFixed(5)} max={(Math.max(0,...Array.from(u).filter(isFinite))).toFixed(5)}
        </span>
      </div>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block', background: '#fff', border: '1px solid #e0e0e0' }}>
        {/* Background */}
        <rect x={pLeft} y={pTop} width={plotW} height={plotH} fill="#fafafa" />

        {/* Ref lines */}
        {isFinite(yRef100) && yRef100 >= pTop && yRef100 <= pTop + plotH && (
          <line x1={pLeft} x2={pLeft+plotW} y1={yRef100} y2={yRef100}
                stroke="#e74c3c" strokeDasharray="3 3" strokeWidth={0.8} opacity={0.6}/>
        )}
        {isFinite(yRef80) && yRef80 >= pTop && yRef80 <= pTop + plotH && (
          <line x1={pLeft} x2={pLeft+plotW} y1={yRef80} y2={yRef80}
                stroke="#f39c12" strokeDasharray="3 3" strokeWidth={0.8} opacity={0.5}/>
        )}

        {/* Confidence band */}
        {bandPaths.map((d,i) => (
          <path key={i} d={d} fill="#3498db" opacity={0.18} />
        ))}

        {/* Utilization line */}
        <path d={utilPath} fill="none" stroke="#2c3e50" strokeWidth={1.2} />

        {/* Missing markers */}
        {missingXs.map((x,i) => (
          <g key={i}>
            <line x1={x-3} y1={pTop+plotH-4} x2={x+3} y2={pTop+plotH+4} stroke="#e74c3c" strokeWidth={1.2}/>
            <line x1={x+3} y1={pTop+plotH-4} x2={x-3} y2={pTop+plotH+4} stroke="#e74c3c" strokeWidth={1.2}/>
          </g>
        ))}

        {/* Stale markers */}
        {stalePoints.map(([x,y],i) => (
          <circle key={i} cx={x} cy={y} r={2.5} fill="#e67e22" opacity={0.7}/>
        ))}

        {/* Y-axis */}
        {yTicks.map(({ y, label }) => y !== null && (
          <g key={label}>
            <line x1={pLeft-4} x2={pLeft} y1={y} y2={y} stroke="#999" strokeWidth={0.8}/>
            <text x={pLeft-6} y={y+4} fontSize={8} fontFamily="monospace" fill="#666" textAnchor="end">{label}</text>
          </g>
        ))}
        <line x1={pLeft} y1={pTop} x2={pLeft} y2={pTop+plotH} stroke="#999" strokeWidth={0.8}/>

        {/* X-axis */}
        <line x1={pLeft} y1={pTop+plotH} x2={pLeft+plotW} y2={pTop+plotH} stroke="#999" strokeWidth={0.8}/>
        {ticks.map(({ x, label }) => (
          <g key={label}>
            <line x1={x} y1={pTop+plotH} x2={x} y2={pTop+plotH+4} stroke="#999" strokeWidth={0.8}/>
            <text x={x} y={pTop+plotH+13} fontSize={8} fontFamily="monospace" fill="#666" textAnchor="middle">{label}</text>
          </g>
        ))}

        {/* Labels */}
        <text x={pLeft-35} y={pTop+plotH/2} fontSize={9} fontFamily="monospace" fill="#555"
              transform={`rotate(-90, ${pLeft-35}, ${pTop+plotH/2})`} textAnchor="middle">util</text>

        {/* Legend */}
        <g transform={`translate(${pLeft+8},${pTop+6})`}>
          <rect x={-2} y={-2} width={200} height={14} fill="#fff" opacity={0.8}/>
          <line x1={0} y1={5} x2={20} y2={5} stroke="#2c3e50" strokeWidth={1.2}/>
          <text x={24} y={9} fontSize={8} fontFamily="monospace" fill="#333">utilization</text>
          <rect x={56} y={1} width={20} height={8} fill="#3498db" opacity={0.25}/>
          <text x={80} y={9} fontSize={8} fontFamily="monospace" fill="#333">conf band</text>
          <circle cx={118} cy={5} r={2.5} fill="#e67e22" opacity={0.7}/>
          <text x={124} y={9} fontSize={8} fontFamily="monospace" fill="#333">stale</text>
          <line x1={152} y1={2} x2={156} y2={8} stroke="#e74c3c" strokeWidth={1.2}/>
          <line x1={156} y1={2} x2={152} y2={8} stroke="#e74c3c" strokeWidth={1.2}/>
          <text x={160} y={9} fontSize={8} fontFamily="monospace" fill="#333">missing</text>
        </g>
      </svg>
    </div>
  );
}

export default function TimeSeriesView({ data }) {
  const { links, nFrames, nLinks, util } = data;

  // Find top-N links by mean utilization
  const topLinks = useMemo(() => {
    return links
      .map((lk, idx) => {
        let sum = 0, cnt = 0;
        for (let t = 0; t < nFrames; t++) {
          const v = util[t * nLinks + idx];
          if (isFinite(v)) { sum += v; cnt++; }
        }
        return { i: lk.i, idx, mean: cnt ? sum/cnt : 0 };
      })
      .sort((a,b) => b.mean - a.mean)
      .slice(0, 5)
      .map(x => x.idx);
  }, [links, nFrames, nLinks, util]);

  // Reset selection when topLinks change (new data uploaded)
  const [selected, setSelected] = useState(topLinks.slice(0, 3));
  const prevTopRef = useRef(topLinks);
  if (prevTopRef.current !== topLinks) {
    prevTopRef.current = topLinks;
    // Can't call setSelected here in render; parent re-mounts this component when data changes
  }
  const [timeWindow, setTimeWindow] = useState(Math.min(500, nFrames));

  const toggleLink = (idx) => {
    setSelected(prev =>
      prev.includes(idx) ? prev.filter(x => x !== idx) : [...prev, idx].slice(0, 5)
    );
  };

  return (
    <div>
      {/* Controls */}
      <div style={{ border: '1px solid #ccc', padding: '10px 12px', background: '#fff', marginBottom: 10 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 11, color: '#555', marginBottom: 6 }}>SELECT LINKS (up to 5)</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {topLinks.map(idx => {
                const lk = links[idx];
                const active = selected.includes(idx);
                return (
                  <button key={idx}
                    onClick={() => toggleLink(idx)}
                    style={{
                      border: '1px solid #666',
                      background: active ? '#111' : '#fff',
                      color: active ? '#fff' : '#111',
                      padding: '2px 8px', fontSize: 11,
                      fontFamily: mono, cursor: 'pointer',
                    }}>
                    {lk.src}→{lk.dst}
                  </button>
                );
              })}
              {links.filter((_,i) => !topLinks.includes(i)).map((lk, i) => {
                const idx = links.indexOf(lk);
                const active = selected.includes(idx);
                if (!active) return null;
                return (
                  <button key={idx}
                    onClick={() => toggleLink(idx)}
                    style={{ border: '1px solid #666', background: '#111', color: '#fff',
                             padding: '2px 8px', fontSize: 11, fontFamily: mono, cursor: 'pointer' }}>
                    {lk.src}→{lk.dst}
                  </button>
                );
              })}
            </div>
          </div>
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={{ fontSize: 11, color: '#555', marginBottom: 6 }}>
              TIME WINDOW: {timeWindow} frames ({Math.round(timeWindow * data.minPerFrame / 60)}h)
            </div>
            <input
              type="range" min={50} max={nFrames} step={50} value={timeWindow}
              onChange={e => setTimeWindow(+e.target.value)}
              style={{ width: '100%' }}
            />
          </div>
        </div>
        <div style={{ fontSize: 11, color: '#666', marginTop: 8 }}>
          Confidence band width: narrower = higher confidence. Red ✕ = missing data. Orange dot = stale/repeated measurement.
          Reference lines: orange = 80% capacity, red = 100% capacity.
        </div>
      </div>

      {/* Charts */}
      {selected.length === 0 ? (
        <div style={{ padding: 24, color: '#777', textAlign: 'center' }}>
          Select at least one link above to plot its time series.
        </div>
      ) : (
        selected.map(idx => (
          <LinkChart key={idx} data={data} linkIdx={idx} timeWindow={timeWindow} />
        ))
      )}
    </div>
  );
}
