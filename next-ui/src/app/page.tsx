import { DivergenceChart } from "@/components/divergence";
import { MOCK_CANDIDATES, MOCK_EVENTS } from "@/lib/mockData";

const TOKENS = [
  { name: "editorial-bg", hex: "#FAFAF9", className: "bg-editorial-bg" },
  { name: "editorial-surface", hex: "#FFFFFF", className: "bg-editorial-surface" },
  { name: "editorial-border", hex: "#E2E8F0", className: "bg-editorial-border" },
  { name: "mint-50", hex: "#E6F7F0", className: "bg-mint-50" },
  { name: "mint-500", hex: "#00C48C", className: "bg-mint-500" },
  { name: "mint-700", hex: "#007A55", className: "bg-mint-700" },
  { name: "poll", hex: "#64748B", className: "bg-poll" },
  { name: "editorial-muted", hex: "#475569", className: "bg-editorial-muted" },
  { name: "editorial-ink", hex: "#0F172A", className: "bg-editorial-ink" },
] as const;

const COPY = {
  fr: { h1: "Les marchés voient-ils ce que les sondages ratent ?", intro: "alimenté par des données fictives.", src: ["Moyenne de sondages", "Marché prédictif"] },
  en: { h1: "Do markets see what the polls miss?", intro: "fed with fictional data.", src: ["Polling average", "Prediction market"] },
} as const;

/** Demo page. `?lang=en` switches the language, `?metric=qual` compares the polls with runoff qualification odds. */
export default async function Page({ searchParams }: { searchParams: Promise<{ lang?: string; metric?: string }> }) {
  const sp = await searchParams;
  const lang = sp.lang === "en" ? "en" : "fr";
  const metric = sp.metric === "qual" ? "qual" : "win";
  const c = COPY[lang];
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
      <p className="font-mono text-xs font-medium uppercase tracking-widest text-mint-700">L'Écart · Design system</p>
      <h1 className="mt-2 font-serif text-4xl font-semibold tracking-tight sm:text-5xl">{c.h1}</h1>
      <p className="mt-3 max-w-2xl font-serif text-lg leading-relaxed text-editorial-muted">
        <code className="font-mono text-base text-editorial-ink">DivergenceChart</code> {c.intro}
      </p>

      <DivergenceChart
        className="mt-8"
        candidates={MOCK_CANDIDATES}
        events={MOCK_EVENTS}
        initialCandidateId="le-pen"
        lang={lang}
        metric={metric}
        pollSource={c.src[0]}
        marketSource={c.src[1]}
        isDemo
      />

      <section aria-label="Design tokens" className="mt-12">
        <h2 className="font-serif text-2xl font-semibold tracking-tight">Tokens</h2>
        <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {TOKENS.map((t) => (
            <li key={t.name} className="overflow-hidden rounded-xl border border-editorial-border bg-white">
              <div className={`h-14 border-b border-editorial-border ${t.className}`} />
              <div className="px-3 py-2">
                <p className="text-sm font-medium">{t.name}</p>
                <p className="font-mono text-xs tracking-tight tabular-nums text-editorial-muted">{t.hex}</p>
              </div>
            </li>
          ))}
        </ul>
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <p className="font-serif text-2xl">Serif éditoriale</p>
          <p className="font-mono text-2xl tracking-tight tabular-nums">+3,8 pts · 37,5 %</p>
          <p className="font-sans text-2xl">Sans, interface</p>
        </div>
      </section>
    </main>
  );
}
