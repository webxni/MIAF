"use client";

type BarChartData = { type: "bar" | "line"; title: string; xKey: string; yKey: string; data: Record<string, unknown>[] };
type PieChartData = { type: "pie"; title: string; labelKey: string; valueKey: string; data: Record<string, unknown>[] };
type MultiLineData = { type: "multi_line"; title: string; xKey: string; series: string[]; data: Record<string, unknown>[] };
export type ChartPayload = BarChartData | PieChartData | MultiLineData;

export function isChartPayload(value: unknown): value is ChartPayload {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    ["bar", "line", "pie", "multi_line"].includes(v.type as string) &&
    Array.isArray(v.data) &&
    v.data.length > 0
  );
}

const W = 480;
const H = 200;
const PAD = { top: 24, right: 12, bottom: 48, left: 48 };
const INNER_W = W - PAD.left - PAD.right;
const INNER_H = H - PAD.top - PAD.bottom;

const COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

function numVals(data: Record<string, unknown>[], key: string): number[] {
  return data.map((d) => Number(d[key]) || 0);
}

function scaleY(val: number, min: number, max: number): number {
  if (max === min) return INNER_H / 2;
  return INNER_H - ((val - min) / (max - min)) * INNER_H;
}

function scaleX(i: number, count: number): number {
  return count <= 1 ? INNER_W / 2 : (i / (count - 1)) * INNER_W;
}

function BarChart({ payload }: { payload: BarChartData }) {
  const vals = numVals(payload.data, payload.yKey);
  const max = Math.max(...vals, 0);
  const barW = Math.max(2, (INNER_W / vals.length) * 0.7);
  const gap = INNER_W / vals.length;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" aria-label={payload.title}>
      <g transform={`translate(${PAD.left},${PAD.top})`}>
        {vals.map((v, i) => {
          const bh = max > 0 ? (v / max) * INNER_H : 0;
          const x = gap * i + gap / 2 - barW / 2;
          const y = INNER_H - bh;
          return (
            <g key={i}>
              <rect x={x} y={y} width={barW} height={bh} fill={COLORS[0]} rx={2} opacity={0.85} />
              <text
                x={x + barW / 2}
                y={INNER_H + 14}
                textAnchor="middle"
                fontSize={10}
                fill="currentColor"
                opacity={0.6}
              >
                {String(payload.data[i][payload.xKey] ?? "").slice(0, 8)}
              </text>
            </g>
          );
        })}
        <line x1={0} y1={INNER_H} x2={INNER_W} y2={INNER_H} stroke="currentColor" opacity={0.2} />
      </g>
    </svg>
  );
}

function LineChart({ payload }: { payload: BarChartData }) {
  const vals = numVals(payload.data, payload.yKey);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const pts = vals
    .map((v, i) => `${scaleX(i, vals.length)},${scaleY(v, min, max)}`)
    .join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" aria-label={payload.title}>
      <g transform={`translate(${PAD.left},${PAD.top})`}>
        <polyline points={pts} fill="none" stroke={COLORS[0]} strokeWidth={2} />
        {vals.map((v, i) => (
          <g key={i}>
            <circle cx={scaleX(i, vals.length)} cy={scaleY(v, min, max)} r={3} fill={COLORS[0]} />
            <text
              x={scaleX(i, vals.length)}
              y={INNER_H + 14}
              textAnchor="middle"
              fontSize={10}
              fill="currentColor"
              opacity={0.6}
            >
              {String(payload.data[i][payload.xKey] ?? "").slice(0, 8)}
            </text>
          </g>
        ))}
        <line x1={0} y1={INNER_H} x2={INNER_W} y2={INNER_H} stroke="currentColor" opacity={0.2} />
      </g>
    </svg>
  );
}

function MultiLineChart({ payload }: { payload: MultiLineData }) {
  const series = payload.series;
  const allVals = series.flatMap((s) => numVals(payload.data, s));
  const min = Math.min(...allVals);
  const max = Math.max(...allVals);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" aria-label={payload.title}>
      <g transform={`translate(${PAD.left},${PAD.top})`}>
        {series.map((s, si) => {
          const vals = numVals(payload.data, s);
          const pts = vals
            .map((v, i) => `${scaleX(i, vals.length)},${scaleY(v, min, max)}`)
            .join(" ");
          return (
            <polyline
              key={s}
              points={pts}
              fill="none"
              stroke={COLORS[si % COLORS.length]}
              strokeWidth={2}
            />
          );
        })}
        {payload.data.map((d, i) => (
          <text
            key={i}
            x={scaleX(i, payload.data.length)}
            y={INNER_H + 14}
            textAnchor="middle"
            fontSize={10}
            fill="currentColor"
            opacity={0.6}
          >
            {String(d[payload.xKey] ?? "").slice(0, 8)}
          </text>
        ))}
        <line x1={0} y1={INNER_H} x2={INNER_W} y2={INNER_H} stroke="currentColor" opacity={0.2} />
      </g>
      <g transform={`translate(${PAD.left},${H - 12})`}>
        {series.map((s, si) => (
          <g key={s} transform={`translate(${si * 100},0)`}>
            <rect width={10} height={4} y={-3} fill={COLORS[si % COLORS.length]} rx={1} />
            <text x={14} fontSize={9} fill="currentColor" opacity={0.7}>{s}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}

function PieChart({ payload }: { payload: PieChartData }) {
  const vals = numVals(payload.data, payload.valueKey);
  const total = vals.reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  const cx = W / 2;
  const cy = H / 2;
  const r = Math.min(INNER_W, INNER_H) / 2 - 4;

  let angle = -Math.PI / 2;
  const slices = vals.map((v, i) => {
    const sweep = (v / total) * 2 * Math.PI;
    const x1 = cx + r * Math.cos(angle);
    const y1 = cy + r * Math.sin(angle);
    angle += sweep;
    const x2 = cx + r * Math.cos(angle);
    const y2 = cy + r * Math.sin(angle);
    const large = sweep > Math.PI ? 1 : 0;
    return { path: `M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${large} 1 ${x2},${y2} Z`, color: COLORS[i % COLORS.length], label: String(payload.data[i][payload.labelKey] ?? ""), pct: Math.round((v / total) * 100) };
  });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" aria-label={payload.title}>
      {slices.map((s, i) => (
        <path key={i} d={s.path} fill={s.color} opacity={0.85} stroke="var(--surface)" strokeWidth={1} />
      ))}
      <g transform={`translate(${PAD.left / 2},${H - 14})`}>
        {slices.map((s, i) => (
          <g key={i} transform={`translate(${i * 110},0)`}>
            <rect width={8} height={8} fill={s.color} rx={1} />
            <text x={12} y={7} fontSize={9} fill="currentColor" opacity={0.8}>
              {s.label.slice(0, 10)} {s.pct}%
            </text>
          </g>
        ))}
      </g>
    </svg>
  );
}

export function MiniChart({ payload }: { payload: ChartPayload }) {
  return (
    <div className="mt-3 rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-3">
      <p className="mb-2 text-xs font-semibold text-[var(--muted)]">{payload.title}</p>
      {payload.type === "bar" && <BarChart payload={payload} />}
      {payload.type === "line" && <LineChart payload={payload} />}
      {payload.type === "multi_line" && <MultiLineChart payload={payload} />}
      {payload.type === "pie" && <PieChart payload={payload} />}
    </div>
  );
}
