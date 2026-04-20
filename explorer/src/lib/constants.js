// ─── Network topology ────────────────────────────────────────
export const NODES = {
  "ATLA-M5": { lat: 33.75,   lng: -84.3833, city: "Atlanta (M5)" },
  "ATLAng":  { lat: 33.75,   lng: -84.3833, city: "Atlanta" },
  "CHINng":  { lat: 41.8333, lng: -87.6167, city: "Chicago" },
  "DNVRng":  { lat: 40.75,   lng: -105.0,   city: "Denver" },
  "HSTNng":  { lat: 29.7700, lng: -95.5174, city: "Houston" },
  "IPLSng":  { lat: 39.7806, lng: -86.1595, city: "Indianapolis" },
  "KSCYng":  { lat: 38.9617, lng: -96.5967, city: "Kansas City" },
  "LOSAng":  { lat: 34.05,   lng: -118.25,  city: "Los Angeles" },
  "NYCMng":  { lat: 40.7833, lng: -73.9667, city: "New York" },
  "SNVAng":  { lat: 37.3858, lng: -122.0255,city: "Sunnyvale" },
  "STTLng":  { lat: 47.6,    lng: -122.3,   city: "Seattle" },
  "WASHng":  { lat: 38.8973, lng: -77.0268, city: "Washington DC" },
};

export const NODE_OFFSETS = { "ATLA-M5": { dLat: -1.4, dLng: -1.8 } };

export const LINKS = [
  { i: 1,  src: "ATLA-M5", dst: "ATLAng",  cls: "background",       capacity: 9920 },
  { i: 2,  src: "ATLAng",  dst: "ATLA-M5", cls: "background",       capacity: 9920 },
  { i: 3,  src: "ATLAng",  dst: "HSTNng",  cls: "background",       capacity: 9920 },
  { i: 4,  src: "ATLAng",  dst: "IPLSng",  cls: "episode_specific", capacity: 9920 },
  { i: 5,  src: "ATLAng",  dst: "WASHng",  cls: "background",       capacity: 9920 },
  { i: 6,  src: "CHINng",  dst: "IPLSng",  cls: "stable_core",      capacity: 9920 },
  { i: 7,  src: "CHINng",  dst: "NYCMng",  cls: "background",       capacity: 9920 },
  { i: 8,  src: "DNVRng",  dst: "KSCYng",  cls: "stable_core",      capacity: 9920 },
  { i: 9,  src: "DNVRng",  dst: "SNVAng",  cls: "episode_specific", capacity: 9920 },
  { i: 10, src: "DNVRng",  dst: "STTLng",  cls: "background",       capacity: 9920 },
  { i: 11, src: "HSTNng",  dst: "ATLAng",  cls: "background",       capacity: 9920 },
  { i: 12, src: "HSTNng",  dst: "KSCYng",  cls: "background",       capacity: 9920 },
  { i: 13, src: "IPLSng",  dst: "CHINng",  cls: "stable_core",      capacity: 9920 },
  { i: 14, src: "IPLSng",  dst: "KSCYng",  cls: "semi_stable",      capacity: 9920 },
  { i: 15, src: "IPLSng",  dst: "NYCMng",  cls: "semi_stable",      capacity: 9920 },
  { i: 16, src: "KSCYng",  dst: "DNVRng",  cls: "stable_core",      capacity: 9920 },
  { i: 17, src: "KSCYng",  dst: "HSTNng",  cls: "background",       capacity: 9920 },
  { i: 18, src: "KSCYng",  dst: "IPLSng",  cls: "semi_stable",      capacity: 9920 },
  { i: 19, src: "KSCYng",  dst: "SNVAng",  cls: "stable_core",      capacity: 9920 },
  { i: 20, src: "LOSAng",  dst: "SNVAng",  cls: "semi_stable",      capacity: 9920 },
  { i: 21, src: "NYCMng",  dst: "CHINng",  cls: "background",       capacity: 9920 },
  { i: 22, src: "NYCMng",  dst: "IPLSng",  cls: "semi_stable",      capacity: 9920 },
  { i: 23, src: "NYCMng",  dst: "WASHng",  cls: "background",       capacity: 9920 },
  { i: 24, src: "SNVAng",  dst: "DNVRng",  cls: "episode_specific", capacity: 9920 },
  { i: 25, src: "SNVAng",  dst: "KSCYng",  cls: "stable_core",      capacity: 9920 },
  { i: 26, src: "SNVAng",  dst: "LOSAng",  cls: "semi_stable",      capacity: 9920 },
  { i: 27, src: "SNVAng",  dst: "STTLng",  cls: "stable_core",      capacity: 9920 },
  { i: 28, src: "STTLng",  dst: "DNVRng",  cls: "background",       capacity: 9920 },
  { i: 29, src: "STTLng",  dst: "SNVAng",  cls: "stable_core",      capacity: 9920 },
  { i: 30, src: "WASHng",  dst: "NYCMng",  cls: "background",       capacity: 9920 },
];

// Default encoding params (from original embedded data)
export const N_FRAMES = 1008;
export const N_LINKS  = 30;
export const U_SCALE  = 0.32;
export const C_LO     = 0.60;
export const C_HI     = 1.00;
export const MIN_PER_FRAME_DEFAULT = 10; // stride-2 → 10-min intervals

// SVG viewport
export const MAP_W = 640;
export const MAP_H = 380;

export function computeLayout(nodes, nodeOffsets = {}, W = MAP_W, H = MAP_H, pad = 38) {
  const pts = Object.entries(nodes).map(([name, n]) => {
    const off = nodeOffsets[name] || { dLat: 0, dLng: 0 };
    return { name, lat: n.lat + off.dLat, lng: n.lng + off.dLng };
  });
  const lats = pts.map(p => p.lat);
  const lngs = pts.map(p => p.lng);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs), maxLng = Math.max(...lngs);
  const rangeW = maxLng - minLng || 1;
  const rangeH = maxLat - minLat || 1;
  const pos = {};
  for (const p of pts) {
    pos[p.name] = {
      x: pad + (p.lng - minLng) / rangeW * (W - 2 * pad),
      y: pad + (maxLat - p.lat) / rangeH * (H - 2 * pad),
    };
  }
  return pos;
}

export function edgePath(a, b, offset) {
  const dx = b.x - a.x, dy = b.y - a.y;
  const len = Math.max(1, Math.hypot(dx, dy));
  const nx = -dy / len, ny = dx / len;
  return {
    x1: a.x + nx * offset, y1: a.y + ny * offset,
    x2: b.x + nx * offset, y2: b.y + ny * offset,
  };
}

export function formatTime(t, minPerFrame) {
  const minutes = t * minPerFrame;
  const day = Math.floor(minutes / (24 * 60)) + 1;
  const hh  = Math.floor((minutes % (24 * 60)) / 60);
  const mm  = Math.floor(minutes % 60);
  return `day ${day}, ${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}

export const LINK_CLASS_COLOR = {
  stable_core:      "#111",
  semi_stable:      "#444",
  episode_specific: "#777",
  background:       "#aaa",
};
