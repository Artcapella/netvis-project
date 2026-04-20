import { useState, useRef, useCallback } from 'react';
import {
  detectFormat, FORMAT,
  parseExplorerCSV, parseTelemetryCSV, runPipeline,
} from '../lib/pipeline.js';
import { LINKS, NODES, NODE_OFFSETS } from '../lib/constants.js';

const S = {
  overlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 1000,
  },
  modal: {
    background: '#fff', border: '1px solid #aaa',
    width: 600, maxWidth: '95vw', maxHeight: '90vh',
    display: 'flex', flexDirection: 'column',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    fontSize: 13,
  },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '10px 14px', borderBottom: '1px solid #ddd',
  },
  body: { padding: '14px', overflowY: 'auto', flex: 1 },
  footer: { padding: '10px 14px', borderTop: '1px solid #ddd', display: 'flex', gap: 8, justifyContent: 'flex-end' },
  btn: (primary) => ({
    padding: '5px 14px', fontSize: 12,
    border: '1px solid #666',
    background: primary ? '#111' : '#fff',
    color: primary ? '#fff' : '#111',
    cursor: 'pointer',
  }),
  dropzone: (drag) => ({
    border: `2px dashed ${drag ? '#333' : '#bbb'}`,
    background: drag ? '#f5f5f5' : '#fafafa',
    borderRadius: 2, padding: '24px 16px', textAlign: 'center',
    cursor: 'pointer', marginBottom: 12, transition: 'all 0.15s',
  }),
  fileRow: {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '6px 8px', border: '1px solid #e0e0e0',
    marginBottom: 6, fontSize: 12,
  },
  badge: (color) => ({
    padding: '1px 7px', fontSize: 10, fontFamily: 'monospace',
    background: color, color: '#fff', borderRadius: 10,
  }),
  progress: {
    height: 6, background: '#e8e8e8', borderRadius: 3, overflow: 'hidden', marginBottom: 4,
  },
  progressBar: (pct, color='#333') => ({
    height: '100%', width: `${pct}%`, background: color, transition: 'width 0.2s',
  }),
  error: { color: '#c00', fontSize: 12, margin: '8px 0', padding: '6px 8px', background: '#fff0f0', border: '1px solid #fcc' },
  info:  { color: '#333', fontSize: 11, margin: '8px 0', padding: '6px 8px', background: '#f8f8f8', border: '1px solid #ddd' },
  section: { marginBottom: 14 },
  label:  { fontSize: 11, color: '#555', marginBottom: 4, display: 'block' },
};

const FORMAT_LABELS = {
  [FORMAT.EXPLORER]:  { label: 'Explorer CSV',      color: '#2e86c1', desc: 'time_index, link_index, util_mean, confidence' },
  [FORMAT.TELEMETRY]: { label: 'Telemetry CSV',     color: '#1a7a4a', desc: 'link_id, time_index, utilization, …, confidence' },
  [FORMAT.DEMANDS]:   { label: 'Demands CSV',       color: '#8e44ad', desc: 'time_index, source, target, demand_value' },
  [FORMAT.NODES]:     { label: 'Nodes CSV',         color: '#d35400', desc: 'node_id, x/lat, y/lng' },
  [FORMAT.LINKS]:     { label: 'Links CSV',         color: '#c0392b', desc: 'link_id, source, target, capacity' },
  [FORMAT.UNKNOWN]:   { label: 'Unknown',           color: '#888',    desc: 'Unrecognised format' },
};

function firstLine(text) { return text.split(/\r?\n/)[0]; }

