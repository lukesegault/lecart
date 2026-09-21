# next-ui: L'Écart design system and divergence chart

A self-contained Next.js 16 / Tailwind 4 / Recharts 3 prototype. It is **not** part of the live GitHub Pages site
(which stays vanilla HTML/JS, see `../CLAUDE.md`) and is not wired into `index.html`.

```bash
npm install
npm run dev        # http://localhost:3000   (?lang=en, ?metric=qual)
npm run typecheck
```

- **Tokens:** `src/app/globals.css` (`@theme`: mint-50/500/700, editorial-bg/ink/border/muted, poll, serif/sans/mono);
  `src/lib/chartTheme.ts` mirrors them as hex for SVG and PNG export. Keep both in sync.
- **Component:** `<DivergenceChart candidates events metric lang marketSource pollSource isDemo />`
  (`src/components/divergence`). Data shape: `src/lib/types.ts`. Everything is props-driven, so real series plug in
  without touching the component.
- **Mock data is fictional** (`src/lib/mockData.ts`, seeded). The chart and the exported PNG say so when `isDemo` is set:
  never publish it as measured. Event notes are illustrative mechanisms, not claims about real events.
- **Export:** "Exporter (PNG / Presse)" snapshots an off-screen 1200x675 card at 2x (2400x1350) with `html-to-image`.
- Fonts come from `next/font` (self-hosted at build time). Prices are data only: no link to any market platform.
