"use client";

import { Fragment } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { isoToT, timeTicks, yScale } from "@/lib/axis";
import { spreadGradient, stroke, theme } from "@/lib/chartTheme";
import { fmtTick } from "@/lib/format";
import { LABELS } from "@/lib/labels";
import type { ChartEvent, ChartRow, Lang, Metric } from "@/lib/types";
import { DivergenceTooltip } from "./DivergenceTooltip";
import { EventMarker } from "./EventMarker";

interface Props {
  rows: ChartRow[];
  /** Every event, in order: marker numbers stay the same whatever the timeframe. */
  events: ChartEvent[];
  lang: Lang;
  metric: Metric;
  /** Unique per rendered plot: two plots on one page must not share an SVG gradient id. */
  gradientId: string;
  /** Interactive: responsive, tooltip, hover and pin on markers. Otherwise a fixed-size static plot (PNG export). */
  interactive: boolean;
  height: number | `${number}%`;
  fixedWidth?: number;
  activeEventId?: string | null;
  onHoverEvent?: (id: string | null) => void;
  onSelectEvent?: (id: string) => void;
}

export function DivergencePlot({
  rows,
  events,
  lang,
  metric,
  gradientId,
  interactive,
  height,
  fixedWidth,
  activeEventId,
  onHoverEvent,
  onSelectEvent,
}: Props) {
  const L = LABELS[lang];
  const first = rows[0];
  const last = rows.at(-1);
  if (!first || !last) return null;

  const { yMax, ticks: yTicks } = yScale(rows);
  const { ticks: xTicks, unit } = timeTicks(first.t, last.t);
  const marketLabel = metric === "win" ? L.tipMarketWin : L.tipMarketQual;

  const chart = (
    <ComposedChart
      data={rows}
      margin={{ top: 24, right: 14, bottom: 4, left: 0 }}
      {...(fixedWidth !== undefined ? { width: fixedWidth, height: height as number } : {})}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={theme.market} stopOpacity={spreadGradient.top} />
          <stop offset="100%" stopColor={theme.market} stopOpacity={spreadGradient.bottom} />
        </linearGradient>
      </defs>
      <CartesianGrid vertical={false} stroke={theme.grid} />
      <XAxis
        type="number"
        dataKey="t"
        scale="time"
        domain={[first.t, last.t]}
        ticks={xTicks}
        tickFormatter={(v: number) => fmtTick(v, unit, lang)}
        tickLine={false}
        axisLine={{ stroke: theme.grid }}
        tick={{ fill: theme.muted, fontSize: 12 }}
        tickMargin={8}
      />
      <YAxis
        domain={[0, yMax]}
        ticks={yTicks}
        tickFormatter={(v: number) => `${v}%`}
        tickLine={false}
        axisLine={false}
        width={44}
        tick={{ fill: theme.muted, fontSize: 12 }}
      />
      {interactive ? (
        <Tooltip
          isAnimationActive={false}
          cursor={{ stroke: theme.faint, strokeDasharray: "3 3" }}
          content={(p) => (
            <DivergenceTooltip
              active={p.active}
              payload={p.payload as ReadonlyArray<{ payload?: ChartRow }> | undefined}
              lang={lang}
              marketLabel={marketLabel}
              pollLabel={L.tipPoll}
              deltaLabel={L.delta}
            />
          )}
        />
      ) : null}

      {/* The écart: an invisible area up to the lower curve, then the spread stacked on top of it. */}
      <Area type="linear" dataKey="base" stackId="ecart" stroke="none" fill="none" activeDot={false} isAnimationActive={false} />
      <Area
        type="linear"
        dataKey="spread"
        stackId="ecart"
        stroke="none"
        fill={`url(#${gradientId})`}
        activeDot={false}
        isAnimationActive={false}
      />

      <Line
        type="linear"
        dataKey="poll"
        stroke={theme.poll}
        strokeWidth={stroke.poll}
        strokeDasharray={stroke.pollDash}
        dot={false}
        activeDot={interactive ? { r: 4, fill: theme.surface, stroke: theme.poll, strokeWidth: 2 } : false}
        isAnimationActive={false}
      />
      <Line
        type="linear"
        dataKey="market"
        stroke={theme.market}
        strokeWidth={stroke.market}
        strokeLinecap="round"
        dot={false}
        activeDot={interactive ? { r: 5, fill: theme.market, stroke: theme.surface, strokeWidth: 2 } : false}
        isAnimationActive={false}
      />

      {events.map((e, i) => {
        const t = isoToT(e.date);
        if (t < first.t || t > last.t) return null;
        const active = e.id === activeEventId;
        return (
          <Fragment key={e.id}>
            <ReferenceLine
              x={t}
              stroke={active ? theme.marketDeep : theme.faint}
              strokeWidth={active ? 1.5 : 1}
              strokeDasharray="2 3"
              ifOverflow="visible"
            />
            <ReferenceDot
              x={t}
              y={yMax}
              r={0}
              ifOverflow="visible"
              shape={(p: { cx?: number; cy?: number }) => (
                <EventMarker
                  cx={p.cx}
                  cy={p.cy}
                  index={i + 1}
                  label={e.label[lang]}
                  active={active}
                  interactive={interactive}
                  onHover={(on) => onHoverEvent?.(on ? e.id : null)}
                  onSelect={() => onSelectEvent?.(e.id)}
                />
              )}
            />
          </Fragment>
        );
      })}
    </ComposedChart>
  );

  return interactive ? (
    <ResponsiveContainer width="100%" height={height}>
      {chart}
    </ResponsiveContainer>
  ) : (
    chart
  );
}
