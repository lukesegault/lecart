"use client";

import { useId, useMemo, useRef, useState } from "react";
import { toRows, windowPoints } from "@/lib/axis";
import { theme } from "@/lib/chartTheme";
import { colon, fmtDateLong } from "@/lib/format";
import { LABELS } from "@/lib/labels";
import type { CandidateSeries, ChartEvent, Lang, Metric, Timeframe } from "@/lib/types";
import { ChartHeader } from "./ChartHeader";
import { ChartLegend } from "./ChartLegend";
import { DivergencePlot } from "./DivergencePlot";
import { EventNotes } from "./EventNotes";
import { ExportCard } from "./ExportCard";

export interface DivergenceChartProps {
  candidates: CandidateSeries[];
  events?: ChartEvent[];
  initialCandidateId?: string;
  /** Market line compared with the polls: win probability (default) or runoff qualification. */
  metric?: Metric;
  lang?: Lang;
  /** Shown as plain text in the footer and on the exported card. Never linked: prices are data only. */
  marketSource?: string;
  pollSource?: string;
  /** Flags the data as fictional on the chart and on the PNG. Set it for any non-measured series. */
  isDemo?: boolean;
  /** Printed on the exported card. */
  siteUrl?: string;
  className?: string;
}

const nextFrame = () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));

export function DivergenceChart({
  candidates,
  events = [],
  initialCandidateId,
  metric = "win",
  lang = "fr",
  marketSource,
  pollSource,
  isDemo = false,
  siteUrl = "lukesegault.github.io/lecart",
  className = "",
}: DivergenceChartProps) {
  const L = LABELS[lang];
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [candidateId, setCandidateId] = useState(initialCandidateId ?? candidates[0]?.id ?? "");
  const [timeframe, setTimeframe] = useState<Timeframe>("6M");
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [pinnedId, setPinnedId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportFailed, setExportFailed] = useState(false);
  const exportRef = useRef<HTMLDivElement>(null);

  const candidate = candidates.find((c) => c.id === candidateId) ?? candidates[0];
  const rows = useMemo(() => (candidate ? toRows(windowPoints(candidate.points, timeframe), metric) : []), [candidate, timeframe, metric]);
  if (!candidate) return null;

  const latest = candidate.points.at(-1);
  const delta = latest ? latest[metric] - latest.poll : 0;
  const activeId = hoveredId ?? pinnedId;
  const caption = metric === "win" ? L.captionWin : L.captionQual;

  const gapFor = (e: ChartEvent): number | null => {
    const p = candidate.points.find((pt) => pt.date === e.date);
    return p ? p[metric] - p.poll : null;
  };

  async function onExport() {
    const node = exportRef.current;
    if (!node || exporting) return;
    setExporting(true);
    setExportFailed(false);
    try {
      await document.fonts.ready;
      await nextFrame();
      await nextFrame();
      const { toPng } = await import("html-to-image");
      const url = await toPng(node, { pixelRatio: 2, cacheBust: true, backgroundColor: theme.bg });
      const a = document.createElement("a");
      a.href = url;
      a.download = `lecart-${candidate?.id ?? "candidat"}-${metric}-${latest?.date ?? "export"}.png`;
      a.click();
    } catch {
      setExportFailed(true);
    } finally {
      setExporting(false);
    }
  }

  return (
    <section
      lang={lang}
      aria-label={candidate.name}
      className={`rounded-2xl border border-editorial-border bg-editorial-surface p-5 shadow-sm sm:p-8 ${className}`}
    >
      <ChartHeader
        labels={L}
        lang={lang}
        candidates={candidates}
        selectedId={candidate.id}
        name={candidate.name}
        caption={caption}
        delta={delta}
        timeframe={timeframe}
        exporting={exporting}
        onSelect={(id) => {
          setCandidateId(id);
          setPinnedId(null);
          setHoveredId(null);
        }}
        onTimeframe={setTimeframe}
        onExport={onExport}
      />
      {exportFailed ? (
        <p role="alert" className="mt-3 text-sm font-medium text-red-700">
          {L.exportError}
        </p>
      ) : null}

      <div role="group" aria-label={L.chartAria(candidate.name)} className="mt-6 h-[300px] w-full font-mono tabular-nums sm:h-[400px]">
        <DivergencePlot
          rows={rows}
          events={events}
          lang={lang}
          metric={metric}
          gradientId={`spread-${uid}`}
          interactive
          height="100%"
          activeEventId={activeId}
          onHoverEvent={setHoveredId}
          onSelectEvent={(id) => setPinnedId((cur) => (cur === id ? null : id))}
        />
      </div>

      <div className="mt-4">
        <ChartLegend labels={L} metric={metric} />
      </div>

      <EventNotes
        labels={L}
        lang={lang}
        events={events}
        activeId={activeId}
        pinnedId={pinnedId}
        gapFor={gapFor}
        onHover={setHoveredId}
        onSelect={(id) => setPinnedId((cur) => (cur === id ? null : id))}
      />

      <footer className="mt-6 flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-editorial-border pt-4 text-xs text-editorial-muted">
        <span>
          {[pollSource, marketSource].filter(Boolean).length > 0 ? `${L.sources}${colon(lang)}${[pollSource, marketSource].filter(Boolean).join(" · ")} · ` : ""}
          {latest ? `${L.asOf} ${fmtDateLong(latest.t, lang)}` : ""}
        </span>
        {isDemo ? (
          <span className="rounded-full border border-editorial-border bg-editorial-bg px-3 py-1 font-medium">{L.demo}</span>
        ) : null}
      </footer>

      {/* Off-screen: the branded card that the export button snapshots. Its wrapper is the one that is moved away, never the captured node. */}
      <div aria-hidden className="pointer-events-none fixed top-0 -left-[10000px]">
        <ExportCard
          ref={exportRef}
          labels={L}
          lang={lang}
          metric={metric}
          name={candidate.name}
          caption={caption}
          delta={delta}
          rows={rows}
          events={events}
          asOfT={latest?.t ?? 0}
          pollSource={pollSource}
          marketSource={marketSource}
          siteUrl={siteUrl}
          isDemo={isDemo}
        />
      </div>
    </section>
  );
}