export default function DataUploadPanel({ onData, onClose }) {
  const [files, setFiles]         = useState([]); // [{name, text, format}]
  const [dragging, setDragging]   = useState(false);
  const [progress, setProgress]   = useState(null); // {msg, pct}
  const [error, setError]         = useState('');
  const [success, setSuccess]     = useState('');
  const fileInputRef              = useRef(null);

  const readFiles = async (fileList) => {
    setError('');
    setSuccess('');
    const results = [];
    for (const f of fileList) {
      const text = await f.text();
      const headers = firstLine(text).split(',').map(s => s.trim());
      const fmt = detectFormat(headers);
      results.push({ name: f.name, text, format: fmt, headers });
    }
    setFiles(prev => {
      // Merge: replace same format, keep others
      const next = [...prev];
      for (const r of results) {
        const existing = next.findIndex(p => p.format === r.format);
        if (existing >= 0) next[existing] = r;
        else next.push(r);
      }
      return next;
    });
  };

  const onDrop = useCallback(e => {
    e.preventDefault();
    setDragging(false);
    readFiles([...e.dataTransfer.files].filter(f => f.name.endsWith('.csv')));
  }, []);

  const onDragOver = e => { e.preventDefault(); setDragging(true); };
  const onDragLeave = () => setDragging(false);

  const removeFile = (name) => setFiles(f => f.filter(x => x.name !== name));

  const canProcess = () => {
    const fmts = files.map(f => f.format);
    if (fmts.includes(FORMAT.EXPLORER))  return 'explorer';
    if (fmts.includes(FORMAT.TELEMETRY)) return 'telemetry';
    if (fmts.includes(FORMAT.DEMANDS))   return 'demands';
    return null;
  };

  const handleProcess = async () => {
    setError('');
    setSuccess('');
    const fmtMap = Object.fromEntries(files.map(f => [f.format, f]));
    const mode = canProcess();
    if (!mode) { setError('No recognisable data file uploaded. See format guide below.'); return; }

    setProgress({ msg: 'Starting…', pct: 0 });

    try {
      let result;
      if (mode === 'explorer') {
        setProgress({ msg: 'Parsing explorer CSV…', pct: 30 });
        await tick();
        result = parseExplorerCSV(fmtMap[FORMAT.EXPLORER].text, LINKS, NODES, NODE_OFFSETS);
        setProgress({ msg: 'Done', pct: 100 });
      } else if (mode === 'telemetry') {
        setProgress({ msg: 'Parsing telemetry CSV…', pct: 30 });
        await tick();
        result = parseTelemetryCSV(fmtMap[FORMAT.TELEMETRY].text, LINKS, NODES, NODE_OFFSETS);
        setProgress({ msg: 'Done', pct: 100 });
      } else if (mode === 'demands') {
        result = await runPipeline(
          {
            demandsText: fmtMap[FORMAT.DEMANDS].text,
            nodesText:   fmtMap[FORMAT.NODES]?.text   ?? null,
            linksText:   fmtMap[FORMAT.LINKS]?.text   ?? null,
          },
          ({ msg, pct }) => setProgress({ msg, pct }),
        );
      }

      setSuccess(`Loaded: ${result.source}`);
      onData(result);
      setTimeout(onClose, 900);
    } catch (err) {
      setError(`Error: ${err.message || String(err)}`);
    } finally {
      setProgress(null);
    }
  };

  const mode = canProcess();
  const fmt = FORMAT_LABELS;

  return (
    <div style={S.overlay} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={S.modal}>
        {/* Header */}
        <div style={S.header}>
          <strong>Upload Network Data</strong>
          <button style={{ ...S.btn(false), padding: '2px 8px' }} onClick={onClose}>✕</button>
        </div>

        {/* Body */}
        <div style={S.body}>
          {/* Dropzone */}
          <div
            style={S.dropzone(dragging)}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onClick={() => fileInputRef.current?.click()}
          >
            <div style={{ fontSize: 28, marginBottom: 6 }}>↑</div>
            <div style={{ fontWeight: 500, marginBottom: 4 }}>Drop CSV files here, or click to browse</div>
            <div style={{ fontSize: 11, color: '#666' }}>
              Select one or more .csv files — format is auto-detected from column headers
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              multiple
              style={{ display: 'none' }}
              onChange={e => readFiles([...e.target.files])}
            />
          </div>

          {/* File list */}
          {files.length > 0 && (
            <div style={S.section}>
              <span style={S.label}>Uploaded files</span>
              {files.map(f => {
                const fi = fmt[f.format] || fmt[FORMAT.UNKNOWN];
                return (
                  <div key={f.name} style={S.fileRow}>
                    <span style={S.badge(fi.color)}>{fi.label}</span>
                    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                    <span style={{ fontSize: 10, color: '#888', fontFamily: 'monospace' }}>
                      {(f.text.length / 1024).toFixed(1)} KB
                    </span>
                    <button
                      style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#999', fontSize: 13 }}
                      onClick={() => removeFile(f.name)}
                    >✕</button>
                  </div>
                );
              })}
            </div>
          )}

          {/* Pipeline note for demands */}
          {files.some(f => f.format === FORMAT.DEMANDS) && (
            <div style={S.info}>
              <strong>Pipeline mode:</strong> demands.csv detected. The app will route traffic,
              compute utilization, and inject synthetic uncertainty (client-side, ~5–30 s depending on size).
              {!files.some(f => f.format === FORMAT.NODES) && (
                <span> <em>No nodes.csv detected — using Abilene topology.</em></span>
              )}
            </div>
          )}

          {/* Progress */}
          {progress && (
            <div style={S.section}>
              <div style={S.progress}>
                <div style={S.progressBar(progress.pct, '#333')} />
              </div>
              <div style={{ fontSize: 11, color: '#555' }}>{progress.msg} ({Math.round(progress.pct)}%)</div>
            </div>
          )}

          {/* Error / Success */}
          {error   && <div style={S.error}>{error}</div>}
          {success && <div style={{ ...S.info, color: '#1a7a4a', background: '#f0fff4', border: '1px solid #b2dfdb' }}>{success}</div>}

          {/* Format guide */}
          <details style={{ marginTop: 16 }}>
            <summary style={{ cursor: 'pointer', fontSize: 11, color: '#555', userSelect: 'none' }}>
              Supported formats (click to expand)
            </summary>
            <div style={{ marginTop: 8 }}>
              {Object.entries(fmt).filter(([k]) => k !== FORMAT.UNKNOWN).map(([k, v]) => (
                <div key={k} style={{ marginBottom: 8 }}>
                  <span style={S.badge(v.color)}>{v.label}</span>
                  <span style={{ fontSize: 11, color: '#555', marginLeft: 8, fontFamily: 'monospace' }}>{v.desc}</span>
                </div>
              ))}
              <div style={{ fontSize: 11, color: '#777', marginTop: 8 }}>
                For the <strong>pipeline mode</strong>, upload <code>demands.csv</code> (required)
                and optionally <code>nodes.csv</code> + <code>links.csv</code> for a custom topology.
                Without nodes/links, the Abilene backbone topology is used.
              </div>
            </div>
          </details>
        </div>

        {/* Footer */}
        <div style={S.footer}>
          <button style={S.btn(false)} onClick={onClose} disabled={!!progress}>Cancel</button>
          <button
            style={S.btn(true)}
            onClick={handleProcess}
            disabled={!mode || !!progress}
          >
            {progress ? 'Processing…' : 'Load Data'}
          </button>
        </div>
      </div>
    </div>
  );
}

const tick = () => new Promise(r => setTimeout(r, 0));
