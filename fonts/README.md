# Fonts

Self-hosted so the site makes no request to Google Fonts. Latin subset only (French and English text; the
symbols ● and ◆ fall back to a system font, as they did with Google Fonts). Files come from fonts.gstatic.com
(Google Fonts, 22 Sept 2026).

- Schibsted Grotesk (variable, 400 to 900): SIL Open Font License 1.1, https://fonts.google.com/specimen/Schibsted+Grotesk
- Spectral (400, 500): SIL Open Font License 1.1, Production Type, https://fonts.google.com/specimen/Spectral
- Used only by `index.html`, `candidat.html` and `second-tour.html` (`css/pages.css`), SIL Open Font License 1.1:
  - Bodoni Moda (500): h1 and h2 only, https://fonts.google.com/specimen/Bodoni+Moda
  - Source Serif 4 (400): all prose (dek, method, about, notes, footnotes), https://fonts.google.com/specimen/Source+Serif+4
  - IBM Plex Sans (400, 600): labels, nav, controls, table headers, candidate names, https://fonts.google.com/specimen/IBM+Plex+Sans
  - IBM Plex Mono (400, 600): numerals only, never words (the `.num` class and the numeric tokens in `css/type.css`), https://fonts.google.com/specimen/IBM+Plex+Mono

The sizes and weights each family may be used at are set in `css/type.css` and enforced by `scripts/audit_type.py`;
only the weights that scale uses are shipped.

Full licence text: https://openfontlicense.org
