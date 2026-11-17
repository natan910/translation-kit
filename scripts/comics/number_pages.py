"""Tavole numerate: un PDF leggero con il numero di ogni testo accanto al suo balloon.

Uso:  python3 scripts/number_pages.py <capitolo|all> "Titolo"   → output/<titolo>_tavole_numerate.pdf

Serve al redattore (per controllare l'ordine di lettura automatico) e al letterista (per sapere dove va ogni
riga del copione). Con le etichette a mano non serve: i numeri sono già sulle tavole.
"""
import re
import sys

from PIL import Image, ImageDraw, ImageFont

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import OUTPUT, WORK, chapter_by_id, load_json, page_ids


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    c = chapter_by_id(sys.argv[1])
    title = sys.argv[2]
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    pages = []
    for pid in page_ids(c["first"], c["last"]):
        prev = WORK / "preview" / f"{pid}.jpg"
        det = load_json(WORK / "detect" / f"{pid}.json")
        if not prev.exists() or not det:
            continue
        im = Image.open(prev).convert("RGB")
        sc = im.width / det["size"][0]
        d = ImageDraw.Draw(im)
        for r in det["regions"]:
            if not r.get("testo"):
                continue
            x, y, w, h = [v * sc for v in r["testo"]]
            label = str(r.get("id", ""))
            cx, cy = max(14, x - 14), max(14, y - 4)
            d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=(0, 70, 200))
            d.text((cx, cy), label, fill="white", font=font, anchor="mm")
            d.rectangle([x, y, x + w, y + h], outline=(0, 70, 200), width=2)
        d.text((10, im.height - 30), f"p. {int(pid[1:])}", fill=(200, 0, 0), font=font)
        pages.append(im)
    if not pages:
        sys.exit("Nessuna pagina: esegui prima render.py e detect.py")
    OUTPUT.mkdir(exist_ok=True)
    out = OUTPUT / (re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_") + f"_{c['id']}_tavole_numerate.pdf")
    pages[0].save(out, save_all=True, append_images=pages[1:], resolution=96)
    print(f"{len(pages)} tavole numerate → {out.relative_to(OUTPUT.parent)}")


if __name__ == "__main__":
    main()
