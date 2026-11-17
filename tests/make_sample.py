"""Crea un fumetto di prova (2 pagine a colori, testo francese) per verificare l'installazione del kit.

Uso:  python3 tests/make_sample.py
Crea  tests/sample_testo.pdf   (PDF con livello di testo, come i file dei licenzianti)
      tests/sample_scansione.pdf (solo immagini, come una scansione: passa dall'OCR)
      tests/sample_atteso.tsv  (testi e ordine di lettura attesi, per il controllo automatico)
"""
import io
import random
from pathlib import Path

from PIL import Image
from reportlab.lib.colors import Color, black, white
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H = 170 * mm, 260 * mm
M, G = 8 * mm, 4 * mm

PAGES = [
    # pannelli: (riga, colonna, colonne_nella_riga); testi in ordine di lettura atteso
    [
        dict(row=0, col=0, ncols=1, items=[("cap", "PARIS, 1954. UNE NUIT SANS LUNE."),
                                           ("bal", "TU AS ENTENDU CE BRUIT ?"),
                                           ("bal", "C'ÉTAIT SÛREMENT LE VENT... RENTRE VITE !")]),
        dict(row=1, col=0, ncols=2, items=[("bal", "LE VENT NE FRAPPE PAS AUX PORTES, MARCEL."),
                                           ("sfx", "TOC !")]),
        dict(row=1, col=1, ncols=2, items=[("bal", "QUI EST LÀ ?"), ("bal", "OUVREZ ! POLICE !")]),
        dict(row=2, col=0, ncols=1, items=[("bal", "LA POLICE ? À CETTE HEURE-CI ? JE N'Y CROIS PAS UNE SECONDE."),
                                           ("cap", "MARCEL AVAIT RAISON DE SE MÉFIER.")]),
    ],
    [
        dict(row=0, col=0, ncols=2, items=[("bal", "VOUS CHERCHEZ QUELQU'UN ?")]),
        dict(row=0, col=1, ncols=2, items=[("bal", "OUI. UN CERTAIN MARCEL DUPONT."), ("bal", "IL N'HABITE PLUS ICI.")]),
        dict(row=1, col=0, ncols=1, items=[("cap", "PENDANT CE TEMPS, SUR LES TOITS..."),
                                           ("bal", "ILS SONT DÉJÀ LÀ. IL FAUT PARTIR CETTE NUIT MÊME !")]),
        dict(row=2, col=0, ncols=3, items=[("bal", "ET LE TABLEAU ?")]),
        dict(row=2, col=1, ncols=3, items=[("bal", "ON LE LAISSE.")]),
        dict(row=2, col=2, ncols=3, items=[("bal", "JAMAIS !"), ("sfx", "BLAM !")]),
    ],
]


