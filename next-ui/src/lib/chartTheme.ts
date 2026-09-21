/**
 * Chart theme. Mirrors the @theme tokens in src/app/globals.css as plain hex, because SVG attributes
 * and the PNG export (html-to-image snapshots the DOM outside the page's CSS variables) need literal colours.
 */
export const theme = {
  bg: "#FAFAF9",
  surface: "#FFFFFF",
  border: "#E2E8F0",
  grid: "#E2E8F0",
  ink: "#0F172A",
  muted: "#475569",
  faint: "#94A3B8",
  market: "#00C48C",
  marketDeep: "#007A55",
  mintTint: "#E6F7F0",
  poll: "#64748B",
} as const;

export const stroke = {
  market: 2.5,
  poll: 2,
  pollDash: "4 4",
} as const;

/** Gradient of the "écart" spread between the two curves: rgba(0, 196, 140, 0.10) on average. */
export const spreadGradient = { top: 0.16, bottom: 0.05 } as const;
