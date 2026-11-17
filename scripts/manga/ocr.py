"""Passo 3 — OCR dei blocchi di testo trovati da detect.py.

Uso:  python3 scripts/ocr.py <capitolo> [--engine auto|manga-ocr|tesseract]

Motori:
  manga-ocr   il migliore per i manga (testo verticale, furigana, font da fumetto). Installazione:
              pip install manga-ocr   (scarica un modello di ~450 MB la prima volta; CPU va bene)
  tesseract   ripiego, già presente su molte macchine: brew/apt install tesseract tesseract-lang
              (serve la lingua jpn_vert). Legge bene il testo pulito, peggio quello stilizzato,
              e a volte include la furigana: il traduttore la ripulisce.
  auto        manga-ocr se installato, altrimenti tesseract.

Scrive work/ocr/pNNN.json: {nome_ritaglio: {testo, conf, motore}}. Gli SFX disegnati non passano dall'OCR:
li legge il traduttore dal ritaglio (work/crops/pNNN_sKK.jpg).
"""
import argparse
import sys

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import WORK, chapter_by_id, load_json, page_ids, save_json

_mocr = None


def engine_available(name):
    if name == "manga-ocr":
        try:
            import manga_ocr  # noqa: F401
            return True
        except ImportError:
            return False
    if name == "tesseract":
        try:
            import pytesseract
            return "jpn_vert" in pytesseract.get_languages()
        except Exception:
            return False
    return False


def run_manga_ocr(path):
    global _mocr
    if _mocr is None:
        from manga_ocr import MangaOcr
        _mocr = MangaOcr()
    return _mocr(str(path)).strip(), ""


def strip_furigana(path):
    """Imbianca le colonne strette (furigana) accanto alle colonne di testo principali."""
    import cv2
    import numpy as np
    g = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    dark = g < 140
    proj = dark.any(axis=0)
    runs, start = [], None
    for x, v in enumerate(list(proj) + [False]):
        if v and start is None:
            start = x
        elif not v and start is not None:
            runs.append((start, x))
            start = None
    if not runs:
        return g
    widest = max(b - a for a, b in runs)
    for a, b in runs:
        if b - a < 0.6 * widest:
            g[:, a:b] = 255
    return g


def run_tesseract(path):
    import pytesseract
    from PIL import Image
    img = Image.fromarray(strip_furigana(path))
    d = pytesseract.image_to_data(img, lang="jpn_vert", config="--psm 5",
                                  output_type=pytesseract.Output.DICT)
    words, confs = [], []
    for t, c in zip(d["text"], d["conf"]):
        t = t.strip()
        if t and float(c) >= 0:
            words.append(t)
            confs.append(float(c))
    conf = round(sum(confs) / len(confs)) if confs else 0
    return "".join(words), conf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chapter", nargs="?")
    ap.add_argument("--pages", nargs="*", type=int)
    ap.add_argument("--engine", default="auto", choices=["auto", "manga-ocr", "tesseract"])
    a = ap.parse_args()
    eng = a.engine
    if eng == "auto":
        eng = "manga-ocr" if engine_available("manga-ocr") else "tesseract"
    if not engine_available(eng):
        sys.exit(f"Motore OCR '{eng}' non disponibile. Vedi le istruzioni in cima a scripts/ocr.py.")
    run = run_manga_ocr if eng == "manga-ocr" else run_tesseract
    if a.chapter:
        c = chapter_by_id(a.chapter)
        pids = page_ids(c["first"], c["last"])
    else:
        pids = [f"p{n:03d}" for n in (a.pages or [])]
    done = 0
    for pid in pids:
        page = load_json(WORK / "detect" / f"{pid}.json")
        if not page:
            continue
        outp = WORK / "ocr" / f"{pid}.json"
        res = load_json(outp, {})
        for r in page["regions"]:
            crop = r.get("crop")
            if r["tipo"] == "SFX" or not crop or crop in res:
                continue
            text, conf = run(WORK / "crops" / crop)
            res[crop] = dict(testo=text, conf=conf, motore=eng)
            done += 1
        save_json(outp, res)
    print(f"{a.chapter or 'pagine'}: OCR con {eng} su {done} blocchi")


if __name__ == "__main__":
    main()
