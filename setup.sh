#!/usr/bin/env bash
# Installazione del kit in un ambiente Python isolato (.venv) dentro la cartella del kit.
# Uso:  bash setup.sh                 dipendenze comuni (manga e fumetti)
#       bash setup.sh --manga-ocr     + manga-ocr, l'OCR consigliato per i manga (~2,5 GB con PyTorch)
#       bash setup.sh --reset         cancella e ricrea .venv (es. dopo un aggiornamento di Python)
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
if [[ " $* " == *" --reset "* ]]; then rm -rf .venv; fi
if [ ! -x .venv/bin/python ]; then
  echo "Creo .venv con $($PY --version)…"
  "$PY" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip -q
.venv/bin/python -m pip install -r requirements.txt
if [[ " $* " == *" --manga-ocr "* ]]; then
  .venv/bin/python -m pip install manga-ocr
fi
echo
echo "Programmi di sistema (non stanno nella .venv):"
echo "  macOS:  brew install poppler tesseract tesseract-lang"
echo "  Linux:  apt install poppler-utils tesseract-ocr tesseract-ocr-jpn-vert tesseract-ocr-fra tesseract-ocr-spa …"
echo
KIT_MODE=manga .venv/bin/python scripts/setup_check.py
echo
echo "Fatto. Avvia Claude Code da questa cartella: gli script e gli agenti usano bin/py, cioè la .venv."
