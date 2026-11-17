"""Controlla che la macchina abbia tutto il necessario, per entrambi i modi.

Uso:  bin/py scripts/setup_check.py
"""
import importlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ok = True
venv = Path(sys.prefix).resolve() == (ROOT / ".venv").resolve()
print(f"  {'ok  ' if venv else '!!  '} Python: {sys.executable}" + ("" if venv else "  (non è la .venv del kit: usa bin/py, o bash setup.sh)"))
for mod, pip in [("cv2", "opencv-python"), ("numpy", "numpy"), ("scipy", "scipy"), ("PIL", "pillow"),
                 ("openpyxl", "openpyxl"), ("docx", "python-docx"), ("pytesseract", "pytesseract")]:
    try:
        importlib.import_module(mod)
        print(f"  ok   {pip}")
    except ImportError:
        ok = False
        print(f"  MANCA {pip}  →  bash setup.sh")
for exe in ("pdftoppm", "pdftotext", "tesseract"):
    if shutil.which(exe):
        print(f"  ok   {exe}")
    else:
        ok = False
        print(f"  MANCA {exe}  →  brew install poppler tesseract tesseract-lang  /  apt install poppler-utils tesseract-ocr")
try:
    import pytesseract
    langs = set(pytesseract.get_languages())
    need = {"manga": ["jpn_vert"]}
    c = json.loads((ROOT / "config" / "comics" / "lettering.json").read_text())
    need["comics"] = c["lingua_originale"].split("+")
    for mode, ls in need.items():
        for l in ls:
            print(f"  {'ok  ' if l in langs else 'MANCA'} tesseract {l} ({mode})")
except Exception as e:
    print("  ?    controllo lingue tesseract non riuscito:", e)
try:
    importlib.import_module("manga_ocr")
    print("  ok   manga-ocr (manga)")
except ImportError:
    print("  !!   manga-ocr non installato (manga): tesseract legge bene solo ~40% dei balloon. bash setup.sh --manga-ocr")
print("Tutto pronto." if ok else "Installare quanto manca e rilanciare.")
