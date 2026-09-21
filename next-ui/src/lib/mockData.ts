import { DAY, isoToT } from "./axis";
import type { CandidateSeries, ChartEvent, SeriesPoint } from "./types";

/**
 * FICTIONAL demo data, generated deterministically (seeded), so server and client render the same numbers.
 * It imitates the shape of the real series (daily market prices, smoother polling average) and nothing else:
 * do not publish it as if it were measured. The chart shows a "fictional data" badge when `isDemo` is set.
 */
export const MOCK_END = "2026-09-21";
const DAYS = 183; // 6 months, inclusive
const START_T = isoToT(MOCK_END) - (DAYS - 1) * DAY;

type Knots = [day: number, value: number][];

interface Spec {
  id: string;
  name: string;
  short: string;
  poll: Knots;
  win: Knots;
  qual: Knots;
}

// Day indexes of the three illustrative events (see MOCK_EVENTS): 58, 108 and 156.
const SPECS: Spec[] = [
  {
    id: "le-pen",
    name: "Marine Le Pen",
    short: "Le Pen",
    poll: [[0, 33.0], [58, 33.4], [75, 34.6], [108, 34.0], [130, 35.0], [156, 34.2], [182, 33.9]],
    win: [[0, 29], [57, 30], [63, 37], [107, 36], [111, 43], [135, 41], [155, 40], [160, 34], [182, 37.5]],
    qual: [[0, 72], [57, 73], [63, 82], [107, 82], [111, 90], [155, 90], [160, 85], [182, 89]],
  },
  {
    id: "philippe",
    name: "Édouard Philippe",
    short: "Philippe",
    poll: [[0, 17.5], [58, 17.0], [108, 16.5], [156, 16.8], [182, 16.6]],
    win: [[0, 27], [57, 27], [63, 24], [107, 23], [111, 22], [155, 22], [160, 26], [182, 23.5]],
    qual: [[0, 52], [63, 49], [111, 48], [160, 52], [182, 49]],
  },
  {
    id: "glucksmann",
    name: "Raphaël Glucksmann",
    short: "Glucksmann",
    poll: [[0, 10.0], [58, 10.5], [108, 11.0], [156, 10.6], [182, 10.3]],
    win: [[0, 4.5], [63, 4.0], [111, 3.2], [160, 2.4], [182, 1.6]],
    qual: [[0, 10], [63, 9], [111, 8], [182, 6.9]],
  },
  {
    id: "melenchon",
    name: "Jean-Luc Mélenchon",
    short: "Mélenchon",
    poll: [[0, 14.0], [58, 14.5], [108, 15.2], [156, 16.0], [182, 16.2]],
    win: [[0, 9], [63, 10], [111, 11], [160, 12.5], [182, 12.5]],
    qual: [[0, 32], [111, 36], [160, 39], [182, 39]],
  },
  {
    id: "attal",
    name: "Gabriel Attal",
    short: "Attal",
    poll: [[0, 7.0], [58, 7.0], [108, 6.5], [156, 6.8], [182, 6.6]],
    win: [[0, 4.0], [63, 3.4], [111, 2.8], [182, 2.2]],
    qual: [[0, 9], [63, 8], [182, 6.4]],
  },
];

function mulberry32(seed: number): () => number {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function interpolate(knots: Knots, day: number): number {
  const first = knots[0];
  const last = knots[knots.length - 1];
  if (!first || !last) return 0;
  if (day <= first[0]) return first[1];
  if (day >= last[0]) return last[1];
  for (let i = 1; i < knots.length; i++) {
    const a = knots[i - 1];
    const b = knots[i];
    if (a && b && day <= b[0]) return a[1] + ((b[1] - a[1]) * (day - a[0])) / (b[0] - a[0]);
  }
  return last[1];
}

/** Knot-to-knot curve plus autocorrelated noise. Polls get little noise (they are an average), markets more. */
function curve(knots: Knots, amp: number, seed: number): number[] {
  const rand = mulberry32(seed);
  let drift = 0;
  return Array.from({ length: DAYS }, (_, day) => {
    drift = 0.85 * drift + amp * (rand() * 2 - 1);
    return Math.max(0.2, Math.round((interpolate(knots, day) + drift) * 10) / 10);
  });
}

function build(spec: Spec, seed: number): CandidateSeries {
  const poll = curve(spec.poll, 0.16, seed);
  const win = curve(spec.win, 0.55, seed + 1);
  const qual = curve(spec.qual, 0.8, seed + 2);
  const points: SeriesPoint[] = poll.map((p, day) => {
    const t = START_T + day * DAY;
    return { date: new Date(t).toISOString().slice(0, 10), t, poll: p, win: win[day] ?? 0, qual: Math.min(99, qual[day] ?? 0) };
  });
  return { id: spec.id, name: spec.name, short: spec.short, points };
}

export const MOCK_CANDIDATES: CandidateSeries[] = SPECS.map((s, i) => build(s, 1000 * (i + 1)));

/**
 * Illustrative markers. The notes explain the mechanism (why a market can move before or without the polls);
 * they do not claim that a specific real-world event happened on these dates.
 */
export const MOCK_EVENTS: ChartEvent[] = [
  {
    id: "declaration",
    date: "2026-05-19",
    label: { fr: "Annonce de candidature", en: "Candidacy announcement" },
    note: {
      fr: "Exemple : les marchés intègrent une annonce en quelques heures. Les sondages, dont le terrain dure plusieurs jours, ne la reflètent qu'à la vague suivante.",
      en: "Example: markets price in an announcement within hours. Polls, whose fieldwork takes several days, only reflect it in the next wave.",
    },
  },
  {
    id: "debate",
    date: "2026-07-08",
    label: { fr: "Débat télévisé", en: "Televised debate" },
    note: {
      fr: "Exemple : après un débat, les prix réagissent aussitôt. La moyenne des sondages, lissée sur plusieurs enquêtes, bouge beaucoup plus lentement.",
      en: "Example: after a debate, prices react at once. The polling average, smoothed over several surveys, moves far more slowly.",
    },
  },
  {
    id: "ruling",
    date: "2026-08-25",
    label: { fr: "Décision de justice", en: "Court ruling" },
    note: {
      fr: "Exemple : une décision de justice change la probabilité de victoire (le candidat pourra-t-il se présenter ?) sans modifier l'intention de vote mesurée.",
      en: "Example: a court ruling changes the probability of winning (can the candidate run?) without changing the measured voting intention.",
    },
  },
];
