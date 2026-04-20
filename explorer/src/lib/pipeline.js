// ─── CSV parsing ─────────────────────────────────────────────

function parseCSV(text) {
  const lines = text.split(/\r?\n/).filter(l => l.trim());
  if (lines.length < 2) throw new Error('CSV has fewer than 2 lines');
  const headers = lines[0].split(',').map(s => s.trim());
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const parts = lines[i].split(',');
    const row = {};
    for (let j = 0; j < headers.length; j++) {
      row[headers[j]] = parts[j]?.trim() ?? '';
    }
    rows.push(row);
  }
  return { headers, rows };
}

// ─── Format detection ─────────────────────────────────────────

export const FORMAT = {
  EXPLORER:   'explorer',   // time_index, link_index, util_mean, confidence
  TELEMETRY:  'telemetry',  // link_id, time_index, utilization, ..., confidence
  DEMANDS:    'demands',    // time_index, source, target, demand_value
  NODES:      'nodes',      // node_id, x, y  OR  node_id, lat, lng
  LINKS:      'links',      // link_id, source, target, capacity
  UNKNOWN:    'unknown',
};

export function detectFormat(headers) {
  const h = new Set(headers.map(s => s.toLowerCase()));
  if (h.has('link_index') && h.has('util_mean'))        return FORMAT.EXPLORER;
  if (h.has('link_id') && h.has('utilization'))         return FORMAT.TELEMETRY;
  if (h.has('demand_value') || (h.has('source') && h.has('target') && !h.has('link_id')))
                                                         return FORMAT.DEMANDS;
  if (h.has('node_id') && (h.has('x') || h.has('lat'))) return FORMAT.NODES;
  if (h.has('link_id') && h.has('source') && h.has('target') && h.has('capacity'))
                                                         return FORMAT.LINKS;
  return FORMAT.UNKNOWN;
}

// ─── Default data builder (from embedded base64) ─────────────

export function buildDefaultData(DATA_B64, N_FRAMES, N_LINKS, U_SCALE, C_LO, C_HI, LINKS_CONST, NODES_CONST, NODE_OFFSETS_CONST) {
  const bin = atob(DATA_B64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);

  const util = new Float32Array(N_FRAMES * N_LINKS);
  const conf = new Float32Array(N_FRAMES * N_LINKS);

  for (let t = 0; t < N_FRAMES; t++) {
    for (let l = 0; l < N_LINKS; l++) {
      util[t * N_LINKS + l] = bytes[t * N_LINKS + l] / 255 * U_SCALE;
      conf[t * N_LINKS + l] = C_LO + bytes[N_FRAMES * N_LINKS + t * N_LINKS + l] / 255 * (C_HI - C_LO);
    }
  }

  return {
    nodes: buildNodeList(NODES_CONST, NODE_OFFSETS_CONST),
    links: LINKS_CONST,
    nFrames: N_FRAMES,
    nLinks: N_LINKS,
    minPerFrame: 10,
    util,
    conf,
    isMissing: null,
    staleness: null,
    latency: null,
    queue: null,
    hasFullTelemetry: false,
    source: 'Abilene (embedded, 1 week, 10-min intervals)',
    uMax: U_SCALE,
    cLo: C_LO,
    cHi: C_HI,
  };
}

function buildNodeList(NODES_CONST, NODE_OFFSETS_CONST) {
  return Object.entries(NODES_CONST).map(([id, n]) => {
    const off = NODE_OFFSETS_CONST[id] || { dLat: 0, dLng: 0 };
    return { id, city: n.city, lat: n.lat + off.dLat, lng: n.lng + off.dLng };
  });
}

// ─── Explorer CSV format ──────────────────────────────────────
// Columns: time_index, link_index, util_mean, confidence

