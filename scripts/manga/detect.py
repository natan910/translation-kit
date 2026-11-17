"""Passo 2 — trova le annotazioni del redattore, i blocchi di testo, e misura i balloon.

Uso:  python3 scripts/detect.py <capitolo>        (es. cap45; usa config/chapters.json)
      python3 scripts/detect.py --pages 40 41 --debug

Per ogni pagina scrive work/detect/pNNN.json con, per ogni regione:
  rid, tipo (BAL = numero blu, SFX = lettera rossa, AUTO = blocco senza etichetta),
  label_crop (ritaglio dell'etichetta a mano, da leggere con l'agente label-reader),
  bbox del testo, bbox del balloon, corpo stimato, capienza in caratteri italiani,
  caratteri per riga (forma del balloon), aperto (balloon non chiuso / testo fuori balloon).
Poi crea i fogli etichette del capitolo in work/sheets/ (un'immagine leggera con tutte le etichette).

Metodo (solo OpenCV, niente modelli):
  - etichette: pixel blu (testi) e rossi (SFX) del redattore; il rosso in fondo pagina è il numero di pagina
  - testo: componenti scure piccole circondate da bianco, unite in colonne e poi in blocchi
  - ogni etichetta blu è assegnata al blocco di testo più vicino; i blocchi senza etichetta sono scartati
    (se la pagina non ha etichette blu, i blocchi restano come AUTO, numerati in ordine di lettura)
  - balloon: area bianca connessa attorno al blocco, limitata a una finestra; capienza = righe da
    line_height × caratteri che stanno nella larghezza utile di ogni riga (balloon ovali → righe corte in alto e in basso)
"""
import argparse
import sys

import cv2
import numpy as np

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import WORK, chapter_by_id, lettering_cfg, page_ids, save_json, load_json


def masks(im, cfg):
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    sat = (s > 80) & (v > 60)
    tc = cfg["label_colors"]["text"]
    blue = sat & (h >= tc["hue_min"]) & (h <= tc["hue_max"])
    red = np.zeros_like(blue)
    for lo, hi in cfg["label_colors"]["sfx"]["hue_ranges"]:
        red |= sat & (h >= lo) & (h <= hi)
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    gray[sat] = 255  # le annotazioni colorate non devono sembrare inchiostro
    return blue.astype(np.uint8), red.astype(np.uint8), gray


def label_boxes(mask, S, min_area):
    d = cv2.dilate(mask * 255, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(25 * S) | 1, int(25 * S) | 1)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(d)
    out = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a >= min_area:
            out.append([int(x), int(y), int(w), int(h)])
    return out


def text_blocks(gray, S, dark_thr=140, white_thr=200):
    H, W = gray.shape
    dark = (gray < dark_thr).astype(np.uint8)
    whiteish = (gray > white_thr).astype(np.uint8)
    ii = cv2.integral(whiteish)

    def wr(x0, y0, x1, y1):
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(W, x1), min(H, y1)
        a = max((x1 - x0) * (y1 - y0), 1)
        return (ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]) / a

    n, lab, st, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    keep = np.zeros_like(dark)
    p = int(10 * S)
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if w > 60 * S or h > 60 * S or a < 4:
            continue
        if wr(x - p, y - p, x + w + p, y + h + p) < 0.62:
            continue
        keep[y:y + h, x:x + w][lab[y:y + h, x:x + w] == i] = 1
    col = cv2.dilate(keep, cv2.getStructuringElement(cv2.MORPH_RECT, (int(9 * S), int(30 * S))))
    blk = cv2.dilate(col, cv2.getStructuringElement(cv2.MORPH_RECT, (int(22 * S), int(9 * S))))
    m, _, bst, _ = cv2.connectedComponentsWithStats(blk)
    blocks = []
    for i in range(1, m):
        x, y, w, h, a = bst[i]
        if keep[y:y + h, x:x + w].sum() < 240 * S * S or (w < 25 * S and h < 25 * S):
            continue
        if wr(x, y, x + w, y + h) < 0.55:
            continue
        blocks.append([int(x), int(y), int(w), int(h)])
    return blocks, keep


