import { fmtDateLong, fmtPct } from "@/lib/format";
import { theme } from "@/lib/chartTheme";
import type { ChartRow, Lang } from "@/lib/types";
import { DeltaPill } from "./DeltaPill";

interface Props {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: ChartRow }>;
  lang: Lang;
  marketLabel: string;
  pollLabel: string;
  deltaLabel: string;
}

/** High-contrast white card, 1px slate border: date, market, polls and the écart as an emerald pill. */
export function DivergenceTooltip({ active, payload, lang, marketLabel, pollLabel, deltaLabel }: Props) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className="min-w-56 rounded-lg border border-poll bg-white p-3 shadow-lg" role="status">
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-editorial-muted">{fmtDateLong(row.t, lang)}</p>
      <dl className="space-y-1.5 text-sm">
        <div className="flex items-center justify-between gap-6">
          <dt className="flex items-center gap-2 text-editorial-ink">
            <span aria-hidden className="h-2.5 w-2.5 rounded-full" style={{ background: theme.market }} />
            {marketLabel}
          </dt>
          <dd className="font-mono font-medium tracking-tight tabular-nums text-editorial-ink">{fmtPct(row.market, lang)}</dd>
        </div>
        <div className="flex items-center justify-between gap-6">
          <dt className="flex items-center gap-2 text-editorial-ink">
            <span aria-hidden className="h-2.5 w-2.5 rounded-full" style={{ background: theme.poll }} />
            {pollLabel}
          </dt>
          <dd className="font-mono font-medium tracking-tight tabular-nums text-editorial-ink">{fmtPct(row.poll, lang)}</dd>
        </div>
      </dl>
      <div className="mt-2.5 flex items-center justify-between border-t border-editorial-border pt-2.5">
        <span className="text-xs font-semibold uppercase tracking-wider text-editorial-muted">{deltaLabel}</span>
        <DeltaPill delta={row.market - row.poll} lang={lang} size="sm" />
      </div>
    </div>
  );
}
