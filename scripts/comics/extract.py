"""Passo 1b — estrae il livello di testo del PDF, se c'è (file dei licenziatari, PDF digitali).

Uso:  python3 scripts/extract.py input/albo.pdf

Per ogni pagina scrive work/textlayer/pNNN.json: blocchi di testo con riquadro in pixel (alla risoluzione di lavoro),
righe con il loro testo e il loro riquadro. Testo esatto, posizioni esatte, nessun OCR.
Pagine senza testo nel PDF (scansioni) → file vuoto: passeranno dal rilevatore + OCR.
"""
import re
import subprocess
import sys
import tempfile
from html import unescape
from pathlib import Path

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import WORK, lettering_cfg, save_json

BOX = r'xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)"'


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pdf = sys.argv[1]
    dpi = lettering_cfg()["render_dpi"]
    sc = dpi / 72.0
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "bbox.html"
        subprocess.run(["pdftotext", "-bbox-layout", pdf, str(out)], check=True)
        html = out.read_text(encoding="utf-8", errors="replace")
    pages = re.findall(r"<page[^>]*>(.*?)</page>", html, flags=re.S)
    with_text = 0
    for n, body in enumerate(pages, start=1):
        blocks = []
        for b in re.finditer(r"<block " + BOX + r">(.*?)</block>", body, flags=re.S):
            lines = []
            for ln in re.finditer(r"<line " + BOX + r">(.*?)</line>", b.group(5), flags=re.S):
                words = [unescape(w) for w in re.findall(r"<word[^>]*>(.*?)</word>", ln.group(5), flags=re.S)]
                text = " ".join(words).strip()
                if text:
                    x0, y0, x1, y1 = (float(ln.group(i)) * sc for i in range(1, 5))
                    lines.append(dict(testo=text, box=[int(x0), int(y0), int(x1 - x0), int(y1 - y0)]))
            if lines:
                x0, y0, x1, y1 = (float(b.group(i)) * sc for i in range(1, 5))
                blocks.append(dict(box=[int(x0), int(y0), int(x1 - x0), int(y1 - y0)], righe=lines))
        if blocks:
            with_text += 1
        save_json(WORK / "textlayer" / f"p{n:03d}.json", dict(blocks=blocks))
    print(f"Livello di testo: {with_text}/{len(pages)} pagine con testo estraibile"
          + ("" if with_text else " (scansione: si userà rilevatore + OCR)"))


if __name__ == "__main__":
    main()
