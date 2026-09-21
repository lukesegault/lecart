import { Download } from "lucide-react";
import type { Labels } from "@/lib/labels";
import type { Lang, Timeframe } from "@/lib/types";
import { DeltaPill } from "./DeltaPill";

const TIMEFRAMES: Timeframe[] = ["1M", "3M", "6M", "ALL"];

interface Props {
  labels: Labels;
  lang: Lang;
  candidates: { id: string; name: string; short?: string }[];
  selectedId: string;
  name: string;
  caption: string;
  /** Current écart: market minus polls, in points. */
  delta: number;
  timeframe: Timeframe;
  exporting: boolean;
  onSelect: (id: string) => void;
  onTimeframe: (tf: Timeframe) => void;
  onExport: () => void;
}

export function ChartHeader({
  labels,
  lang,
  candidates,
  selectedId,
  name,
  caption,
  delta,
  timeframe,
  exporting,
  onSelect,
  onTimeframe,
  onExport,
}: Props) {
  return (
    <header className="flex flex-col gap-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <h2 className="font-serif text-3xl font-semibold tracking-tight text-editorial-ink sm:text-4xl">{name}</h2>
            <DeltaPill delta={delta} lang={lang} label={labels.delta} />
          </div>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-editorial-muted">{caption}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2 lg:justify-end">
          <div role="group" aria-label={labels.period} className="inline-flex rounded-lg border border-editorial-border bg-white p-0.5">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                type="button"
                aria-pressed={timeframe === tf}
                onClick={() => onTimeframe(tf)}
                className={`rounded-md px-3 py-1.5 font-mono text-xs font-medium tracking-tight transition-colors ${
                  timeframe === tf ? "bg-mint-50 text-mint-700" : "text-editorial-muted hover:text-editorial-ink"
                }`}
              >
                {labels.timeframes[tf]}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={onExport}
            disabled={exporting}
            className="inline-flex items-center gap-2 rounded-lg bg-mint-700 px-3.5 py-2 text-sm font-medium text-white transition-colors hover:bg-editorial-ink disabled:cursor-wait disabled:opacity-70"
          >
            <Download aria-hidden size={16} strokeWidth={2} />
            <span>
              {exporting ? labels.exporting : labels.export}
              {exporting ? null : <span className="hidden sm:inline"> {labels.exportSuffix}</span>}
            </span>
          </button>
        </div>
      </div>

      <div role="group" aria-label={labels.candidate} className="flex flex-wrap gap-2">
        {candidates.map((c) => {
          const active = c.id === selectedId;
          return (
            <button
              key={c.id}
              type="button"
              aria-pressed={active}
              onClick={() => onSelect(c.id)}
              className={`rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors ${
                active
                  ? "border-mint-700 bg-mint-700 text-white"
                  : "border-editorial-border bg-white text-editorial-muted hover:border-mint-500 hover:text-mint-700"
              }`}
            >
              {c.short ?? c.name}
            </button>
          );
        })}
      </div>
    </header>
  );
}
