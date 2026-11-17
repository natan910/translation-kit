"""Passo 9 — esporta il copione in Excel (.xlsx) e Word (.docx).

Uso:  python3 scripts/export.py work/final/copione.tsv "Serie vol. 1"
      [--out output/] [--glossary config/glossary.tsv]

Il TSV deve avere le colonne del copione adattato:
  pag_pdf, folio, id, tipo, personaggio, originale, traduzione, adattamento, capienza, stato, note_editor

xlsx: foglio Copione (filtrabile, stati colorati, colonna vuota "Nota redattore" per la revisione),
      foglio Da rivedere (LUNGO + RIVEDERE), foglio Glossario.
docx: A4 orizzontale; glossario, righe da rivedere, legenda, poi capitolo per capitolo, pagina per pagina.
Il file rivisto (xlsx o docx) si rimanda indietro con scripts/review_diff.py.
"""
import argparse
import re
from pathlib import Path

from common import CONFIG, OUTPUT, chapters, id_sort_key, read_tsv

STATE_FILL = {"LUNGO": "F8C9C4", "RIVEDERE": "FCE8B2", "STRETTO": "FFF6D9"}
XLSX_COLS = [("pag_pdf", "Pag. PDF", 8), ("folio", "Folio", 7), ("id", "#", 6), ("tipo", "Tipo", 8),
             ("personaggio", "Personaggio", 16), ("originale", "Originale", 40), ("traduzione", "Traduzione", 42),
             ("adattamento", "Adattamento (lettering)", 45), ("capienza", "Capienza (car.)", 10),
             ("stato", "Stato", 11), ("note_editor", "Note editor", 60), ("nota_redattore", "Nota redattore", 40)]


def slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return v


def load(tsv):
    _, rows = read_tsv(tsv)
    rows.sort(key=lambda r: (int(r["pag_pdf"]), r.get("tipo") == "SFX", id_sort_key(r.get("id", ""))))
    return rows


