import { isoToT } from "@/lib/axis";
import { colon, fmtDateLong, fmtDelta } from "@/lib/format";
import type { Labels } from "@/lib/labels";
import type { ChartEvent, Lang } from "@/lib/types";

interface Props {
  labels: Labels;
  lang: Lang;
  events: ChartEvent[];
  /** Event whose note is shown: hovered, else pinned. */
  activeId: string | null;
  pinnedId: string | null;
  /** Écart (market minus polls) on the day of an event, when the series covers it. */
  gapFor: (event: ChartEvent) => number | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string) => void;
}

/** Keyboard- and touch-friendly twin of the chart markers, plus the editorial note of the active one. */
export function EventNotes({ labels, lang, events, activeId, pinnedId, gapFor, onHover, onSelect }: Props) {
  if (events.length === 0) return null;
  const active = events.find((e) => e.id === activeId) ?? null;
  const gap = active ? gapFor(active) : null;
  return (
    <section aria-label={labels.events} className="mt-6 border-t border-editorial-border pt-5">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-editorial-muted">{labels.events}</h3>
      <ul className="mt-3 flex flex-wrap gap-2">
        {events.map((e, i) => {
          const on = e.id === activeId;
          return (
            <li key={e.id}>
              <button
                type="button"
                aria-pressed={e.id === pinnedId}
                onClick={() => onSelect(e.id)}
                onMouseEnter={() => onHover(e.id)}
                onMouseLeave={() => onHover(null)}
                className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors ${
                  on ? "border-mint-700 bg-mint-50 text-mint-700" : "border-editorial-border bg-white text-editorial-ink hover:border-mint-500"
                }`}
              >
                <span
                  aria-hidden
                  className={`grid h-5 w-5 place-items-center rounded-full border font-mono text-[11px] font-bold ${
                    on ? "border-mint-700 bg-mint-700 text-white" : "border-poll text-editorial-ink"
                  }`}
                >
                  {i + 1}
                </span>
                {e.label[lang]}
              </button>
            </li>
          );
        })}
      </ul>

      <div aria-live="polite" className="mt-4 min-h-24 rounded-xl border border-editorial-border bg-editorial-bg p-4">
        {active ? (
          <>
            <p className="font-serif text-lg font-semibold text-editorial-ink">{active.label[lang]}</p>
            <p className="mt-0.5 font-mono text-xs tracking-tight tabular-nums text-editorial-muted">
              {fmtDateLong(isoToT(active.date), lang)}
              {gap !== null ? ` · ${labels.eventGap}${colon(lang)}${fmtDelta(gap, lang)}` : ""}
            </p>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-editorial-ink">{active.note[lang]}</p>
          </>
        ) : (
          <p className="text-sm text-editorial-muted">{labels.eventHint}</p>
        )}
      </div>
    </section>
  );
}
