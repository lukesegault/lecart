"""Small hand-made data shared by the tests (no network)."""
import datetime

TODAY = datetime.date(2026, 9, 21)

# first-round polls; the second one has no Mélenchon
POLLS = [
    {"id": "p1", "inst": "A", "for": "X", "start": "2026-09-01", "end": "2026-09-03", "n": 1000,
     "v": {"Marine Le Pen": 31.0, "Édouard Philippe": 18.0, "Jean-Luc Mélenchon": 17.0, "Raphaël Glucksmann": 10.0, "Bruno Retailleau": 8.0}},
    {"id": "p2", "inst": "B", "for": "Y", "start": "2026-09-05", "end": "2026-09-07", "n": 1200,
     "v": {"Marine Le Pen": 33.5, "Édouard Philippe": 16.5, "Raphaël Glucksmann": 12.0, "Bruno Retailleau": 9.0}},
    {"id": "p3", "inst": "C", "for": "Z", "start": "2026-09-10", "end": "2026-09-12", "n": 900,
     "v": {"Marine Le Pen": 29.0, "Édouard Philippe": 19.0, "Jean-Luc Mélenchon": 15.5, "Raphaël Glucksmann": 11.0, "Bruno Retailleau": 7.5}},
]
PAIRS = {"Marine Le Pen|Édouard Philippe": [53.3, 7], "Jean-Luc Mélenchon|Marine Le Pen": [33.5, 7]}


def csv_rows(poll_id, end, tour, scores):
    """Rows of the MieuxVoter CSV (only the columns the parser reads)."""
    return [{"poll_id": poll_id, "nom_institut": "Inst", "commanditaire": "Sponsor", "debut_enquete": end, "fin_enquete": end,
             "echantillon": "1000", "tour": tour, "candidat": c, "intentions": str(v)} for c, v in scores.items()]


def market(names_prices):
    """A Polymarket-like response: one Yes/No market per name."""
    return [{"markets": [{"groupItemTitle": n, "outcomePrices": f'["{p / 100}", "{1 - p / 100}"]', "outcomes": '["Yes", "No"]'}
                         for n, p in names_prices.items()], "volume": "1000000"}]
