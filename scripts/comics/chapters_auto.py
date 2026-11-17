"""Divide il volume in parti per lavorare in parallelo e scrive config/chapters.json (da confermare).

Uso:  python3 scripts/chapters_auto.py [pagine_per_parte]
  0 (default) = sceglie da solo: un albo fino a 64 pagine resta intero; oltre, parti da ~24 pagine
  (un albo franco-belga: 46–62 pagine; un comic book americano: ~22–24 pagine per numero).
Se config/chapters.json ha già parti scritte a mano (senza "auto": true) non lo tocca.
"""
import sys

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import CONFIG, WORK, load_json, save_json


def main():
    per = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    n = len(list((WORK / "pages").glob("p*.png")))
    data = load_json(CONFIG / "chapters.json", {}) or {}
    if data.get("chapters") and not data.get("auto"):
        print(f"config/chapters.json già compilato a mano ({len(data['chapters'])} parti): non lo tocco.")
        return
    if per <= 0:
        per = n if n <= 64 else 24
    parts = []
    for i, start in enumerate(range(1, n + 1, per), start=1):
        parts.append(dict(id=f"parte{i}", title=f"Parte {i}", first=start, last=min(n, start + per - 1)))
    data.update(chapters=parts, auto=True)
    data.setdefault("folio_offset", 0)
    save_json(CONFIG / "chapters.json", data)
    print(f"{n} pagine → {len(parts)} parti da {per} pagine (config/chapters.json, da confermare)")


if __name__ == "__main__":
    main()
