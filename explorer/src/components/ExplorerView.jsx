import { useState, useEffect, useMemo, useRef } from 'react';
import TopologyMap from './TopologyMap.jsx';
import Sparkline from './Sparkline.jsx';
import { formatTime, LINK_CLASS_COLOR } from '../lib/constants.js';

const font  = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
const mono  = '"Menlo","Consolas",monospace';

const S = {
  panel:   { border: '1px solid #ccc', padding: 10, background: '#fff' },
  row:     { display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' },
  label:   { fontSize: 10, color: '#555', textTransform: 'uppercase', letterSpacing: 0.5 },
  btn:     (active) => ({
    border: '1px solid #666', background: active ? '#111' : '#fff',
    color: active ? '#fff' : '#111', padding: '2px 10px', fontSize: 12, fontFamily: font, cursor: 'pointer',
  }),
  num:     { fontFamily: mono, fontSize: 12 },
  table:   { fontFamily: mono, fontSize: 12, borderCollapse: 'collapse', width: '100%' },
  td:      { border: '1px solid #ddd', padding: '3px 6px' },
  th:      { border: '1px solid #999', padding: '3px 6px', background: '#f0f0f0', textAlign: 'left', fontWeight: 'bold' },
};

export default function ExplorerView({ data }) {
  const { links, nFrames, nLinks, minPerFrame, util, conf } = data;

  const [t, setT]           = useState(() => Math.min(432, nFrames - 1));
  const [trust, setTrust]   = useState(0);
  const [colorBy, setColorBy] = useState('util');
  const [selected, setSelected] = useState(19); // KSCY→IPLS default
  const [playing, setPlaying]  = useState(false);
  const [hover, setHover]      = useState(null);
  const playRef                = useRef(null);

  // Clamp t if data changes
  useEffect(() => { if (t >= nFrames) setT(0); }, [nFrames]);

  // Animation loop
  useEffect(() => {
    if (!playing) return;
    playRef.current = setInterval(() => setT(prev => (prev + 1) % nFrames), 160);
    return () => clearInterval(playRef.current);
  }, [playing, nFrames]);

  // Current frame util/conf
  const frame = useMemo(() => {
    const u = new Float32Array(nLinks);
    const c = new Float32Array(nLinks).fill(data.cLo || 0.6);
    for (let l = 0; l < nLinks; l++) {
      const idx = t * nLinks + l;
      u[l] = isFinite(util[idx]) ? util[idx] : 0;
      if (conf && conf[idx] !== undefined) c[l] = conf[idx];
    }
    return { u, c };
  }, [util, conf, t, nLinks]);

  // Top-5 rankings
  const ranks = useMemo(() => {
    const entries = links.map((lk, idx) => ({ i: lk.i, idx, u: frame.u[idx], c: frame.c[idx] }));
    const naive    = [...entries].sort((a,b) => b.u - a.u).slice(0, 5);
    const filtered = entries.filter(e => e.c >= trust).sort((a,b) => b.u - a.u).slice(0, 5);
    const naiveSet    = new Set(naive.map(x => x.i));
    const filteredSet = new Set(filtered.map(x => x.i));
    return {
      naive,
      filtered,
      droppedFromNaive: naive.filter(x => !filteredSet.has(x.i)),
      addedByFilter:    filtered.filter(x => !naiveSet.has(x.i)),
    };
  }, [frame, trust, links]);

  // Time series for selected link
  const series = useMemo(() => {
    if (selected == null) return null;
    const lk = links.find(l => l.i === selected);
    if (!lk) return null;
    const idx = lk.i - 1;
    const u = new Float32Array(nFrames);
    const c = new Float32Array(nFrames);
    for (let i = 0; i < nFrames; i++) {
      const k = i * nLinks + idx;
      u[i] = isFinite(util[k]) ? util[k] : 0;
      if (conf && conf[k] !== undefined) c[i] = conf[k];
    }
    return { lk, u, c };
  }, [selected, links, nFrames, nLinks, util, conf]);

  const frameStats = useMemo(() => {
    let mx = 0, mxIdx = 0, mn = 1e9, mnIdx = 0;
    for (let l = 0; l < nLinks; l++) {
      if (frame.u[l] > mx) { mx = frame.u[l]; mxIdx = l; }
      if (frame.u[l] < mn) { mn = frame.u[l]; mnIdx = l; }
    }
    return { mx, mxIdx, mn, mnIdx };
  }, [frame]);

  const uMax = data.uMax || 0.32;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Controls */}
      <div style={{ ...S.panel }}>
        <div style={{ ...S.row, marginBottom: 8 }}>
          <span style={S.label}>time</span>
          <input
            type="range" min={0} max={nFrames - 1} value={t}
            onChange={e => setT(+e.target.value)}
            style={{ flex: 1, minWidth: 240 }}
          />
          <span style={{ ...S.num, minWidth: 220 }}>
            t={String(t).padStart(4,'0')}/{nFrames-1} &nbsp;({formatTime(t, minPerFrame)})
          </span>
          <button style={S.btn(playing)} onClick={() => setPlaying(p => !p)}>
            {playing ? '⏸ pause' : '▶ play'}
          </button>
          <button style={S.btn(false)} onClick={() => { setT(0); setPlaying(false); }}>reset</button>
        </div>

        <div style={{ ...S.row, marginBottom: 8 }}>
          <span style={S.label}>confidence filter</span>
          <input
            type="range" min={0} max={1} step={0.01} value={trust}
            onChange={e => setTrust(+e.target.value)}
            style={{ flex: 1, minWidth: 240 }}
          />
          <span style={{ ...S.num, minWidth: 80 }}>
            {trust === 0 ? 'off' : `c≥${trust.toFixed(2)}`}
          </span>
          <span style={{ fontSize: 11, color: '#666', flex: 1 }}>
            de-emphasises low-confidence links; excludes them from filtered ranking
          </span>
        </div>

        <div style={S.row}>
          <span style={S.label}>color by</span>
          <button style={S.btn(colorBy === 'util')} onClick={() => setColorBy('util')}>utilization</button>
          <button style={S.btn(colorBy === 'conf')} onClick={() => setColorBy('conf')}>confidence</button>
        </div>
      </div>

      {/* Main split: topology | detail */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 380px', gap: 10 }}>
        {/* Topology */}
        <div style={S.panel}>
          <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>
            topology — click an edge to inspect
          </div>
          <TopologyMap
            data={data} t={t}
            colorBy={colorBy}
            showConfidence={false}
            trustFilter={trust}
            selected={selected}
            hover={hover}
            onLinkClick={setSelected}
            onLinkHover={setHover}
            uMax={uMax}
          />
          <div style={{ fontSize: 11, color: '#666', marginTop: 4, fontFamily: mono }}>
            {links[frameStats.mxIdx] && (
              <>peak: link {links[frameStats.mxIdx].i} &nbsp;
              ({links[frameStats.mxIdx].src} → {links[frameStats.mxIdx].dst})
              &nbsp; util={frameStats.mx.toFixed(5)}</>
            )}
          </div>
        </div>

        {/* Detail panel */}
        <div style={S.panel}>
          {!series ? (
            <div style={{ fontSize: 12, color: '#777' }}>No link selected — click an edge on the map.</div>
          ) : (
            <>
              <div style={{ fontSize: 11, color: '#666' }}>selected link</div>
              <div style={{ fontFamily: mono, fontSize: 14, marginBottom: 2 }}>
                #{series.lk.i} &nbsp; {series.lk.src} → {series.lk.dst}
              </div>
              <div style={{ fontSize: 11, color: '#777', marginBottom: 10 }}>
                class: <span style={{ color: LINK_CLASS_COLOR[series.lk.cls] || '#333' }}>
                  {(series.lk.cls||'').replace('_',' ')}
                </span>
              </div>

              <table style={{ ...S.table, marginBottom: 10 }}>
                <tbody>
                  {[
                    ['utilization at t',    frame.u[series.lk.i - 1]?.toFixed(5)],
                    ['confidence at t',     frame.c[series.lk.i - 1]?.toFixed(3)],
                    ['util (period mean)',  (series.u.reduce((a,b)=>a+b,0)/nFrames).toFixed(5)],
                    ['util (period max)',   Math.max(...series.u).toFixed(5)],
                    ['conf (period min)',   Math.min(...series.c).toFixed(3)],
                  ].map(([k, v]) => (
                    <tr key={k}>
                      <td style={S.td}>{k}</td>
                      <td style={{ ...S.td, textAlign: 'right' }}>{v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div style={{ fontSize: 11, color: '#444', marginBottom: 2 }}>
                utilization over period (bar = current t)
              </div>
              <Sparkline
                values={Array.from(series.u)} t={t}
                w={356} h={72} yMax={uMax} yRef={uMax * 0.85}
                color="#a63603" label={`util (ref ${(uMax*0.85).toFixed(2)})`}
              />

              <div style={{ fontSize: 11, color: '#444', margin: '8px 0 2px' }}>confidence over period</div>
              <Sparkline
                values={Array.from(series.c)} t={t}
                w={356} h={72} yMax={1.0} yRef={0.8}
                color="#08519c" label="conf (ref 0.80)"
              />
            </>
          )}
        </div>
      </div>

      {/* Rankings */}
      <div style={S.panel}>
        <div style={{ fontSize: 12, color: '#444', marginBottom: 8 }}>
          Top-5 hotspots at t={t} — naive view vs confidence-filtered (c≥{trust.toFixed(2)})
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {[
            { title: 'A. By utilization, ignoring confidence', rows: ranks.naive,    highlight: ranks.droppedFromNaive, bg: '#fdecea' },
            { title: `B. By utilization, c ≥ ${trust.toFixed(2)}`,  rows: ranks.filtered, highlight: ranks.addedByFilter,    bg: '#e8f5e9' },
          ].map(({ title, rows, highlight, bg }) => (
            <div key={title}>
              <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>{title}</div>
              <table style={S.table}>
                <thead>
                  <tr>{['#','link','src → dst','util','conf'].map(h => (
                    <th key={h} style={S.th}>{h}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {rows.length === 0 ? (
                    <tr><td colSpan={5} style={S.td}>no links meet threshold</td></tr>
                  ) : rows.map((r, k) => {
                    const lk = links[r.idx];
                    const hl = highlight.some(x => x.i === r.i);
                    return (
                      <tr key={r.i}
                        style={{ background: hl ? bg : (selected === r.i ? '#eef' : 'transparent'), cursor: 'pointer' }}
                        onClick={() => setSelected(r.i)}>
                        <td style={S.td}>{k+1}</td>
                        <td style={S.td}>{r.i}</td>
                        <td style={S.td}>{lk?.src} → {lk?.dst}</td>
                        <td style={{ ...S.td, textAlign: 'right' }}>{r.u.toFixed(5)}</td>
                        <td style={{ ...S.td, textAlign: 'right', color: r.c < trust ? '#c00' : '#111' }}>{r.c.toFixed(3)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ))}
        </div>
        <div style={{ fontSize: 11, color: '#666', marginTop: 8 }}>
          Red rows in A are dropped by the confidence filter; green rows in B appear only because lower-confidence rivals
          were removed. With filter off, both lists are identical — raise the slider to see the thesis in action.
        </div>
      </div>
    </div>
  );
}
