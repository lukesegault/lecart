import type { Lang, Timeframe } from "./types";

export interface Labels {
  delta: string;
  candidate: string;
  period: string;
  timeframes: Record<Timeframe, string>;
  export: string;
  exportSuffix: string;
  exporting: string;
  exportError: string;
  captionWin: string;
  captionQual: string;
  legendPoll: string;
  legendWin: string;
  legendQual: string;
  legendSpread: string;
  tipMarketWin: string;
  tipMarketQual: string;
  tipPoll: string;
  events: string;
  eventHint: string;
  eventGap: string;
  demo: string;
  sources: string;
  asOf: string;
  brand: string;
  chartAria: (name: string) => string;
}

export const LABELS: Record<Lang, Labels> = {
  fr: {
    delta: "L'Écart",
    candidate: "Candidat",
    period: "Période",
    timeframes: { "1M": "1M", "3M": "3M", "6M": "6M", ALL: "Tout" },
    export: "Exporter",
    exportSuffix: "(PNG / Presse)",
    exporting: "Export en cours…",
    exportError: "L'export a échoué. Réessayez.",
    captionWin: "Intentions de vote au premier tour (moyenne des sondages) et probabilité de victoire implicite du marché.",
    captionQual: "Intentions de vote au premier tour (moyenne des sondages) et probabilité implicite de qualification au second tour.",
    legendPoll: "Sondages : intentions de vote",
    legendWin: "Marché : probabilité de victoire",
    legendQual: "Marché : qualification au second tour",
    legendSpread: "L'Écart",
    tipMarketWin: "Marché, victoire",
    tipMarketQual: "Marché, second tour",
    tipPoll: "Moyenne des sondages",
    events: "Repères éditoriaux",
    eventHint: "Survolez ou touchez un repère pour lire la note.",
    eventGap: "Écart ce jour-là",
    demo: "Données fictives, à titre d'illustration",
    sources: "Sources",
    asOf: "Données au",
    brand: "L'Écart · Présidentielle 2027",
    chartAria: (name) => `Courbes des sondages et du marché pour ${name}, avec l'écart entre les deux`,
  },
  en: {
    delta: "The gap",
    candidate: "Candidate",
    period: "Period",
    timeframes: { "1M": "1M", "3M": "3M", "6M": "6M", ALL: "All" },
    export: "Export",
    exportSuffix: "(PNG / Press)",
    exporting: "Exporting…",
    exportError: "Export failed. Please try again.",
    captionWin: "First-round voting intentions (polling average) and the market-implied probability of winning.",
    captionQual: "First-round voting intentions (polling average) and the market-implied probability of reaching the runoff.",
    legendPoll: "Polls: voting intentions",
    legendWin: "Market: probability of winning",
    legendQual: "Market: reaching the runoff",
    legendSpread: "The gap",
    tipMarketWin: "Market, win",
    tipMarketQual: "Market, runoff",
    tipPoll: "Polling average",
    events: "Editorial markers",
    eventHint: "Hover or tap a marker to read the note.",
    eventGap: "Gap that day",
    demo: "Fictional data, for illustration only",
    sources: "Sources",
    asOf: "Data as of",
    brand: "L'Écart · French election 2027",
    chartAria: (name) => `Polls and market lines for ${name}, with the gap between them`,
  },
};
