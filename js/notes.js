(async () => {
  const { get, loadLang, paintNav } = Lecart;
  let NOTES = [];
  try { [, NOTES] = await Promise.all([loadLang(Lecart.lang), get("data/notes.json")]); } catch (e) {}

  function render() {
    document.title = Lecart.lang === "fr" ? "L'Écart · Notes" : "L'Écart · Notes";
    const sorted = NOTES.slice().sort((a, b) => b.date < a.date ? -1 : 1);
    document.getElementById("notesEmptyMsg").hidden = sorted.length > 0;
    document.getElementById("notesList").innerHTML = sorted.map(n =>
      `<div class="sp-note" style="border-left-color:var(--rule)">` +
      `<p class="sp-note-date">${Lecart.longDate(n.date)}</p>` +
      `<h2 class="sp-note-title">${Lecart.lang === "fr" ? n.titleFr : n.titleEn}</h2>` +
      `<p>${Lecart.lang === "fr" ? n.bodyFr : n.bodyEn}</p>` +
      `</div>`
    ).join("");
  }

  window.addEventListener("lecart-lang-change", () => { render(); paintNav("home"); });
  paintNav("home");
  render();
})();
