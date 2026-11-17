#!/usr/bin/env bash
# Preparazione del volume/albo, zero token.
# Uso: bash scripts/prep.sh manga  input/volume.pdf
#      bash scripts/prep.sh comics input/albo.pdf [pagine_per_parte]
set -euo pipefail
cd "$(dirname "$0")/.."
MODE="${1:?Uso: bash scripts/prep.sh manga|comics input/file.pdf}"
PDF="${2:?Uso: bash scripts/prep.sh manga|comics input/file.pdf}"
PY=bin/py
$PY scripts/mode.py "$MODE"
$PY scripts/render.py "$PDF"
if [ "$MODE" = "manga" ]; then
  $PY scripts/manga/detect.py all
  $PY scripts/manga/ocr.py all
  $PY scripts/manga/chapters_guess.py
  echo "Ora conferma i capitoli (bin/py scripts/manga/chapters_guess.py --write, poi correggi config/manga/chapters.json) e folio_offset."
else
  $PY scripts/comics/extract.py "$PDF"
  $PY scripts/comics/chapters_auto.py "${3:-0}"
  $PY scripts/comics/detect.py all
  $PY scripts/comics/ocr.py all
  echo "Ora controlla config/comics/chapters.json (parti) e config/comics/lettering.json (lingua, ordine di lettura, numerazione)."
fi