def write_xlsx(rows, gloss, title, path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Copione"
    ws.append([h for _, h, _ in XLSX_COLS])
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDDDDD")
    stato_col = [k for k, _, _ in XLSX_COLS].index("stato") + 1
    for r in rows:
        ws.append([to_int(r.get(k, "")) if k in ("pag_pdf", "capienza") else r.get(k, "") for k, _, _ in XLSX_COLS])
        st = r.get("stato", "")
        if st in STATE_FILL:
            ws.cell(ws.max_row, stato_col).fill = PatternFill("solid", fgColor=STATE_FILL[st])
    for i, (_, _, w) in enumerate(XLSX_COLS):
        ws.column_dimensions[chr(65 + i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    rv = wb.create_sheet("Da rivedere")
    rv.append(["Pag. PDF", "#", "Stato", "Adattamento", "Note editor"])
    for r in rows:
        if r.get("stato") in ("LUNGO", "RIVEDERE"):
            rv.append([to_int(r["pag_pdf"]), r.get("id", ""), r["stato"], r.get("adattamento", ""), r.get("note_editor", "")])
    for col, w in zip("ABCDE", (8, 6, 11, 50, 80)):
        rv.column_dimensions[col].width = w
    if gloss:
        g = wb.create_sheet("Glossario")
        g.append(["Originale", "Italiano", "Note"])
        for x in gloss:
            g.append([x.get("originale", ""), x.get("italiano", ""), x.get("note", "")])
        for col, w in zip("ABC", (24, 30, 80)):
            g.column_dimensions[col].width = w
    wb.properties.title = title
    wb.save(path)


def write_docx(rows, gloss, title, path):
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.shared import Cm, Pt, RGBColor
    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Cm(29.7), Cm(21.0)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Cm(1.5))
    st = doc.styles["Normal"]
    st.font.name = "Arial"
    st.font.size = Pt(9)
    doc.add_heading(title + " – Copione di lettering", 0)
    n = len(rows)
    cnt = {s: sum(1 for r in rows if r.get("stato") == s) for s in ("OK", "STRETTO", "LUNGO", "RIVEDERE")}
    doc.add_paragraph(f"{n} righe. OK {cnt['OK']} · STRETTO {cnt['STRETTO']} · LUNGO {cnt['LUNGO']} · RIVEDERE {cnt['RIVEDERE']}. "
                      "Chiave: numeri blu (testi) e lettere rosse (SFX) annotati sulle tavole. "
                      "\" / \" = a capo proposto; \" // \" = riga bianca. Folio = pagina stampata.")

    def table(header, data, widths):
        t = doc.add_table(rows=1, cols=len(header))
        t.style = "Table Grid"
        for i, h in enumerate(header):
            cell = t.rows[0].cells[i]
            cell.text = h
            cell.paragraphs[0].runs[0].font.bold = True
        for d in data:
            cells = t.add_row().cells
            for i, v in enumerate(d):
                cells[i].text = str(v)
        t.autofit = False
        for i, w in enumerate(widths):
            t.columns[i].width = Cm(w)
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
                for p in row.cells[i].paragraphs:
                    for run in p.runs:
                        run.font.size = Pt(8)
        return t

    if gloss:
        doc.add_heading("Glossario e decisioni", 1)
        table(["Originale", "Italiano", "Note"], [[g.get("originale", ""), g.get("italiano", ""), g.get("note", "")] for g in gloss],
              [5, 6, 15.7])
    flagged = [r for r in rows if r.get("stato") in ("LUNGO", "RIVEDERE")]
    if flagged:
        doc.add_heading("Da guardare per primi", 1)
        table(["Pag.", "#", "Stato", "Italiano", "Nota"],
              [[r["pag_pdf"], r.get("id", ""), r["stato"], r.get("adattamento", ""), r.get("note_editor", "")] for r in flagged],
              [1.3, 1.2, 2, 9, 13.2])
    chaps = chapters() or [{"title": "Copione", "first": 1, "last": 10 ** 6}]
    by_page = {}
    for r in rows:
        by_page.setdefault(int(r["pag_pdf"]), []).append(r)
    grey = RGBColor(0x66, 0x66, 0x66)
    for ch in chaps:
        pages = [p for p in sorted(by_page) if ch["first"] <= p <= ch["last"]]
        if not pages:
            continue
        doc.add_page_break()
        doc.add_heading(f"{ch['title']} (pp. {ch['first']}–{ch['last']})", 1)
        for p in pages:
            pr = by_page[p]
            fol = next((r["folio"] for r in pr if r.get("folio")), "")
            doc.add_heading(f"Pag. {p}" + (f" · folio {fol}" if fol else ""), 3)
            txt = [r for r in pr if r.get("tipo") != "VUOTA"]
            if not txt:
                para = doc.add_paragraph("Pagina senza testo.")
                para.runs[0].font.color.rgb = grey
                continue
            data = []
            for r in txt:
                note = r.get("note_editor", "") if r.get("stato") in ("LUNGO", "RIVEDERE") or "CORREZIONE" in r.get("note_editor", "") else ""
                data.append([r.get("id", ""), r.get("tipo", ""), r.get("personaggio", ""), r.get("originale", ""),
                             r.get("adattamento", ""), "" if r.get("stato") == "OK" else r.get("stato", ""), note])
            table(["#", "Tipo", "Chi", "Originale", "Italiano", "Stato", "Nota"], data, [1, 1.4, 2.6, 6.2, 7.4, 1.9, 6.2])
    doc.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tsv")
    ap.add_argument("title")
    ap.add_argument("--out", default=str(OUTPUT))
    ap.add_argument("--glossary", default=str(CONFIG / "glossary.tsv"))
    a = ap.parse_args()
    rows = load(a.tsv)
    gloss = read_tsv(a.glossary)[1] if Path(a.glossary).exists() else []
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    base = out / slug(a.title)
    import shutil
    shutil.copyfile(a.tsv, f"{base}_copione.tsv")  # copia esatta di ciò che si consegna: base per il confronto con la revisione
    write_xlsx(rows, gloss, a.title, f"{base}_copione.xlsx")
    write_docx(rows, gloss, a.title, f"{base}_copione.docx")
    print(f"{len(rows)} righe → {base}_copione.xlsx, {base}_copione.docx (+ {base.name}_copione.tsv per il confronto con la revisione)")


if __name__ == "__main__":
    main()