def text_score(keep, b, S):
    """Quanto un blocco somiglia a testo giapponese: tante componenti piccole, in colonne regolari."""
    x, y, w, h = b
    sub = keep[y:y + h, x:x + w]
    n, _, st, _ = cv2.connectedComponentsWithStats(sub)
    glyphs = sum(1 for i in range(1, n) if st[i][4] >= 6 * S * S)
    proj = sub.sum(axis=0) > 0
    cols = int(np.sum(np.diff(proj.astype(np.int8)) == 1) + (1 if proj[0] else 0))
    fill = sub.mean()
    score = glyphs * (1.0 if 0.04 <= fill <= 0.45 else 0.3) * (1.2 if h > 1.3 * w or cols >= 2 else 1.0)
    return float(score)


def glyph_size(keep, b, S):
    """Colonna più larga del blocco ≈ corpo dell'ideogramma (la furigana è più stretta)."""
    x, y, w, h = b
    proj = keep[y:y + h, x:x + w].sum(axis=0) > 0
    runs, cur = [], 0
    for v in proj:
        if v:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    runs = [r for r in runs if r >= 8 * S]
    if not runs:
        return None
    return float(min(max(runs), 60 * S))


def box_dist(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    dx = max(bx - (ax + aw), ax - (bx + bw), 0)
    dy = max(by - (ay + ah), ay - (by + bh), 0)
    return (dx * dx + dy * dy) ** 0.5


def measure(gray, b, font, cfg, S):
    H, W = gray.shape
    x, y, w, h = b
    white = (gray > 170).astype(np.uint8)
    white[y:y + h, x:x + w] = 1
    white = cv2.erode(white, np.ones((max(2, int(3 * S)),) * 2, np.uint8))
    white[y:y + h, x:x + w] = 1
    mx, my = int(max(1.5 * w, 6 * font)), int(max(1.0 * h, 6 * font))
    x0, y0, x1, y1 = max(0, x - mx), max(0, y - my), min(W, x + w + mx), min(H, y + h + my)
    sub = white[y0:y1, x0:x1]
    n, lab = cv2.connectedComponents(sub, connectivity=4)
    cl = lab[(y + h // 2) - y0, (x + w // 2) - x0]
    region = (lab == cl).astype(np.uint8)
    edges = [region[0, :].mean(), region[-1, :].mean(), region[:, 0].mean(), region[:, -1].mean()]
    # balloon chiuso = la zona bianca non arriva al bordo della finestra di misura
    # (una coda del balloon tocca il bordo con una frazione piccola; una fuga nello sfondo con una grande)
    aperto = sum(edges) / 4 > 0.2 or region.sum() > 10 * w * h
    itf0 = cfg["it_font_vs_jp_glyph"] * font
    if aperto:
        # testo fuori balloon o balloon aperto: la forma non è misurabile; solo una stima per area
        # (il testo italiano può allargarsi in orizzontale), nessuna riga per la prova di impaginazione
        area = (w + 2 * font) * (h + 2 * font)
        cap = int(area / (cfg["char_width_em"] * itf0 * cfg["line_height_em"] * itf0) * 0.6)
        return dict(balloon=[int(x - font), int(y - font), int(w + 2 * font), int(h + 2 * font)],
                    capienza=cap, righe=[], aperto=True, corpo_px=round(itf0, 1))
    itf = cfg["it_font_vs_jp_glyph"] * font
    pad = max(1, int(cfg["padding_em"] * itf))
    inner = cv2.erode(region, np.ones((2 * pad + 1, 2 * pad + 1), np.uint8))
    ys, xs = np.nonzero(inner)
    if len(ys) == 0:
        return dict(balloon=[x, y, w, h], capienza=0, righe=[], aperto=aperto, corpo_px=round(itf, 1))
    top, bot = ys.min(), ys.max()
    lh = cfg["line_height_em"] * itf
    cw = cfg["char_width_em"] * itf
    nlines = int((bot - top + 1) // lh)
    off = top + ((bot - top + 1) - nlines * lh) / 2
    righe = []
    for k in range(nlines):
        band = inner[int(off + k * lh):int(off + (k + 1) * lh)]
        if band.size == 0:
            continue
        rowok = band.all(axis=0)
        best = cur = 0
        for v in rowok:
            cur = cur + 1 if v else 0
            best = max(best, cur)
        c = int(best // cw)
        if c >= 2:
            righe.append(c)
    bx, by = xs.min() + x0, ys.min() + y0
    bw, bh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    return dict(balloon=[int(bx - pad), int(by - pad), int(bw + 2 * pad), int(bh + 2 * pad)],
                capienza=int(sum(righe)), righe=righe, aperto=bool(aperto), corpo_px=round(itf, 1))


def reading_order(blocks, S):
    """Ordine di lettura giapponese approssimato: fasce dall'alto, da destra a sinistra. Solo per pagine senza etichette."""
    bands = []
    for b in sorted(blocks, key=lambda b: b[1]):
        cy = b[1] + b[3] / 2
        for band in bands:
            if abs(band[0] - cy) < 150 * S:
                band[1].append(b)
                break
        else:
            bands.append([cy, [b]])
    out = []
    for _, bl in bands:
        out += sorted(bl, key=lambda b: -(b[0] + b[2]))
    return out


def detect_page(pid, cfg, debug=False):
    im = cv2.imread(str(WORK / "pages" / f"{pid}.png"))
    if im is None:
        sys.exit(f"Manca work/pages/{pid}.png: esegui prima scripts/render.py")
    H, W = im.shape[:2]
    S = cfg["render_dpi"] / 200.0
    blue, red, gray = masks(im, cfg)
    min_area = int(400 * S * S)
    lb_text = label_boxes(blue, S, min_area)
    lb_sfx = [b for b in label_boxes(red, S, min_area)
              if b[1] < H * (1 - cfg["ignore_red_bottom_fraction"])]
    blocks, keep = text_blocks(gray, S)
    # secondo passaggio: fondo retinato chiaro (soglie più morbide) e testo bianco su nero (immagine invertita)
    extra = []
    for g2, dt, wt in ((gray, 110, 160), (255 - gray, 140, 200)):
        b2, k2 = text_blocks(g2, S, dt, wt)
        for b in b2:
            if all(box_dist(b, o) > 4 * S for o in blocks + [e[0] for e in extra]):
                extra.append((b, k2))
    n_primary = len(blocks)
    for b, k2 in extra:
        x, y, w, h = b
        keep[y:y + h, x:x + w] |= k2[y:y + h, x:x + w]
        blocks.append(b)
    scores = [text_score(keep, b, S) * (1.0 if i < n_primary else 0.5) for i, b in enumerate(blocks)]
    sizes = [glyph_size(keep, b, S) for b in blocks]
    good = [z for z, sc in zip(sizes, scores) if z and sc >= 8]
    page_font = float(np.median(good)) if good else 32 * S
    crops = WORK / "crops"
    crops.mkdir(parents=True, exist_ok=True)
    regions = []

    # assegna le etichette blu ai blocchi di testo: abbinamento globale, il migliore per primo.
    # Un blocco che ha già un'etichetta vale meno per la successiva (due etichette sullo stesso balloon,
    # tipo 2a/2b, restano possibili ma solo se non c'è un blocco migliore vicino).
    cand = []
    for li, lb in enumerate(lb_text):
        for k, b in enumerate(blocks):
            d = box_dist(lb, b)
            if d <= 200 * S and scores[k] >= 4:
                cand.append((scores[k] ** 0.5 / (1 + d / (60 * S)), li, k))
    assigned, taken, load = {}, set(), {}
    while cand:
        cand.sort(key=lambda c: -c[0] * (0.35 ** load.get(c[2], 0)))
        v, li, k = cand.pop(0)
        if li in taken:
            continue
        assigned.setdefault(k, []).append(li)
        taken.add(li)
        load[k] = load.get(k, 0) + 1
        cand = [c for c in cand if c[1] != li]
    auto = cfg.get("labels_mode", "hand") == "auto"
    used_blocks = sorted(assigned) if not auto else list(range(len(blocks)))
    if auto:
        used_blocks = [j for j in used_blocks if scores[j] >= 8]
        order = reading_order([blocks[j] for j in used_blocks], S)
        used_blocks = [blocks.index(b) for b in order]

    def save_crop(img, box, name, grow):
        x, y, w, h = box
        g = int(grow)
        c = img[max(0, y - g):min(H, y + h + g), max(0, x - g):min(W, x + w + g)]
        cv2.imwrite(str(crops / name), c)
        return name

    rn = 0
    for j in used_blocks:
        b = blocks[j]
        font = sizes[j] if sizes[j] and 0.75 * page_font <= sizes[j] <= 1.6 * page_font else page_font
        m = measure(gray, b, font, cfg, S)
        # nome legato alla posizione del blocco: se il rilevamento cambia, cambia il nome e l'OCR si rifà
        text_crop = save_crop(gray, b, f"{pid}_t{b[0]}x{b[1]}x{b[2]}x{b[3]}.png", 6 * S)
        labs = assigned.get(j, [None])
        for li in labs:
            rn += 1
            # rid stabile: legato all'etichetta (che dipende solo dall'inchiostro colorato), non al blocco di testo
            rid = f"{pid}_L{li:02d}" if li is not None else f"{pid}_A{rn:02d}"
            reg = dict(rid=rid, tipo="BAL" if li is not None else "AUTO",
                       auto_id=str(rn) if li is None else "", testo=b, crop=text_crop, **m)
            if li is not None:
                reg["label_box"] = lb_text[li]
                reg["label_crop"] = save_crop(im, lb_text[li], f"{pid}_L{li:02d}.png", 4 * S)
            regions.append(reg)
    unassigned = [lb_text[i] for i in range(len(lb_text)) if not any(i in v for v in assigned.values())]
    for li, lb in enumerate(lb_text):
        if lb in unassigned:
            rn += 1
            regions.append(dict(rid=f"{pid}_L{li:02d}", tipo="BAL", testo=None, crop="", capienza=0, righe=[],
                                aperto=True, label_box=lb,
                                label_crop=save_crop(im, lb, f"{pid}_L{li:02d}.png", 4 * S),
                                nota="etichetta senza testo vicino: testo non trovato dal rilevatore"))
    for si, lb in enumerate(lb_sfx):
        rn += 1
        x, y, w, h = lb
        ctx = [x - 2 * w, y - 2 * h, 5 * w, 5 * h]
        regions.append(dict(rid=f"{pid}_S{si:02d}", tipo="SFX", testo=None,
                            crop=save_crop(im, [max(0, ctx[0]), max(0, ctx[1]), ctx[2], ctx[3]], f"{pid}_s{si:02d}.jpg", 0),
                            label_box=lb, label_crop=save_crop(im, lb, f"{pid}_S{si:02d}.png", 4 * S),
                            capienza=0, righe=[], aperto=True))
    page = dict(pid=pid, size=[W, H], n_text_labels=len(lb_text), n_sfx_labels=len(lb_sfx),
                n_blocks_found=len(blocks), regions=regions)
    save_json(WORK / "detect" / f"{pid}.json", page)
    if debug:
        ov = im.copy()
        for r in regions:
            if r.get("testo"):
                x, y, w, h = r["testo"]
                cv2.rectangle(ov, (x, y), (x + w, y + h), (0, 160, 0), 3)
                x, y, w, h = r["balloon"]
                cv2.rectangle(ov, (x, y), (x + w, y + h), (200, 120, 0), 2)
                cv2.putText(ov, str(r["capienza"]), (x, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 220), 3)
        (WORK / "debug").mkdir(exist_ok=True)
        cv2.imwrite(str(WORK / "debug" / f"{pid}.jpg"), cv2.resize(ov, None, fx=0.45, fy=0.45))
    return page


def label_sheets(cid, pids, cell=(132, 112), cols=8, rows=7):
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chapter", nargs="?")
    ap.add_argument("--pages", nargs="*", type=int)
    ap.add_argument("--debug", action="store_true", help="salva sovrapposizioni in work/debug/")
    a = ap.parse_args()
    cfg = lettering_cfg()
    if a.chapter:
        c = chapter_by_id(a.chapter)
        pids = page_ids(c["first"], c["last"])
    elif a.pages:
        pids = [f"p{n:03d}" for n in a.pages]
    else:
        sys.exit(__doc__)
    tot = dict(text=0, sfx=0, unmatched=0, aperti=0)
    for pid in pids:
        p = detect_page(pid, cfg, a.debug)
        tot["text"] += p["n_text_labels"]
        tot["sfx"] += p["n_sfx_labels"]
        tot["unmatched"] += sum(1 for r in p["regions"] if r.get("nota"))
        tot["aperti"] += sum(1 for r in p["regions"] if r["tipo"] == "BAL" and r["aperto"])
    if a.chapter:
        sheets, n = label_sheets(a.chapter, pids)
        print(f"{a.chapter}: {len(pids)} pagine · etichette testo {tot['text']} · SFX {tot['sfx']} · "
              f"senza testo vicino {tot['unmatched']} · balloon aperti/fuori balloon {tot['aperti']} · "
              f"fogli etichette {len(sheets)} ({n} ritagli)")
    else:
        print(tot)


if __name__ == "__main__":
    main()
