"""Confronta la versione rivista dal redattore con quella consegnata, per far imparare gli agenti.

Uso:  python3 scripts/review_diff.py <rivisto.xlsx|.docx|.tsv> --delivered output/<titolo>_copione.tsv --label <serie>-vol<N>
      (--delivered = la copia TSV che export.py salva accanto all'xlsx e al docx consegnati)

Il file rivisto può essere:
  - l'xlsx esportato da export.py, modificato nelle colonne Adattamento / Personaggio / Stato, con commenti
    nella colonna "Nota redattore";
  - il docx esportato, modificato nella colonna Italiano (e Chi / Stato), con commenti nella colonna Nota;
  - un TSV con le stesse colonne del copione.
La chiave di confronto è (pagina PDF, #): non rinumerare le righe.

Scrive work/feedback/<label>/:
  diff.tsv     una riga per ogni campo cambiato: nostro testo, testo rivisto, traduzione, originale, nota
  summary.md   statistiche: righe cambiate, somiglianza media, sostituzioni ricorrenti di parole,
               matrice degli stati (nostro → rivisto), commenti del redattore
Sono l'input dell'agente feedback-analyst (Opus), che propone le regole da aggiungere a config/learned/.
"""
import argparse
import collections
import difflib
import re
from datetime import date
from pathlib import Path

from common import WORK, read_tsv, write_tsv

XLSX_MAP = {"Giapponese": "originale", "Pag. PDF": "pag_pdf", "#": "id", "Tipo": "tipo", "Personaggio": "personaggio", "Originale": "originale",
            "Traduzione": "traduzione", "Adattamento (lettering)": "adattamento", "Stato": "stato",
            "Note editor": "note_editor", "Nota redattore": "nota_redattore"}
DOCX_MAP = {"Giapponese": "originale", "#": "id", "Tipo": "tipo", "Chi": "personaggio", "Originale": "originale", "Italiano": "adattamento",
            "Stato": "stato", "Nota": "nota_docx"}
FIELDS = ["adattamento", "personaggio", "stato", "tipo"]


def norm(v):
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip()


def read_xlsx(path):
    from openpyxl import load_workbook
    ws = load_workbook(path, read_only=True, data_only=True)["Copione"]
    it = ws.iter_rows(values_only=True)
    header = [XLSX_MAP.get(norm(h), norm(h)) for h in next(it)]
    return [dict(zip(header, [norm(v) for v in row])) for row in it if any(v is not None for v in row)]


def read_docx(path):
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    doc = Document(path)
    rows, page = [], None
    for el in doc.element.body.iterchildren():
        tag = el.tag.split("}")[1]
        if tag == "p":
            m = re.match(r"Pag\.\s*(\d+)", Paragraph(el, doc).text.strip())
            if m:
                page = int(m.group(1))
        elif tag == "tbl" and page is not None:
            t = Table(el, doc)
            header = [norm(c.text) for c in t.rows[0].cells]
            if "Pag." in header or "#" not in header:
                continue
            keys = [DOCX_MAP.get(h, h) for h in header]
            for row in t.rows[1:]:
                d = dict(zip(keys, [norm(c.text) for c in row.cells]))
                d["pag_pdf"] = str(page)
                if d.get("stato", "") == "":
                    d["stato"] = "OK"  # nel docx lo stato OK è lasciato vuoto
                rows.append(d)
    return rows


def read_any(path):
    p = Path(path)
    if p.suffix.lower() == ".xlsx":
        return read_xlsx(p)
    if p.suffix.lower() == ".docx":
        return read_docx(p)
    return [{k: norm(v) for k, v in r.items()} for r in read_tsv(p)[1]]


def k(r):
    try:
        return (int(float(r["pag_pdf"])), norm(r["id"]))
    except (KeyError, ValueError):
        return None


