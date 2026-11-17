"""Passo 4 — costruisce il copione sorgente di un capitolo/albo per il traduttore.

Uso:  python3 scripts/build_inputs.py <capitolo>

Unisce rilevamento, livello di testo / OCR ed eventuali etichette a mano. Per ogni testo calcola la capienza in
caratteri italiani usando il lettering originale come righello: larghezza media di un carattere originale
(px della riga / caratteri della riga) × it_font_vs_source → caratteri per ogni riga utile del balloon.

Scrive work/chapters/<capitolo>/source.tsv con:
  pag_pdf, id, tipo, vignetta, testo_originale, conf, fonte (pdf/ocr), lung_orig (caratteri dell'originale),
  capienza, righe (caratteri italiani per riga, dall'alto), aperto, crop, rid
"""
import statistics
import sys

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import WORK, chapter_by_id, id_sort_key, lettering_cfg, load_json, page_ids, write_tsv

COLS = ["pag_pdf", "id", "tipo", "vignetta", "testo_originale", "conf", "fonte", "lung_orig", "capienza", "righe",
        "aperto", "crop", "rid"]


def char_width(lines, px):
    lines = [l for l in (lines or []) if l.strip()]
    if lines and px and len(lines) == len(px):
        n = sum(len(l) for l in lines)
        return sum(px) / n if n else None
    if lines and px:
        return max(px) / max(len(l) for l in lines)
    return None


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cid = sys.argv[1]
    c = chapter_by_id(cid)
    cfg = lettering_cfg()
    hand = cfg.get("labels_mode", "auto") == "hand"
    labels = load_json(WORK / "labels" / f"{cid}.json", {}) if hand else {}
    rows, unread = [], 0
    for pid in page_ids(c["first"], c["last"]):
        page = load_json(WORK / "detect" / f"{pid}.json")
        n = int(pid[1:])
        if not page:
            continue
        ocr = load_json(WORK / "ocr" / f"{pid}.json", {})
        pr = []
        widths = []
        for r in page["regions"]:
            o = ocr.get(r.get("crop", ""), {})
            lines = r.get("righe_testo") or o.get("righe") or []
            text = " ".join(r["righe_testo"]) if r.get("righe_testo") else o.get("testo", "")
            cw = char_width(lines, r.get("righe_px_orig"))
            if cw:
                widths.append(cw)
            pr.append((r, text, cw, o.get("conf", "") if r.get("fonte") == "ocr" else ""))
        page_cw = statistics.median(widths) if widths else None
        prow = []
        for r, text, cw, conf in pr:
            cw = cw or page_cw
            righe = []
            if cw and r.get("bande_px"):
                cwi = cw * cfg["it_font_vs_source"]
                righe = [int(b // cwi) for b in r["bande_px"]]
                righe = [x for x in righe if x >= 2]
            if hand:
                lid = str(labels.get(r["rid"], "")).strip()
                if not lid:
                    lid = "?" + r["rid"].split("_")[1]
                    unread += 1
            else:
                lid = r["id"]
            prow.append(dict(pag_pdf=n, id=lid, tipo=r.get("tipo", "BAL"), vignetta=r.get("vignetta", ""),
                             testo_originale=text, conf=conf, fonte=r.get("fonte", ""), lung_orig=len(text),
                             capienza=sum(righe) if righe else "", righe=",".join(map(str, righe)),
                             aperto="sì" if r.get("aperto") else "", crop=r.get("crop", ""), rid=r["rid"]))
        if not prow:
            prow.append(dict(pag_pdf=n, id="", tipo="VUOTA", rid=f"{pid}_vuota"))
        if hand:
            prow.sort(key=lambda r: (r["tipo"] == "SFX", id_sort_key(r["id"])))
        rows += prow
    out = WORK / "chapters" / cid / "source.tsv"
    write_tsv(out, COLS, rows)
    measured = sum(1 for r in rows if r.get("righe"))
    texts = sum(1 for r in rows if r["tipo"] not in ("VUOTA",))
    print(f"{cid}: {texts} testi → {out.relative_to(WORK.parent)} · con misura del balloon {measured}"
          + (f" · etichette non lette {unread}" if hand else ""))


if __name__ == "__main__":
    main()
