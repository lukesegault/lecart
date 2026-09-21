import type { Lang } from "./types";

const NBSP = " ";
const locale = (lang: Lang) => (lang === "fr" ? "fr-FR" : "en-GB");

const number1 = (lang: Lang) =>
  new Intl.NumberFormat(locale(lang), { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** Label separator: French puts a non-breaking space before the colon, English does not. */
export const colon = (lang: Lang): string => (lang === "fr" ? `${NBSP}: ` : ": ");

/** 37.5 -> "37,5 %" (fr) or "37.5%" (en). */
export function fmtPct(v: number, lang: Lang): string {
  return lang === "fr" ? `${number1(lang).format(v)}${NBSP}%` : `${number1(lang).format(v)}%`;
}

/** Signed gap in percentage points: 3.84 -> "+3,8 pts", -2 -> "−2,0 pts". */
export function fmtDelta(d: number, lang: Lang): string {
  const rounded = Math.round(d * 10) / 10;
  const sign = rounded > 0 ? "+" : rounded < 0 ? "−" : "";
  return `${sign}${number1(lang).format(Math.abs(rounded))}${NBSP}pts`;
}

/** Dates are always UTC so server and browser render the same text. */
export function fmtDateLong(t: number, lang: Lang): string {
  return new Intl.DateTimeFormat(locale(lang), { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(t);
}

export function fmtTick(t: number, unit: "day" | "month", lang: Lang): string {
  const d = new Date(t);
  if (unit === "day") {
    return new Intl.DateTimeFormat(locale(lang), { day: "numeric", month: "short", timeZone: "UTC" }).format(t);
  }
  const month = new Intl.DateTimeFormat(locale(lang), { month: "short", timeZone: "UTC" }).format(t);
  return d.getUTCMonth() === 0 ? `${month} ${d.getUTCFullYear()}` : month;
}