export function parseExplorerCSV(text, linksConst, nodesConst, nodeOffsetsConst) {
  const { rows } = parseCSV(text);
  let maxT = 0, maxL = 0;
  for (const r of rows) {
    const ti = parseInt(r.time_index);
    const li = parseInt(r.link_index);
    if (!isFinite(ti) || !isFinite(li)) continue;
    if (ti > maxT) maxT = ti;
    if (li > maxL) maxL = li;
  }
  const nFrames = maxT + 1;
  const nLinks  = maxL; // link_index is 1-based in this format
  const util = new Float32Array(nFrames * nLinks);
  const conf = new Float32Array(nFrames * nLinks).fill(0.8);

  for (const r of rows) {
    const ti = parseInt(r.time_index);
    const li = parseInt(r.link_index) - 1; // 0-based
    const u  = parseFloat(r.util_mean);
    const c  = parseFloat(r.confidence ?? r.conf ?? '0.8');
    if (!isFinite(ti) || li < 0 || li >= nLinks) continue;
    util[ti * nLinks + li] = isFinite(u) ? u : 0;
    conf[ti * nLinks + li] = isFinite(c) ? c : 0.8;
  }

  const uMax = Math.max(...util) || 0.32;
  const cLo  = Math.min(...conf.filter(v => v > 0)) || 0.6;
  const cHi  = Math.max(...conf) || 1.0;

  return {
    nodes: buildNodeList(nodesConst, nodeOffsetsConst),
    links: linksConst.slice(0, nLinks),
    nFrames, nLinks, minPerFrame: 5,
    util, conf,
    isMissing: null, staleness: null, latency: null, queue: null,
    hasFullTelemetry: false,
    source: 'uploaded (explorer CSV format)',
    uMax, cLo, cHi,
  };
}

// ─── Telemetry CSV format ─────────────────────────────────────
// Columns: link_id, time_index, utilization, latency_proxy, queue_proxy,
//          variance, is_missing, staleness_count, disagreement, util_original, confidence

export function parseTelemetryCSV(text, linksConst, nodesConst, nodeOffsetsConst) {
  const { rows } = parseCSV(text);

  // Build link ordering from data
  const linkIds = [...new Set(rows.map(r => r.link_id))].sort();
  const timeIndices = [...new Set(rows.map(r => parseInt(r.time_index)))].sort((a,b)=>a-b);
  const nLinks  = linkIds.length;
  const nFrames = timeIndices.length;
  const tMap = new Map(timeIndices.map((t, i) => [t, i]));
  const lMap = new Map(linkIds.map((id, i) => [id, i]));

  const util      = new Float32Array(nFrames * nLinks);
  const conf      = new Float32Array(nFrames * nLinks).fill(0.8);
  const isMissing = new Uint8Array(nFrames * nLinks);
  const staleness = new Uint8Array(nFrames * nLinks);
  const latency   = new Float32Array(nFrames * nLinks);
  const queue     = new Float32Array(nFrames * nLinks);

  for (const r of rows) {
    const ti = tMap.get(parseInt(r.time_index));
    const li = lMap.get(r.link_id);
    if (ti === undefined || li === undefined) continue;
    const idx = ti * nLinks + li;
    util[idx]      = parseFloat(r.utilization)     || 0;
    conf[idx]      = parseFloat(r.confidence)      || 0.8;
    isMissing[idx] = r.is_missing === 'True' || r.is_missing === '1' ? 1 : 0;
    staleness[idx] = parseInt(r.staleness_count)   || 0;
    latency[idx]   = parseFloat(r.latency_proxy)   || 0;
    queue[idx]     = parseFloat(r.queue_proxy)     || 0;
    if (isMissing[idx]) util[idx] = NaN;
  }

  // Try to match link_ids to known Abilene links or build generic link list
  const resolvedLinks = buildLinksFromIds(linkIds, linksConst);
  const resolvedNodes = matchNodesForLinks(resolvedLinks, nodesConst, nodeOffsetsConst);

  const uMax = nanMax(util) || 0.32;
  const cLo  = nanMin(conf.filter(v => isFinite(v) && v > 0)) || 0.6;
  const cHi  = nanMax(conf) || 1.0;

  return {
    nodes: resolvedNodes,
    links: resolvedLinks,
    nFrames, nLinks, minPerFrame: 5,
    util, conf, isMissing, staleness, latency, queue,
    hasFullTelemetry: true,
    source: 'uploaded (telemetry_final.csv format)',
    uMax, cLo, cHi,
  };
}

