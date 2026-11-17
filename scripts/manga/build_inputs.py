"""Passo 5 — costruisce il copione sorgente di un capitolo per il traduttore.

Uso:  python3 scripts/build_inputs.py <capitolo>

Legge  work/detect/pNNN.json, work/ocr/pNNN.json, work/labels/<capitolo>.json (scritto dall'agente label-reader)
Scrive work/chapters/<capitolo>/source.tsv con una riga per testo/SFX:
  pag_pdf, id (numero blu / lettera rossa letti dall'etichetta), tipo, testo_ocr, conf_ocr,
  capienza (caratteri italiani), righe (caratteri per riga, forma del balloon), aperto, crop, rid, condiviso
"""
import sys

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import WORK, chapter_by_id, id_sort_key, load_json, page_ids, write_tsv

COLS = ["pag_pdf", "id", "tipo", "testo_ocr", "conf_ocr", "capienza", "righe", "aperto", "crop", "rid", "condiviso"]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cid = sys.argv[1]
    c = chapter_by_id(cid)
    labels = load_json(WORK / "labels" / f"{cid}.json", {})
    rows, missing, unread = [], 0, 0
    for pid in page_ids(c["first"], c["last"]):
        page = load_json(WORK / "detect" / f"{pid}.json")
        if not page:
            missing += 1
            continue
        ocr = load_json(WORK / "ocr" / f"{pid}.json", {})
        n = int(pid[1:])
        prow = []
        for r in page["regions"]:
            if r["tipo"] == "AUTO":
                lid = r["auto_id"]
            else:
                lid = str(labels.get(r["rid"], "")).strip()
                if not lid:
                    lid = "?" + r["rid"].split("_")[1]
                    unread += 1
            o = ocr.get(r.get("crop", ""), {})
            prow.append(dict(pag_pdf=n, id=lid, tipo=r["tipo"] if r["tipo"] != "AUTO" else "BAL",
                             testo_ocr=o.get("testo", ""), conf_ocr=o.get("conf", ""),
                             capienza=r.get("capienza", 0), righe=",".join(map(str, r.get("righe", []))),
                             aperto="sì" if r.get("aperto") else "", crop=r.get("crop", ""), rid=r["rid"],
                             _crop=r.get("crop", "")))
        if not prow:
            prow.append(dict(pag_pdf=n, id="", tipo="VUOTA", rid=f"{pid}_vuota", _crop=""))
        # più etichette sullo stesso blocco (es. 2a/2b nello stesso balloon): segnalalo al traduttore
        by_crop = {}
        for r in prow:
            if r["_crop"] and r["tipo"] == "BAL":
                by_crop.setdefault(r["_crop"], []).append(r["id"])
        for r in prow:
            ids = by_crop.get(r["_crop"], [])
            r["condiviso"] = ",".join(i for i in ids if i != r["id"]) if len(ids) > 1 else ""
        prow.sort(key=lambda r: (r["tipo"] == "SFX", id_sort_key(r["id"])))
        rows += prow
    out = WORK / "chapters" / cid / "source.tsv"
    write_tsv(out, COLS, rows)
    print(f"{cid}: {len(rows)} righe → {out.relative_to(WORK.parent)} · etichette non lette {unread} · pagine senza rilevamento {missing}")


if __name__ == "__main__":
    main()
