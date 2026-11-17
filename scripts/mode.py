"""Sceglie il modo del lavoro: manga (giapponese, testo verticale) o comics (lingue europee, testo orizzontale).

Uso:  bin/py scripts/mode.py manga | comics      (senza argomenti: mostra il modo attivo)
Il modo decide quale config usare (config/manga/ o config/comics/) e quali script di rilevamento/OCR.
Un lavoro alla volta per cartella: se work/ contiene un lavoro dell'altro modo, archivialo prima (scripts/archive.sh).
"""
import sys

from common import MODES, WORK

if len(sys.argv) < 2:
    m = (WORK / "mode").read_text().strip() if (WORK / "mode").exists() else "(nessuno)"
    sys.exit(f"Modo attivo: {m}")
m = sys.argv[1]
if m not in MODES:
    sys.exit(__doc__)
old = (WORK / "mode").read_text().strip() if (WORK / "mode").exists() else ""
busy = any((WORK / d).exists() and any((WORK / d).iterdir()) for d in ("pages", "chapters"))
if old and old != m and busy:
    sys.exit(f"work/ contiene un lavoro in modo «{old}». Archivialo prima:  bash scripts/archive.sh <nome>")
WORK.mkdir(exist_ok=True)
(WORK / "mode").write_text(m)
print(f"Modo attivo: {m} (config/{m}/)")