// ─── Demands pipeline ─────────────────────────────────────────
// Full pipeline: demands.csv + (optionally nodes.csv + links.csv) → data object

export async function runPipeline({ demandsText, nodesText, linksText }, onProgress) {
  const step = (msg, pct) => onProgress?.({ msg, pct });

  step('Parsing topology...', 5);
  const nodesArr  = nodesText  ? parseNodesCSV(nodesText)  : null;
  const linksArr  = linksText  ? parseLinksCSV(linksText)  : null;

  step('Parsing demands...', 10);
  const { rows: demandRows } = parseCSV(demandsText);
  const demands = demandRows.map(r => ({
    time_index:   parseInt(r.time_index),
    source:       r.source,
    target:       r.target,
    demand_value: parseFloat(r.demand_value) || 0,
  })).filter(d => isFinite(d.time_index));

  if (demands.length === 0) throw new Error('No valid demand rows found');

  // Use provided nodes/links or fall back to hardcoded Abilene
  const nodes = nodesArr || DEFAULT_ABILENE_NODES;
  const links = linksArr || DEFAULT_ABILENE_LINKS;

  step('Building routing graph...', 15);
  const { adj, linkKeyMap } = buildRoutingGraph(nodes, links);

  const timeIndices = [...new Set(demands.map(d => d.time_index))].sort((a,b)=>a-b);
  const nFrames = timeIndices.length;
  const nLinks  = links.length;
  const tMap    = new Map(timeIndices.map((t,i) => [t,i]));

  const util    = new Float32Array(nFrames * nLinks);
  const latency = new Float32Array(nFrames * nLinks);
  const queue   = new Float32Array(nFrames * nLinks);

  // Path cache
  const pathCache = new Map();
  const byTime = new Map();
  for (const d of demands) {
    if (!byTime.has(d.time_index)) byTime.set(d.time_index, []);
    byTime.get(d.time_index).push(d);
  }

  step('Routing demands and computing utilization...', 20);
  let done = 0;
  for (const t of timeIndices) {
    const traffic = new Float32Array(nLinks);
    for (const d of (byTime.get(t) || [])) {
      const cacheKey = d.source + '→' + d.target;
      if (!pathCache.has(cacheKey)) {
        pathCache.set(cacheKey, bfsPath(adj, d.source, d.target));
      }
      const path = pathCache.get(cacheKey);
      if (!path) continue;
      for (let i = 0; i < path.length - 1; i++) {
        const lIdx = linkKeyMap.get(path[i] + '__' + path[i+1]);
        if (lIdx !== undefined) traffic[lIdx] += d.demand_value;
      }
    }
    const ti = tMap.get(t);
    for (let l = 0; l < nLinks; l++) {
      const cap = links[l].capacity || 9920;
      const u   = traffic[l] / cap;
      const lat = 5.0 / (1 - Math.min(u, 0.99));
      const q   = Math.max(0, u - 0.8) * cap;
      util[ti * nLinks + l]    = u;
      latency[ti * nLinks + l] = lat;
      queue[ti * nLinks + l]   = q;
    }
    done++;
    if (done % 50 === 0) {
      step(`Routed ${done}/${nFrames} timesteps...`, 20 + (done/nFrames)*50);
      await tick();
    }
  }

  step('Injecting uncertainty...', 72);
  await tick();
  const { conf, isMissing, staleness } = injectUncertainty(util, nFrames, nLinks, 42, onProgress);

  step('Finalizing...', 98);
  await tick();

  const uMax = nanMax(util) || 0.32;
  const cLo  = nanMin(conf.filter(v => isFinite(v) && v > 0)) || 0.6;
  const cHi  = nanMax(conf) || 1.0;

  const resolvedNodes = nodes.map(n => ({
    id: n.node_id || n.id,
    city: n.city || n.node_id || n.id,
    lat: parseFloat(n.lat || n.y),
    lng: parseFloat(n.lng || n.x),
  }));

  const resolvedLinks = links.map((l, i) => ({
    i: i + 1,
    src: l.source,
    dst: l.target,
    cls: 'background',
    capacity: l.capacity || 9920,
  }));

  step('Done', 100);

  return {
    nodes: resolvedNodes,
    links: resolvedLinks,
    nFrames, nLinks, minPerFrame: 5,
    util, conf, isMissing, staleness, latency, queue,
    hasFullTelemetry: true,
    source: `uploaded (${nFrames} timesteps × ${nLinks} links, pipeline computed)`,
    uMax, cLo, cHi,
  };
}