def word_subs(a, b, counter):
    wa, wb = a.replace(" / ", " ").split(), b.replace(" / ", " ").split()
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=wa, b=wb).get_opcodes():
        if op == "replace" and (i2 - i1) <= 4 and (j2 - j1) <= 4:
            counter[(" ".join(wa[i1:i2]), " ".join(wb[j1:j2]))] += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reviewed")
    ap.add_argument("--delivered", default=str(WORK / "final" / "copione.tsv"))
    ap.add_argument("--label", default=date.today().isoformat())
    a = ap.parse_args()
    ours = {k(r): {f: norm(v) for f, v in r.items()} for r in read_tsv(a.delivered)[1]}
    theirs = {}
    for r in read_any(a.reviewed):
        kk = k(r)
        if kk:
            theirs[kk] = r
    out_dir = WORK / "feedback" / a.label
    diffs, subs, conf = [], collections.Counter(), collections.Counter()
    sims, lens, comments = [], [], []
    changed_rows = set()
    for kk, o in ours.items():
        t = theirs.get(kk)
        if t is None:
            continue
        for f in FIELDS:
            if f not in t:
                continue
            ov, tv = o.get(f, ""), t.get(f, "")
            if f == "stato":
                conf[(ov or "—", tv or "—")] += 1
            if ov != tv:
                changed_rows.add(kk)
                diffs.append(dict(pag_pdf=kk[0], id=kk[1], campo=f, nostro=ov, rivisto=tv,
                                  traduzione=o.get("traduzione", ""), originale=o.get("originale", ""),
                                  nota=t.get("nota_redattore", "") or (t.get("nota_docx", "") if t.get("nota_docx", "") != o.get("note_editor", "") else "")))
                if f == "adattamento":
                    sims.append(difflib.SequenceMatcher(a=ov, b=tv).ratio())
                    lens.append(len(tv) - len(ov))
                    word_subs(ov, tv, subs)
        note = t.get("nota_redattore", "")
        if note:
            comments.append((kk, note))
            if kk not in changed_rows:
                diffs.append(dict(pag_pdf=kk[0], id=kk[1], campo="commento", nostro=o.get("adattamento", ""),
                                  rivisto="", traduzione=o.get("traduzione", ""), originale=o.get("originale", ""), nota=note))
    added = [kk for kk in theirs if kk not in ours]
    removed = [kk for kk in ours if kk not in theirs]
    write_tsv(out_dir / "diff.tsv", ["pag_pdf", "id", "campo", "nostro", "rivisto", "traduzione", "originale", "nota"], diffs)
    n = len([kk for kk in ours if kk in theirs])
    lines = [f"# Revisione {a.label}", "",
             f"- Righe confrontate: {n}; cambiate: {len(changed_rows)} ({100 * len(changed_rows) / max(n, 1):.1f}%)",
             f"- Campi cambiati: " + ", ".join(f"{f} {sum(1 for d in diffs if d['campo'] == f)}" for f in FIELDS),
             f"- Somiglianza media degli adattamenti cambiati: {sum(sims) / len(sims):.2f}" if sims else "- Nessun adattamento cambiato",
             f"- Variazione media di lunghezza: {sum(lens) / len(lens):+.1f} caratteri" if lens else "",
             f"- Righe aggiunte dal redattore: {len(added)}; righe tolte: {len(removed)}",
             f"- Commenti del redattore: {len(comments)}", "", "## Sostituzioni ricorrenti (nostro → rivisto)", ""]
    for (x, y), c in subs.most_common(30):
        if c >= 2:
            lines.append(f"- «{x}» → «{y}» ×{c}")
    lines += ["", "## Stati (nostro → rivisto)", ""]
    for (x, y), c in sorted(conf.items(), key=lambda z: -z[1]):
        if x != y:
            lines.append(f"- {x} → {y}: {c}")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.md").write_text("\n".join(l for l in lines if l is not None) + "\n", encoding="utf-8")
    print(f"Revisione {a.label}: {len(changed_rows)}/{n} righe cambiate · {len(diffs)} differenze → {out_dir.relative_to(WORK.parent)}/")


if __name__ == "__main__":
    main()
