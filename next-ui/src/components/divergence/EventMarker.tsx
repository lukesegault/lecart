import type { KeyboardEvent } from "react";
import { theme } from "@/lib/chartTheme";

interface Props {
  cx?: number;
  cy?: number;
  /** 1-based number shown in the marker; matches the list under the chart. */
  index: number;
  label: string;
  active: boolean;
  interactive: boolean;
  onHover?: (on: boolean) => void;
  onSelect?: () => void;
}

/** Numbered marker on the top rail of the chart. Hover or focus previews the note, click or Enter pins it. */
export function EventMarker({ cx, cy, index, label, active, interactive, onHover, onSelect }: Props) {
  if (cx === undefined || cy === undefined) return null;
  const onKeyDown = (e: KeyboardEvent<SVGGElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect?.();
    }
  };
  return (
    <g
      transform={`translate(${cx},${cy})`}
      {...(interactive
        ? {
            role: "button",
            tabIndex: 0,
            "aria-label": label,
            "aria-pressed": active,
            onMouseEnter: () => onHover?.(true),
            onMouseLeave: () => onHover?.(false),
            onFocus: () => onHover?.(true),
            onBlur: () => onHover?.(false),
            onClick: onSelect,
            onKeyDown,
            style: { cursor: "pointer" },
          }
        : {})}
    >
      <circle r={14} fill="transparent" />
      <circle
        r={active ? 11 : 9.5}
        fill={active ? theme.marketDeep : theme.surface}
        stroke={active ? theme.marketDeep : theme.poll}
        strokeWidth={1.5}
      />
      <text
        textAnchor="middle"
        dy="0.35em"
        fontSize={11}
        fontWeight={700}
        fill={active ? "#FFFFFF" : theme.ink}
        style={{ pointerEvents: "none", userSelect: "none" }}
      >
        {index}
      </text>
    </g>
  );
}