// ─── Uncertainty injection ───────────────────────────────────

function injectUncertainty(util, nFrames, nLinks, seed = 42, onProgress) {
  let rngState = seed >>> 0;
  const rng = () => {
    rngState = (Math.imul(1664525, rngState) + 1013904223) >>> 0;
    return rngState / 0xffffffff;
  };
  const randn = () => {
    const u1 = Math.max(1e-10, rng());
    return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * rng());
  };

  const conf      = new Float32Array(nFrames * nLinks);
  const isMissing = new Uint8Array(nFrames * nLinks);
  const staleness = new Uint8Array(nFrames * nLinks);

  for (let l = 0; l < nLinks; l++) {
    const variance = new Float32Array(nFrames);
    const disagree = new Float32Array(nFrames);
    const utilCol  = new Float32Array(nFrames);
    for (let t = 0; t < nFrames; t++) utilCol[t] = util[t * nLinks + l];

    // 1. Temporal variance (rolling σ, window=12)
    for (let t = 0; t < nFrames; t++) {
      const start  = Math.max(0, t - 11);
      const window = Array.from({ length: t - start + 1 }, (_, k) => utilCol[start + k]);
      const mean   = window.reduce((a,b) => a+b, 0) / window.length;
      const v      = window.reduce((a,b) => a+(b-mean)**2, 0) / window.length;
      variance[t]  = Math.sqrt(v);
    }

    // 2. Missingness (~8%, bursty)
    let burstActive = false;
    for (let t = 0; t < nFrames; t++) {
      if (burstActive) {
        isMissing[t * nLinks + l] = rng() < 0.4 ? 1 : 0;
        if (!isMissing[t * nLinks + l]) burstActive = false;
      } else if (rng() < 0.08) {
        isMissing[t * nLinks + l] = 1;
        burstActive = rng() < 0.4;
      }
    }

    // 3. Staleness (~5%)
    let staleCount = 0;
    for (let t = 1; t < nFrames; t++) {
      if (!isMissing[t * nLinks + l] && rng() < 0.05) {
        const prev = util[(t-1) * nLinks + l];
        util[t * nLinks + l] = prev;
        staleCount++;
        staleness[t * nLinks + l] = staleCount;
      } else {
        staleCount = 0;
      }
    }

    // 4. Estimator disagreement (Gaussian σ=0.05)
    for (let t = 0; t < nFrames; t++) disagree[t] = Math.abs(randn() * 0.05);

    // Composite confidence
    const maxVar  = Math.max(...variance) || 1;
    const maxDisg = Math.max(...disagree) || 1;
    for (let t = 0; t < nFrames; t++) {
      const v_n = variance[t]  / maxVar;
      const m   = isMissing[t * nLinks + l];
      const s_n = Math.min(staleness[t * nLinks + l] / 5, 1);
      const d_n = disagree[t]  / maxDisg;
      const raw = 0.30 * v_n + 0.25 * m + 0.20 * s_n + 0.25 * d_n;
      conf[t * nLinks + l] = Math.max(0.05, Math.min(1.0, 1 - raw));
    }
  }

  // Apply missingness → NaN
  for (let t = 0; t < nFrames; t++) {
    for (let l = 0; l < nLinks; l++) {
      if (isMissing[t * nLinks + l]) util[t * nLinks + l] = NaN;
    }
  }

  return { conf, isMissing, staleness };
}

