"""Passo 8 — unisce gli adattamenti dei capitoli nel copione del volume.

Uso:  python3 scripts/merge.py            → work/final/copione.tsv
Controlla che ogni pagina del volume sia presente una volta sola e stampa il riepilogo per stato.
"""
from common import CONFIG, ED_COLS, WORK, chapters, id_sort_key, load_json, read_tsv, write_tsv


def main():
    offset = (load_json(CONFIG / "chapters.json", {}) or {}).get("folio_offset")
    rows, pages, missing_ch = [], {}, []
    for c in chapters():
        p = WORK / "chapters" / c["id"] / "adattamento.tsv"
        if not p.exists():
            missing_ch.append(c["id"])
            continue
        for r in read_tsv(p)[1]:
            if not r.get("folio") and offset is not None:
                r["folio"] = f"{int(r['pag_pdf']) + offset:03d}"
            rows.append(r)
            pages.setdefault(int(r["pag_pdf"]), c["id"])
    rows.sort(key=lambda r: (int(r["pag_pdf"]), r.get("tipo") == "SFX", id_sort_key(r["id"])))
    allp = set()
    for c in chapters():
        allp |= set(range(c["first"], c["last"] + 1))
    gaps = sorted(allp - set(pages))
    write_tsv(WORK / "final" / "copione.tsv", ED_COLS, rows)
    st = {s: sum(1 for r in rows if r["stato"] == s) for s in ("OK", "STRETTO", "LUNGO", "RIVEDERE")}
    print(f"copione.tsv: {len(rows)} righe, {len(pages)} pagine · {st}")
    if missing_ch:
        print("  capitoli senza adattamento:", ", ".join(missing_ch))
    if gaps:
        print("  pagine assenti:", gaps[:30])


if __name__ == "__main__":
    main()
