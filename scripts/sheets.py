"""Fogli etichette per l'agente label-reader (solo labels_mode = "hand").

Uso:  python3 scripts/sheets.py <capitolo>
"""
import sys

import cv2
import numpy as np

from common import WORK, chapter_by_id, load_json, page_ids, save_json


def build_sheets(cid, pids, cell=(132, 112), cols=8, rows=7):
    """Fogli leggeri con tutte le etichette di un capitolo per l'agente label-reader.

    Una riga per pagina: la prima cella dice la pagina, le altre sono i ritagli numerati (n) in ordine di
    posizione. Vedere tutte le etichette di una pagina insieme aiuta a leggere la sequenza (1, 2a, 2b, 3…)."""
    lines = []  # ogni riga: (pagina, [(n, rid, tipo, crop)])
    n = 0
    for pid in pids:
        page = load_json(WORK / "detect" / f"{pid}.json")
        if not page:
            continue
        items = [r for r in page["regions"] if r.get("label_crop")]
        items.sort(key=lambda r: (r["tipo"] == "SFX", r["label_box"][1] // 150, -r["label_box"][0]))
        per = cols - 1
        for i in range(0, len(items), per):
            chunk = []
            for r in items[i:i + per]:
                n += 1
                chunk.append((n, r["rid"], r["tipo"], r["label_crop"]))
            lines.append((int(pid[1:]), chunk, i > 0))
    out = WORK / "sheets"
    out.mkdir(parents=True, exist_ok=True)
    cw, ch = cell
    sheets = []
    for si in range(0, len(lines), rows):
        block = lines[si:si + rows]
        sheet = np.full((rows * ch, cols * cw, 3), 255, np.uint8)
        index = []
        for ri, (pg, chunk, cont) in enumerate(block):
            y = ri * ch
            cv2.putText(sheet, f"p{pg}" + ("+" if cont else ""), (6, y + ch // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
            cv2.line(sheet, (0, y + ch - 1), (cols * cw, y + ch - 1), (160, 160, 160), 1)
            for ci, (num, rid, tipo, crop) in enumerate(chunk, start=1):
                img = cv2.imread(str(WORK / "crops" / crop))
                if img is None:
                    continue
                sc = min((cw - 8) / img.shape[1], (ch - 24) / img.shape[0], 1.0)
                img = cv2.resize(img, None, fx=sc, fy=sc)
                y0, x0 = y + 20, ci * cw + 4
                sheet[y0:y0 + img.shape[0], x0:x0 + img.shape[1]] = img
                cv2.putText(sheet, str(num), (ci * cw + 3, y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                cv2.rectangle(sheet, (ci * cw, y), (ci * cw + cw - 1, y + ch - 1), (215, 215, 215), 1)
                index.append(dict(n=num, rid=rid, tipo=tipo, pagina=pg))
        name = f"{cid}_etichette_{si // rows + 1:02d}.png"
        cv2.imwrite(str(out / name), sheet)
        sheets.append(dict(sheet=name, items=index))
    save_json(out / f"{cid}_index.json", sheets)
    return sheets, n



def build(cid):
    c = chapter_by_id(cid)
    sheets, n = build_sheets(c["id"], page_ids(c["first"], c["last"]))
    print(f"{c['id']}: {len(sheets)} fogli etichette, {n} ritagli → work/sheets/")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    build(sys.argv[1])
