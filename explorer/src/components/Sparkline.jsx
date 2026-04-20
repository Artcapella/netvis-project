export default function Sparkline({ values, t, w = 360, h = 70, yMax, yRef = null, color = "#000", label = "" }) {
  if (!values || values.length === 0) return null;
  const max    = yMax ?? Math.max(...values.filter(isFinite));
  const safeMax = max || 1;
  const pad    = 2;
  const n      = values.length;
  const step   = (w - 2 * pad) / Math.max(n - 1, 1);

  // Build path, breaking on NaN
  let d = '';
  let penDown = false;
  for (let i = 0; i < n; i++) {
    const v = values[i];
    const x = (pad + i * step).toFixed(1);
    const y = (h - pad - (isFinite(v) ? v / safeMax : 0) * (h - 2 * pad)).toFixed(1);
    if (!isFinite(v)) { penDown = false; continue; }
    d += penDown ? ` L${x},${y}` : ` M${x},${y}`;
    penDown = true;
  }

  const tx = pad + t * step;

  return (
    <svg width={w} height={h} style={{ display: "block", border: "1px solid #ccc", background: "#fff" }}>
      {yRef !== null && (() => {
        const ry = h - pad - (yRef / safeMax) * (h - 2 * pad);
        return <line x1={pad} x2={w - pad} y1={ry} y2={ry}
                     stroke="#aaa" strokeDasharray="3 3" strokeWidth={0.8} />;
      })()}
      <path d={d} fill="none" stroke={color} strokeWidth={1} />
      <line x1={tx} x2={tx} y1={pad} y2={h - pad} stroke="#000" strokeWidth={0.8} />
      {label && (
        <text x={pad + 3} y={12} fontSize={9} fill="#555" fontFamily="monospace">{label}</text>
      )}
    </svg>
  );
}
