"""Passo 1 — PDF → immagini di lavoro.

Uso:  python3 scripts/render.py input/volume.pdf

Crea:
  work/pages/pNNN.png    pagina a risoluzione di lavoro (render_dpi in config/lettering.json)
  work/preview/pNNN.jpg  anteprima leggera per gli agenti (preview_width_px), ~600 token a pagina
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image

from common import WORK, lettering_cfg


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pdf = Path(sys.argv[1])
    cfg = lettering_cfg()
    pages = WORK / "pages"
    prev = WORK / "preview"
    pages.mkdir(parents=True, exist_ok=True)
    prev.mkdir(parents=True, exist_ok=True)
    if not any(pages.glob("p*.png")):
        print(f"Render di {pdf.name} a {cfg['render_dpi']} dpi…", flush=True)
        subprocess.run(["pdftoppm", "-r", str(cfg["render_dpi"]), "-png", str(pdf), str(pages / "p")], check=True)
    # pdftoppm scrive p-001.png / p-0001.png a seconda del numero di pagine: normalizza in pNNN.png
    for f in sorted(pages.glob("p-*.png")):
        n = int(f.stem.split("-")[1])
        f.rename(pages / f"p{n:03d}.png")
    w = cfg["preview_width_px"]
    count = 0
    for f in sorted(pages.glob("p*.png")):
        out = prev / f"{f.stem}.jpg"
        if out.exists():
            continue
        im = Image.open(f).convert("RGB")
        im.thumbnail((w, w * 2))
        im.save(out, quality=78)
        count += 1
    total = len(list(pages.glob("p*.png")))
    print(f"Pagine: {total} (nuove anteprime: {count})")


if __name__ == "__main__":
    main()