// ─── Graph helpers ────────────────────────────────────────────

function buildRoutingGraph(nodes, links) {
  const adj = new Map();
  for (const n of nodes) {
    const id = n.node_id || n.id;
    adj.set(id, []);
  }
  const linkKeyMap = new Map();
  for (let i = 0; i < links.length; i++) {
    const l = links[i];
    const src = l.source, dst = l.target;
    if (!adj.has(src)) adj.set(src, []);
    if (!adj.has(dst)) adj.set(dst, []);
    adj.get(src).push(dst);
    linkKeyMap.set(src + '__' + dst, i);
  }
  return { adj, linkKeyMap };
}

function bfsPath(adj, src, dst) {
  if (src === dst) return [src];
  const visited = new Set([src]);
  const queue = [[src, [src]]];
  while (queue.length > 0) {
    const [node, path] = queue.shift();
    const neighbors = adj.get(node) || [];
    for (const next of neighbors) {
      const newPath = [...path, next];
      if (next === dst) return newPath;
      if (!visited.has(next)) {
        visited.add(next);
        queue.push([next, newPath]);
      }
    }
  }
  return null;
}

// ─── Nodes/Links CSV parsers ──────────────────────────────────

function parseNodesCSV(text) {
  const { headers, rows } = parseCSV(text);
  const h = headers.map(s => s.toLowerCase());
  const hasLat = h.includes('lat') || h.includes('latitude');
  return rows.map(r => {
    const id = r.node_id || r.id || r.name;
    return {
      node_id: id,
      id,
      city: r.city || r.label || id,
      lat: parseFloat(hasLat ? (r.lat || r.latitude) : r.y),
      lng: parseFloat(hasLat ? (r.lng || r.lon || r.longitude) : r.x),
    };
  }).filter(n => n.id && isFinite(n.lat) && isFinite(n.lng));
}

function parseLinksCSV(text) {
  const { rows } = parseCSV(text);
  return rows.map(r => ({
    link_id:  r.link_id,
    source:   r.source,
    target:   r.target,
    capacity: parseFloat(r.capacity) || 9920,
  })).filter(l => l.source && l.target);
}

// ─── Link/Node resolution helpers ────────────────────────────

function buildLinksFromIds(linkIds, linksConst) {
  return linkIds.map((id, i) => {
    // Try to find in known Abilene links first
    const known = linksConst.find(l => {
      const canonical = l.src + '__' + l.dst;
      return canonical === id || id.replace('ATLAM5','ATLA-M5') === canonical;
    });
    if (known) return known;
    // Parse from id format: "SRC__DST"
    const parts = id.split('__');
    return {
      i: i + 1,
      src: parts[0] || id,
      dst: parts[1] || id,
      cls: 'background',
      capacity: 9920,
    };
  });
}

function matchNodesForLinks(links, nodesConst, nodeOffsetsConst) {
  const nodeIds = [...new Set(links.flatMap(l => [l.src, l.dst]))];
  return nodeIds.map(id => {
    const normalId = id.replace('ATLAM5', 'ATLA-M5');
    const known = nodesConst[id] || nodesConst[normalId];
    const off = nodeOffsetsConst[id] || nodeOffsetsConst[normalId] || { dLat: 0, dLng: 0 };
    if (known) {
      return { id, city: known.city, lat: known.lat + off.dLat, lng: known.lng + off.dLng };
    }
    return { id, city: id, lat: 0, lng: 0 };
  });
}

