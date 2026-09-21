import { fmtDelta } from "@/lib/format";
import type { Lang } from "@/lib/types";

interface Props {
  /** Market minus polls, in percentage points. */
  delta: number;
  lang: Lang;
  label?: string;
  size?: "sm" | "md" | "lg";
}

const SIZE = { sm: "px-2 py-0.5 text-xs", md: "px-3 py-1 text-sm", lg: "px-4 py-1.5 text-xl" } as const;

/** Emerald when the market sits above the polls, slate when below. The sign is always spelled out. */
export function DeltaPill({ delta, lang, label, size = "md" }: Props) {
  const above = delta >= 0;
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border font-mono font-medium tracking-tight tabular-nums ${SIZE[size]} ${
        above ? "border-mint-500/30 bg-mint-50 text-mint-700" : "border-editorial-border bg-slate-100 text-editorial-muted"
      }`}
    >
      {label ? <span className="font-sans text-[0.7em] font-semibold uppercase tracking-wider opacity-80">{label}</span> : null}
      {fmtDelta(delta, lang)}
    </span>
  );
}
