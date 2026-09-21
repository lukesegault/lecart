export type Lang = "fr" | "en";
/** Which market line is compared with the polls: win probability, or qualification for the runoff. */
export type Metric = "win" | "qual";
export type Timeframe = "1M" | "3M" | "6M" | "ALL";

/** One day of data for a candidate. All values are percentages (0 to 100). */
export interface SeriesPoint {
  /** ISO date, yyyy-mm-dd (UTC). */
  date: string;
  /** Same day as a UTC timestamp in ms, used as the numeric time axis. */
  t: number;
  /** Polling average, first-round voting intentions. */
  poll: number;
  /** Market-implied probability of winning the election. */
  win: number;
  /** Market-implied probability of reaching the runoff. */
  qual: number;
}

export interface CandidateSeries {
  id: string;
  name: string;
  /** Label of the selector pill, e.g. "Le Pen". Defaults to `name`. */
  short?: string;
  points: SeriesPoint[];
}

export interface Localized {
  fr: string;
  en: string;
}

/** An editorial marker pinned to a date where markets and polls diverged. */
export interface ChartEvent {
  id: string;
  /** ISO date, yyyy-mm-dd (UTC). */
  date: string;
  label: Localized;
  note: Localized;
}

/** A point as the chart consumes it. `base` and `spread` are the two stacked areas that fill the écart. */
export interface ChartRow {
  t: number;
  date: string;
  poll: number;
  market: number;
  base: number;
  spread: number;
}
