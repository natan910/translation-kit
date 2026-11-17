#!/usr/bin/env bash
# Sposta il lavoro in corso (work/) in archive/<nome>/ per iniziarne uno nuovo. Niente viene cancellato.
# Uso: bash scripts/archive.sh <nome>      es. bash scripts/archive.sh serie-vol01
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="${1:?Uso: bash scripts/archive.sh <nome>}"
mkdir -p archive
[ -e "archive/$NAME" ] && { echo "archive/$NAME esiste già"; exit 1; }
mv work "archive/$NAME" && mkdir work && touch work/.keep
echo "Lavoro archiviato in archive/$NAME; work/ è vuota."
