import { stroke, theme } from "@/lib/chartTheme";
import type { Labels } from "@/lib/labels";
import type { Metric } from "@/lib/types";

interface Props {
  labels: Labels;
  metric: Metric;
}

/** Hand-built legend: a solid mint line for the market, a dashed slate line for the polls, a tint for the écart. */
export function ChartLegend({ labels, metric }: Props) {
  return (
    <ul className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-editorial-muted">
      <li className="flex items-center gap-2">
        <svg width="26" height="8" aria-hidden>
          <line x1="1" x2="25" y1="4" y2="4" stroke={theme.market} strokeWidth={stroke.market} strokeLinecap="round" />
        </svg>
        {metric === "win" ? labels.legendWin : labels.legendQual}
      </li>
      <li className="flex items-center gap-2">
        <svg width="26" height="8" aria-hidden>
          <line x1="1" x2="25" y1="4" y2="4" stroke={theme.poll} strokeWidth={stroke.poll} strokeDasharray={stroke.pollDash} />
        </svg>
        {labels.legendPoll}
      </li>
      <li className="flex items-center gap-2">
        <span aria-hidden className="h-3 w-6 rounded-sm border border-mint-500/30 bg-mint-500/15" />
        {labels.legendSpread}
      </li>
    </ul>
  );
}
