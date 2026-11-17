"""Passo 2b — propone config/chapters.json cercando i titoli di capitolo (第N話) nell'OCR di tutto il volume.

Uso:  python3 scripts/chapters_guess.py [--write]
Senza --write stampa la proposta; con --write la salva (da far confermare al redattore).
Calcola anche folio_offset (pagina stampata − pagina PDF) se trova numeri di pagina nei metadati di detect.
"""
import argparse
import re

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import CONFIG, WORK, load_json, save_json

TITLE = re.compile(r"第\s*([0-9０-９一二三四五六七八九十百]+)\s*[話回章]")
KANJI = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def to_num(s):
    s = s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if s.isdigit():
        return int(s)
    total, cur = 0, 0
    for ch in s:
        if ch in KANJI:
            cur = KANJI[ch]
        elif ch == "十":
            total += (cur or 1) * 10
            cur = 0
        elif ch == "百":
            total += (cur or 1) * 100
            cur = 0
    return total + cur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    pages = sorted(WORK.glob("ocr/p*.json"))
    n = len(list((WORK / "pages").glob("p*.png")))
    starts = []
    for f in pages:
        pid = int(f.stem[1:])
        for v in load_json(f, {}).values():
            m = TITLE.search(v.get("testo", ""))
            if m:
                num = to_num(m.group(1))
                if not starts or starts[-1][1] != num:
                    starts.append((pid, num))
                break
    starts = [s for i, s in enumerate(starts) if i == 0 or s[1] > starts[i - 1][1]]
    chs = []
    if not starts:
        print("Nessun titolo di capitolo trovato: compilare config/chapters.json a mano.")
        return
    if starts[0][0] > 1:
        chs.append(dict(id="iniziali", title="Pagine iniziali", first=1, last=starts[0][0] - 1))
    for i, (p, num) in enumerate(starts):
        last = starts[i + 1][0] - 1 if i + 1 < len(starts) else n
        chs.append(dict(id=f"cap{num}", title=f"Cap. {num}", first=p, last=last))
    data = load_json(CONFIG / "chapters.json", {}) or {}
    data["chapters"] = chs
    for c in chs:
        print(f"  {c['id']}: pp. {c['first']}–{c['last']}")
    print("Attenzione: l'ultimo capitolo include eventuali extra finali (rubrica, galleria, colophon): separarli a mano se serve.")
    if a.write:
        save_json(CONFIG / "chapters.json", data)
        print("Scritto config/chapters.json")


if __name__ == "__main__":
    main()
