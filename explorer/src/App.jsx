import { useState, useEffect } from 'react';
import { DATA_B64 } from './lib/defaultData.js';
import { buildDefaultData } from './lib/pipeline.js';
import {
  NODES, NODE_OFFSETS, LINKS,
  N_FRAMES, N_LINKS, U_SCALE, C_LO, C_HI,
} from './lib/constants.js';
import ExplorerView       from './components/ExplorerView.jsx';
import TopologyCompareView from './components/TopologyCompareView.jsx';
import TimeSeriesView     from './components/TimeSeriesView.jsx';
import ScenariosView      from './components/ScenariosView.jsx';
import DataUploadPanel    from './components/DataUploadPanel.jsx';

const TABS = [
  { id: 'explorer',  label: 'Explorer',          desc: 'Animated topology, confidence filter, link rankings' },
  { id: 'compare',   label: 'Topology Compare',   desc: 'Figure A (congestion only) vs Figure B (confidence-aware)' },
  { id: 'timeseries',label: 'Time Series',        desc: 'Per-link utilization with confidence bands and anomaly markers' },
  { id: 'scenarios', label: 'Scenarios',          desc: 'Auto-detected evaluation scenarios (clean spike, noisy hotspot, missing gap, stable link)' },
];

const bodyFont = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
const mono     = '"Menlo","Consolas",monospace';

export default function App() {
  const [view, setView]           = useState('explorer');
  const [data, setData]           = useState(null);
  const [showUpload, setShowUpload] = useState(false);
  const [dataLabel, setDataLabel] = useState('');

  // Build default data on mount (synchronous decode of embedded base64)
  useEffect(() => {
    const d = buildDefaultData(
      DATA_B64, N_FRAMES, N_LINKS, U_SCALE, C_LO, C_HI,
      LINKS, NODES, NODE_OFFSETS,
    );
    setData(d);
    setDataLabel(d.source);
  }, []);

  const handleNewData = (d) => {
    setData(d);
    setDataLabel(d.source);
    setShowUpload(false);
  };

  if (!data) {
    return (
      <div style={{ fontFamily: bodyFont, padding: 40, color: '#555', fontSize: 14 }}>
        Loading default dataset…
      </div>
    );
  }

  const currentTab = TABS.find(t => t.id === view);

  return (
    <div style={{ fontFamily: bodyFont, fontSize: 13, minHeight: '100vh', background: '#fff' }}>
      {/* ── Header ── */}
      <div style={{ borderBottom: '1px solid #ddd', background: '#fff', position: 'sticky', top: 0, zIndex: 100 }}>
        <div style={{ padding: '0 16px', maxWidth: 1400, margin: '0 auto' }}>
          {/* Title row */}
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 16, padding: '10px 0 4px' }}>
            <h1 style={{
              margin: 0, fontSize: 17, fontWeight: 'normal',
              fontFamily: '"Georgia","Times New Roman",serif', color: '#111',
            }}>
              Abilene Network Congestion &amp; Uncertainty Explorer
            </h1>
            <span style={{ fontSize: 11, color: '#888', fontFamily: mono }}>
              12 routers · 30 directed links · SNDlib Abilene
            </span>
            <span style={{ flex: 1 }} />
            <button
              onClick={() => setShowUpload(true)}
              style={{
                border: '1px solid #666', background: '#fff', color: '#111',
                padding: '4px 12px', fontSize: 12, cursor: 'pointer',
                fontFamily: bodyFont,
              }}
            >
              ↑ Upload Data
            </button>
          </div>

          {/* Tab bar */}
          <div style={{ display: 'flex', gap: 0 }}>
            {TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => setView(tab.id)}
                title={tab.desc}
                style={{
                  border: 'none',
                  borderBottom: view === tab.id ? '2px solid #111' : '2px solid transparent',
                  background: 'none',
                  color: view === tab.id ? '#111' : '#666',
                  padding: '6px 14px',
                  fontSize: 12,
                  fontFamily: bodyFont,
                  cursor: 'pointer',
                  fontWeight: view === tab.id ? '600' : 'normal',
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Data source banner ── */}
      <div style={{
        background: '#f8f8f8', borderBottom: '1px solid #e8e8e8',
        padding: '4px 16px', fontSize: 11, color: '#666', fontFamily: mono,
        display: 'flex', gap: 16, alignItems: 'center',
      }}>
        <span>
          <span style={{ color: '#444' }}>data:</span> {dataLabel}
        </span>
        <span style={{ color: '#aaa' }}>|</span>
        <span>
          <span style={{ color: '#444' }}>frames:</span> {data.nFrames}
        </span>
        <span style={{ color: '#aaa' }}>|</span>
        <span>
          <span style={{ color: '#444' }}>links:</span> {data.nLinks}
        </span>
        <span style={{ color: '#aaa' }}>|</span>
        <span>
          <span style={{ color: '#444' }}>interval:</span> {data.minPerFrame} min
        </span>
        {data.hasFullTelemetry && (
          <>
            <span style={{ color: '#aaa' }}>|</span>
            <span style={{ color: '#1a7a4a' }}>✓ full telemetry (missing + stale markers)</span>
          </>
        )}
      </div>

      {/* ── Tab description ── */}
      <div style={{
        padding: '5px 16px', fontSize: 11, color: '#777',
        borderBottom: '1px solid #efefef', maxWidth: 1400, margin: '0 auto',
      }}>
        {currentTab?.desc}
      </div>

      {/* ── Main content ── */}
      <div style={{ padding: '12px 16px', maxWidth: 1400, margin: '0 auto' }}>
        {view === 'explorer'   && <ExplorerView        data={data} />}
        {view === 'compare'    && <TopologyCompareView  data={data} />}
        {view === 'timeseries' && <TimeSeriesView       data={data} />}
        {view === 'scenarios'  && <ScenariosView        data={data} />}
      </div>

      {/* ── Footer ── */}
      <div style={{
        borderTop: '1px solid #e8e8e8', padding: '10px 16px',
        fontSize: 10, color: '#888', fontFamily: mono,
        maxWidth: 1400, margin: '0 auto',
      }}>
        data: SNDlib directed-abilene-zhang-5min-over-6months, one-week subset (stride 2, 10-min intervals).
        Color scales: ColorBrewer YlOrRd and Blues.
        Built with React + SVG. &nbsp;|&nbsp;
        Upload your own CSVs (Explorer, Telemetry, or Demands format) via ↑ Upload Data.
      </div>

      {/* ── Upload modal ── */}
      {showUpload && (
        <DataUploadPanel
          onData={handleNewData}
          onClose={() => setShowUpload(false)}
        />
      )}
    </div>
  );
}
