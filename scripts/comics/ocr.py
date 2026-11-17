"""Passo 3 — OCR dei testi senza livello di testo PDF (scansioni).

Uso:  python3 scripts/ocr.py <capitolo>     (lingua da config/lettering.json, campo lingua_originale)

Tesseract con il pacchetto della lingua di partenza (fra, spa, eng, deu, por, nld…; più lingue: "fra+eng").
Il lettering dei fumetti è spesso tutto maiuscolo: tesseract lo legge bene se il font è regolare.
Scrive work/ocr/pNNN.json: {ritaglio: {testo, righe, conf}}. Le parole spezzate a fine riga con il trattino
vengono riunite nel campo testo (le righe restano come sono, servono a misurare il lettering).
I testi che arrivano dal livello di testo del PDF non passano dall'OCR.
"""
import argparse
import re
import sys

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import WORK, chapter_by_id, lettering_cfg, load_json, page_ids, save_json


def ocr_crop(path, lang):
    import pytesseract
    from PIL import Image
    img = Image.open(path)
    w, h = img.size
    if h < 120:  # i ritagli piccoli si leggono meglio ingranditi
        img = img.resize((w * 2, h * 2))
    d = pytesseract.image_to_data(img, lang=lang, config="--psm 6", output_type=pytesseract.Output.DICT)
    lines, confs, cur, key = [], [], [], None
    for i, t in enumerate(d["text"]):
        t = t.strip()
        k = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        if k != key and cur:
            lines.append(" ".join(cur))
            cur = []
        key = k
        if t and float(d["conf"][i]) >= 0:
            cur.append(t)
            confs.append(float(d["conf"][i]))
    if cur:
        lines.append(" ".join(cur))
    lines = [l for l in lines if l.strip()]
    text = " ".join(lines)
    text = re.sub(r"(\w)- (\w)", r"\1\2", text)  # parola spezzata a fine riga
    return text, lines, round(sum(confs) / len(confs)) if confs else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chapter")
    a = ap.parse_args()
    cfg = lettering_cfg()
    lang = cfg["lingua_originale"]
    try:
        import pytesseract
        missing = [l for l in lang.split("+") if l not in pytesseract.get_languages()]
    except Exception as e:
        sys.exit(f"tesseract non disponibile: {e}")
    if missing:
        sys.exit(f"Manca il pacchetto lingua tesseract: {', '.join(missing)} (es. apt install tesseract-ocr-{missing[0]})")
    c = chapter_by_id(a.chapter)
    done = 0
    for pid in page_ids(c["first"], c["last"]):
        page = load_json(WORK / "detect" / f"{pid}.json")
        if not page:
            continue
        outp = WORK / "ocr" / f"{pid}.json"
        res = load_json(outp, {})
        for r in page["regions"]:
            crop = r.get("crop")
            if not crop or r.get("fonte") == "pdf" or r.get("tipo") == "SFX" or crop in res:
                continue
            text, lines, conf = ocr_crop(WORK / "crops" / crop, lang)
            res[crop] = dict(testo=text, righe=lines, conf=conf)
            done += 1
        save_json(outp, res)
    print(f"{a.chapter}: OCR ({lang}) su {done} testi")


if __name__ == "__main__":
    main()
