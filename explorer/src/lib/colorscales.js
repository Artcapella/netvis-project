// YlOrRd 5-stop (ColorBrewer)
const REDS = [
  [255, 255, 204],
  [254, 217, 118],
  [253, 141, 60],
  [227, 26,  28],
  [128, 0,   38],
];

// Blues 5-stop (ColorBrewer)
const BLUES = [
  [239, 243, 255],
  [189, 215, 231],
  [107, 174, 214],
  [49,  130, 189],
  [8,   81,  156],
];

function lerp(a, b, f) { return a + (b - a) * f; }

function rgbStr(r, g, b, a = 1) {
  return a < 1
    ? `rgba(${r | 0},${g | 0},${b | 0},${a})`
    : `rgb(${r | 0},${g | 0},${b | 0})`;
}

export function interpStops(stops, t) {
  const n = stops.length - 1;
  const i = Math.max(0, Math.min(n - 1, Math.floor(t * n)));
  const f = Math.max(0, Math.min(1, t * n - i));
  const a = stops[i], b = stops[i + 1];
  return [lerp(a[0], b[0], f), lerp(a[1], b[1], f), lerp(a[2], b[2], f)];
}

export function utilColor(u, uMax = 0.12, alpha = 1) {
  const t = Math.max(0, Math.min(1, u / uMax));
  const [r, g, b] = interpStops(REDS, t);
  return rgbStr(r, g, b, alpha);
}

export function confColor(c, cLo = 0.60, cHi = 1.00, alpha = 1) {
  const t = Math.max(0, Math.min(1, (c - cLo) / (cHi - cLo)));
  const [r, g, b] = interpStops(BLUES, t);
  return rgbStr(r, g, b, alpha);
}

export function confToAlpha(c, cLo = 0.60, cHi = 1.00) {
  const t = Math.max(0, Math.min(1, (c - cLo) / (cHi - cLo)));
  return 0.15 + 0.85 * t;
}

export { REDS, BLUES };
