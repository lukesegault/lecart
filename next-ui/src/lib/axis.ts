import type { ChartRow, Metric, SeriesPoint, Timeframe } from "./types";

export const DAY = 86_400_000;

const TIMEFRAME_DAYS: Record<Exclude<Timeframe, "ALL">, number> = { "1M": 30, "3M": 91, "6M": 183 };

/** Points inside the timeframe, counted back from the latest point (not from today, so the chart is reproducible). */
export function windowPoints(points: SeriesPoint[], timeframe: Timeframe): SeriesPoint[] {
  const last = points.at(-1);
  if (!last || timeframe === "ALL") return points;
  const cutoff = last.t - TIMEFRAME_DAYS[timeframe] * DAY;
  return points.filter((p) => p.t >= cutoff);
}

/** Shapes points for the chart. The écart is drawn as two stacked areas: an invisible one up to the lower curve, then the spread. */
export function toRows(points: SeriesPoint[], metric: Metric): ChartRow[] {
  return points.map((p) => {
    const market = p[metric];
    return {
      t: p.t,
      date: p.date,
      poll: p.poll,
      market,
      base: Math.min(p.poll, market),
      spread: Math.abs(market - p.poll),
    };
  });
}

/** 0 to 60 % by default (spec); grows in steps of 10 if a series goes above it (e.g. runoff odds). */
export function yScale(rows: ChartRow[]): { yMax: number; ticks: number[] } {
  const peak = Math.max(0, ...rows.flatMap((r) => [r.poll, r.market]));
  const yMax = Math.max(60, Math.ceil(peak / 10) * 10);
  const step = yMax > 60 ? 20 : 10;
  const ticks: number[] = [];
  for (let v = 0; v <= yMax; v += step) ticks.push(v);
  return { yMax, ticks };
}

/** Weekly (Monday) ticks for short windows, month starts otherwise. */
export function timeTicks(t0: number, t1: number): { ticks: number[]; unit: "day" | "month" } {
  const ticks: number[] = [];
  if ((t1 - t0) / DAY <= 45) {
    const d = new Date(t0);
    const dow = (d.getUTCDay() + 6) % 7;
    let t = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) + ((7 - dow) % 7) * DAY;
    for (; t <= t1; t += 7 * DAY) ticks.push(t);
    return { ticks, unit: "day" };
  }
  const d = new Date(t0);
  let t = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1);
  if (t < t0) t = Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1);
  while (t <= t1) {
    ticks.push(t);
    const c = new Date(t);
    t = Date.UTC(c.getUTCFullYear(), c.getUTCMonth() + 1, 1);
  }
  return { ticks, unit: "month" };
}

export const isoToT = (iso: string): number => Date.parse(`${iso}T00:00:00Z`);