// ─── Hardcoded Abilene fallback ───────────────────────────────
const DEFAULT_ABILENE_NODES = [
  { node_id: 'ATLA-M5', city: 'Atlanta (M5)',  lat: 33.75,   lng: -84.3833 },
  { node_id: 'ATLAng',  city: 'Atlanta',        lat: 33.75,   lng: -84.3833 },
  { node_id: 'CHINng',  city: 'Chicago',         lat: 41.8333, lng: -87.6167 },
  { node_id: 'DNVRng',  city: 'Denver',          lat: 40.75,   lng: -105.0   },
  { node_id: 'HSTNng',  city: 'Houston',         lat: 29.77,   lng: -95.5174 },
  { node_id: 'IPLSng',  city: 'Indianapolis',    lat: 39.7806, lng: -86.1595 },
  { node_id: 'KSCYng',  city: 'Kansas City',     lat: 38.9617, lng: -96.5967 },
  { node_id: 'LOSAng',  city: 'Los Angeles',     lat: 34.05,   lng: -118.25  },
  { node_id: 'NYCMng',  city: 'New York',        lat: 40.7833, lng: -73.9667 },
  { node_id: 'SNVAng',  city: 'Sunnyvale',       lat: 37.3858, lng: -122.0255},
  { node_id: 'STTLng',  city: 'Seattle',         lat: 47.6,    lng: -122.3   },
  { node_id: 'WASHng',  city: 'Washington DC',   lat: 38.8973, lng: -77.0268 },
];

const DEFAULT_ABILENE_LINKS = [
  { source: 'ATLA-M5', target: 'ATLAng',  capacity: 9920 },
  { source: 'ATLAng',  target: 'ATLA-M5', capacity: 9920 },
  { source: 'ATLAng',  target: 'HSTNng',  capacity: 9920 },
  { source: 'ATLAng',  target: 'IPLSng',  capacity: 9920 },
  { source: 'ATLAng',  target: 'WASHng',  capacity: 9920 },
  { source: 'CHINng',  target: 'IPLSng',  capacity: 9920 },
  { source: 'CHINng',  target: 'NYCMng',  capacity: 9920 },
  { source: 'DNVRng',  target: 'KSCYng',  capacity: 9920 },
  { source: 'DNVRng',  target: 'SNVAng',  capacity: 9920 },
  { source: 'DNVRng',  target: 'STTLng',  capacity: 9920 },
  { source: 'HSTNng',  target: 'ATLAng',  capacity: 9920 },
  { source: 'HSTNng',  target: 'KSCYng',  capacity: 9920 },
  { source: 'IPLSng',  target: 'CHINng',  capacity: 9920 },
  { source: 'IPLSng',  target: 'KSCYng',  capacity: 9920 },
  { source: 'IPLSng',  target: 'NYCMng',  capacity: 9920 },
  { source: 'KSCYng',  target: 'DNVRng',  capacity: 9920 },
  { source: 'KSCYng',  target: 'HSTNng',  capacity: 9920 },
  { source: 'KSCYng',  target: 'IPLSng',  capacity: 9920 },
  { source: 'KSCYng',  target: 'SNVAng',  capacity: 9920 },
  { source: 'LOSAng',  target: 'SNVAng',  capacity: 9920 },
  { source: 'NYCMng',  target: 'CHINng',  capacity: 9920 },
  { source: 'NYCMng',  target: 'IPLSng',  capacity: 9920 },
  { source: 'NYCMng',  target: 'WASHng',  capacity: 9920 },
  { source: 'SNVAng',  target: 'DNVRng',  capacity: 9920 },
  { source: 'SNVAng',  target: 'KSCYng',  capacity: 9920 },
  { source: 'SNVAng',  target: 'LOSAng',  capacity: 9920 },
  { source: 'SNVAng',  target: 'STTLng',  capacity: 9920 },
  { source: 'STTLng',  target: 'DNVRng',  capacity: 9920 },
  { source: 'STTLng',  target: 'SNVAng',  capacity: 9920 },
  { source: 'WASHng',  target: 'NYCMng',  capacity: 9920 },
];

// ─── Utilities ────────────────────────────────────────────────
function nanMax(arr) {
  let m = -Infinity;
  for (const v of arr) if (isFinite(v) && v > m) m = v;
  return m === -Infinity ? 0 : m;
}
function nanMin(arr) {
  let m = Infinity;
  for (const v of arr) if (isFinite(v) && v < m) m = v;
  return m === Infinity ? 0 : m;
}
const tick = () => new Promise(r => setTimeout(r, 0));