def wrap(text, font, size, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if pdfmetrics.stringWidth(cand, font, size) <= maxw:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def draw_page(c, panels, rnd):
    rows = 3
    ph = (H - 2 * M - (rows - 1) * G) / rows
    expected = []
    for pi, p in enumerate(panels):
        pw = (W - 2 * M - (p["ncols"] - 1) * G) / p["ncols"]
        x0 = M + p["col"] * (pw + G)
        y0 = H - M - (p["row"] + 1) * ph - p["row"] * G
        # fondo colorato e un po' di "disegno"
        c.setFillColor(Color(rnd.uniform(.55, .9), rnd.uniform(.55, .9), rnd.uniform(.6, .95)))
        c.setStrokeColor(black)
        c.setLineWidth(2)
        c.rect(x0, y0, pw, ph, fill=1, stroke=1)
        c.setLineWidth(1.2)
        for _ in range(14):
            c.setStrokeColor(Color(*(rnd.uniform(0, .35),) * 3))
            c.line(x0 + rnd.uniform(0, pw), y0 + rnd.uniform(0, ph * .45), x0 + rnd.uniform(0, pw), y0 + rnd.uniform(0, ph * .45))
        c.setFillColor(Color(.85, .55, .4))
        c.circle(x0 + pw * rnd.uniform(.3, .7), y0 + ph * .25, ph * .14, fill=1, stroke=1)
        # testi, dall'alto in basso, alternati sinistra/destra
        n = len(p["items"])
        for k, (kind, text) in enumerate(p["items"]):
            size = 9 if kind != "sfx" else 22
            cy = y0 + ph * (0.86 - k * 0.32 / max(1, n - 1)) if n > 1 else y0 + ph * .78
            if kind == "cap":
                tw = min(pw * .9, pdfmetrics.stringWidth(text, "Comic", size) + 10)
                lines = wrap(text, "Comic", size, tw - 8)
                bh = len(lines) * size * 1.15 + 6
                bx = x0 + 4 if k == 0 else x0 + pw - tw - 4
                by = y0 + ph - bh - 4 if k == 0 else y0 + 4
                c.setFillColor(Color(1, .95, .6))
                c.setStrokeColor(black)
                c.rect(bx, by, tw, bh, fill=1, stroke=1)
                c.setFillColor(black)
                for i, ln in enumerate(lines):
                    c.setFont("Comic", size)
                    c.drawString(bx + 4, by + bh - 4 - (i + 1) * size * 1.15 + 2, ln)
            elif kind == "bal":
                maxw = min(pw * .55, 46 * mm)
                lines = wrap(text, "Comic", size, maxw)
                tw = max(pdfmetrics.stringWidth(l, "Comic", size) for l in lines)
                th = len(lines) * size * 1.2
                cx = x0 + pw * (0.3 if k % 2 == 0 else 0.68)
                cx = min(max(cx, x0 + tw / 2 + 12), x0 + pw - tw / 2 - 12)
                rx, ry = tw / 2 + 10, th / 2 + 8
                cy = min(cy, y0 + ph - ry - 4)
                c.setFillColor(white)
                c.setStrokeColor(black)
                c.setLineWidth(1.5)
                path = c.beginPath()
                path.moveTo(cx - 6, cy - ry + 2)
                path.lineTo(cx - 14, cy - ry - 14)
                path.lineTo(cx + 6, cy - ry + 2)
                path.close()
                c.drawPath(path, fill=1, stroke=1)
                c.ellipse(cx - rx, cy - ry, cx + rx, cy + ry, fill=1, stroke=1)
                c.setFillColor(black)
                for i, ln in enumerate(lines):
                    c.setFont("Comic", size)
                    lw = pdfmetrics.stringWidth(ln, "Comic", size)
                    c.drawString(cx - lw / 2, cy + th / 2 - (i + 1) * size * 1.2 + 3, ln)
            else:  # sfx disegnato, grande e colorato
                c.setFillColor(Color(.85, .1, .1))
                c.setFont("Comic", size)
                c.drawString(x0 + pw * .55, y0 + ph * .45, text)
                continue
            expected.append((kind, text))
    return expected


def main():
    pdfmetrics.registerFont(TTFont("Comic", FONT))
    rnd = random.Random(7)
    out = HERE / "sample_testo.pdf"
    c = canvas.Canvas(str(out), pagesize=(W, H))
    exp = []
    for pn, panels in enumerate(PAGES, start=1):
        for kind, text in draw_page(c, panels, rnd):
            exp.append((pn, kind, text))
        c.showPage()
    c.save()
    # versione "scansione": stesse pagine come sole immagini
    import subprocess
    tmp = HERE / "_tmp"
    tmp.mkdir(exist_ok=True)
    subprocess.run(["pdftoppm", "-r", "150", "-png", str(out), str(tmp / "s")], check=True)
    imgs = [Image.open(f).convert("RGB") for f in sorted(tmp.glob("s-*.png"))]
    imgs[0].save(HERE / "sample_scansione.pdf", save_all=True, append_images=imgs[1:], resolution=150)
    for f in tmp.glob("*"):
        f.unlink()
    tmp.rmdir()
    with open(HERE / "sample_atteso.tsv", "w", encoding="utf-8") as fh:
        fh.write("pag_pdf\tid\ttipo\ttesto\n")
        counters = {}
        for pn, kind, text in exp:
            counters[pn] = counters.get(pn, 0) + 1
            fh.write(f"{pn}\t{counters[pn]}\t{'DID' if kind == 'cap' else 'BAL'}\t{text}\n")
    print("Creati tests/sample_testo.pdf, tests/sample_scansione.pdf, tests/sample_atteso.tsv")


if __name__ == "__main__":
    main()
