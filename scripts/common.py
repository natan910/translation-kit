"""Funzioni condivise dagli script del kit. Nessuna dipendenza oltre la libreria standard."""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
OUTPUT = ROOT / "output"
MODES = ("manga", "comics")


def active_mode():
    """Modo del lavoro in corso: manga (giapponese, testo verticale) o comics (lingue europee, testo orizzontale).
    Si sceglie con scripts/prep.sh o scripts/mode.py; si può forzare con la variabile d'ambiente KIT_MODE."""
    import os
    m = os.environ.get("KIT_MODE") or ((WORK / "mode").read_text().strip() if (WORK / "mode").exists() else "")
    if m not in MODES:
        sys.exit("Nessun modo attivo: esegui  bin/py scripts/mode.py manga  oppure  bin/py scripts/mode.py comics")
    return m


class _Config:
    """config/<modo>/ del lavoro attivo (glossario, guida di stile, lettering, lezioni apprese)."""
    def __truediv__(self, other):
        return ROOT / "config" / active_mode() / other

    def __str__(self):
        return str(ROOT / "config" / active_mode())

    __fspath__ = __str__


CONFIG = _Config()

# Colonne del copione, nell'ordine usato da tutti gli script e gli agenti.
SOURCE_COLS = ["pag_pdf", "id", "tipo", "testo_originale", "conf", "capienza", "righe", "aperto", "crop"]
TRAD_COLS = ["pag_pdf", "folio", "id", "tipo", "personaggio", "originale", "italiano", "note_traduttore"]
ED_COLS = ["pag_pdf", "folio", "id", "tipo", "personaggio", "originale", "traduzione",
           "adattamento", "capienza", "stato", "note_editor"]
STATI = {"OK", "STRETTO", "LUNGO", "RIVEDERE", ""}


def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def lettering_cfg():
    return load_json(CONFIG / "lettering.json")


def chapters():
    data = load_json(CONFIG / "chapters.json", {"chapters": []})
    return data["chapters"]


def chapter_by_id(cid):
    if cid == "all":
        n = len(list((WORK / "pages").glob("p*.png")))
        return {"id": "all", "title": "Tutto il volume", "first": 1, "last": n}
    for c in chapters():
        if c["id"] == cid:
            return c
    sys.exit(f"Capitolo '{cid}' non trovato in config/chapters.json")


def read_tsv(path):
    """Legge un TSV con intestazione. Tollera righe corte, scarta righe vuote."""
    p = Path(path)
    lines = p.read_text(encoding="utf-8").split("\n")
    if not lines or not lines[0].strip():
        return [], []
    header = lines[0].rstrip("\r").split("\t")
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        cells = ln.rstrip("\r").split("\t")
        cells += [""] * (len(header) - len(cells))
        rows.append(dict(zip(header, cells[: len(header)])))
    return header, rows


def write_tsv(path, header, rows):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as fh:
        fh.write("\t".join(header) + "\n")
        for r in rows:
            fh.write("\t".join(clean_cell(r.get(c, "")) for c in header) + "\n")


def clean_cell(v):
    return str(v).replace("\t", " ").replace("\r", " ").replace("\n", " / ")


def page_ids(first, last):
    return [f"p{n:03d}" for n in range(first, last + 1)]


def text_len(s):
    """Lunghezza del testo come la vede il letterista: senza i separatori di a capo."""
    return len(s.replace(" // ", " ").replace(" / ", " ").strip())


def id_sort_key(label):
    """Ordina 1, 2a, 2b, 3+, 10, x1 in modo naturale; le lettere SFX (a, b, …) dopo i numeri."""
    s = str(label)
    num = ""
    i = 0
    while i < len(s) and s[i].isdigit():
        num += s[i]
        i += 1
    if num:
        return (0, int(num), s[i:])
    return (1, 0, s)
