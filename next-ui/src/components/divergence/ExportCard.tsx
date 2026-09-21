import { forwardRef } from "react";
import { isoToT } from "@/lib/axis";
import { theme } from "@/lib/chartTheme";
import { colon, fmtDateLong } from "@/lib/format";
import type { Labels } from "@/lib/labels";
import type { ChartEvent, ChartRow, Lang, Metric } from "@/lib/types";
import { ChartLegend } from "./ChartLegend";
import { DeltaPill } from "./DeltaPill";
import { DivergencePlot } from "./DivergencePlot";

export const EXPORT_SIZE = { width: 1200, height: 675 } as const;

interface Props {
  labels: Labels;
  lang: Lang;
  metric: Metric;
  name: string;
  caption: string;
  delta: number;
  rows: ChartRow[];
  events: ChartEvent[];
  asOfT: number;
  pollSource?: string;
  marketSource?: string;
  siteUrl: string;
  isDemo: boolean;
}

/**
 * The branded 1200x675 card that "Exporter (PNG / Presse)" snapshots (2x, so 2400x1350).
 * Static: no tooltip, no hover, fixed pixel sizes. Fictional data is flagged on the image itself.
 */
export const ExportCard = forwardRef<HTMLDivElement, Props>(function ExportCard(
  { labels, lang, metric, name, caption, delta, rows, events, asOfT, pollSource, marketSource, siteUrl, isDemo },
  ref,
) {
  const first = rows[0]?.t ?? 0;
  const last = rows.at(-1)?.t ?? 0;
  const shown = events
    .map((e, i) => ({ e, n: i + 1, t: isoToT(e.date) }))
    .filter(({ t }) => t >= first && t <= last);
  const sources = [pollSource, marketSource].filter(Boolean).join(" · ");
  return (
    <div
      ref={ref}
      style={{ width: EXPORT_SIZE.width, height: EXPORT_SIZE.height }}
      className="flex flex-col overflow-hidden bg-editorial-bg px-12 py-10 font-sans text-editorial-ink"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span aria-hidden className="flex items-center gap-1">
            <span className="h-3 w-3 rounded-full" style={{ background: theme.poll }} />
            <span className="h-3 w-3 rotate-45 rounded-[2px]" style={{ background: theme.market }} />
          </span>
          <span className="text-base font-bold tracking-tight">{labels.brand}</span>
        </div>
        {isDemo ? (
          <span className="rounded-full border border-editorial-border bg-white px-3 py-1 text-sm font-medium text-editorial-muted">
            {labels.demo}
          </span>
        ) : null}
      </div>

      <div className="mt-5 flex items-center gap-5">
        <h3 className="font-serif text-5xl font-semibold tracking-tight">{name}</h3>
        <DeltaPill delta={delta} lang={lang} label={labels.delta} size="lg" />
      </div>
      <p className="mt-2 text-base text-editorial-muted">{caption}</p>

      <div className="mt-4 rounded-xl border border-editorial-border bg-white px-3 py-2">
        <DivergencePlot
          rows={rows}
          events={events}
          lang={lang}
          metric={metric}
          gradientId="spread-export"
          interactive={false}
          fixedWidth={EXPORT_SIZE.width - 96 - 26}
          height={330}
        />
      </div>

      <div className="mt-3 flex items-start justify-between gap-6">
        <ChartLegend labels={labels} metric={metric} />
        {shown.length > 0 ? (
          <ol className="flex flex-wrap justify-end gap-x-4 gap-y-1 text-xs text-editorial-muted">
            {shown.map(({ e, n }) => (
              <li key={e.id} className="flex items-center gap-1.5">
                <span className="grid h-4 w-4 place-items-center rounded-full border border-poll font-mono text-[10px] font-bold text-editorial-ink">
                  {n}
                </span>
                {e.label[lang]}
              </li>
            ))}
          </ol>
        ) : null}
      </div>

      <div className="mt-auto flex items-end justify-between border-t border-editorial-border pt-3 text-xs text-editorial-muted">
        <span>
          {sources ? `${labels.sources}${colon(lang)}${sources} · ` : ""}
          {labels.asOf} {fmtDateLong(asOfT, lang)}
        </span>
        <span className="font-mono tracking-tight">{siteUrl}</span>
      </div>
    </div>
  );
});
