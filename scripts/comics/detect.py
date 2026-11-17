"""Passo 2 — trova i testi, l'ordine di lettura e misura i balloon (fumetti occidentali, testo orizzontale).

Uso:  python3 scripts/detect.py <capitolo>          (es. albo1; vedi config/chapters.json; "all" = tutto)
      python3 scripts/detect.py --pages 3 4 --debug

Per ogni pagina scrive work/detect/pNNN.json; per ogni testo:
  rid, id (numero in ordine di lettura, o etichetta a mano), tipo (BAL / DID), vignetta, riquadro del testo,
  righe del testo originale (dal livello di testo del PDF, se c'è), altezza riga e larghezze utili del balloon
  in pixel (`bande_px`: una per riga, dall'alto). La conversione in caratteri italiani si fa in build_inputs.py,
  usando la larghezza media dei caratteri del lettering originale (il lettering originale fa da righello).

Metodo (OpenCV, nessun modello):
  - testi: dal livello di testo del PDF se c'è; altrimenti componenti scure piccole su fondo chiaro, unite in
    righe e poi in blocchi;
  - vignette: tagli ricorsivi lungo i canali bianchi (XY-cut); ordine di lettura: vignette dall'alto in basso e
    da sinistra a destra (config reading_order = "rtl" per l'ordine giapponese), poi testi dall'alto in basso;
  - balloon: area connessa del colore di fondo del testo (bianco nei balloon, giallo nelle didascalie…),
    larghezza utile riga per riga;
  - etichette a mano (labels_mode = "hand"): come nel kit manga, numeri blu e lettere rosse. Solo per pagine in
    bianco e nero: nei fumetti a colori il blu e il rosso del disegno sembrerebbero etichette.
"""
import argparse
import sys

import cv2
import numpy as np

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from common import WORK, chapter_by_id, lettering_cfg, load_json, page_ids, save_json


# ---------- etichette a mano (solo labels_mode = "hand") ----------
def label_masks(im, cfg):
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    sat = (s > 80) & (v > 60)
    tc = cfg["label_colors"]["text"]
    blue = sat & (h >= tc["hue_min"]) & (h <= tc["hue_max"])
    red = np.zeros_like(blue)
    for lo, hi in cfg["label_colors"]["sfx"]["hue_ranges"]:
        red |= sat & (h >= lo) & (h <= hi)
    return blue.astype(np.uint8), red.astype(np.uint8)


def label_boxes(mask, S, min_area):
    d = cv2.dilate(mask * 255, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(25 * S) | 1, int(25 * S) | 1)))
    n, _, st, _ = cv2.connectedComponentsWithStats(d)
    return [[int(v) for v in st[i][:4]] for i in range(1, n) if st[i][4] >= min_area]


def box_dist(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    dx = max(bx - (ax + aw), ax - (bx + bw), 0)
    dy = max(by - (ay + ah), ay - (by + bh), 0)
    return (dx * dx + dy * dy) ** 0.5


# ---------- testo ----------
def text_blocks(gray, S):
    """Blocchi di testo orizzontale scuro su fondo chiaro (balloon, didascalie)."""
    H, W = gray.shape
    dark = (gray < 110).astype(np.uint8)
    light = (gray > 190).astype(np.uint8)
    ii = cv2.integral(light)

    def lr(x0, y0, x1, y1):
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
        return (ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]) / max((x1 - x0) * (y1 - y0), 1)

    n, lab, st, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    keep = np.zeros_like(dark)
    p = int(6 * S)
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if h > 45 * S or w > 60 * S or h < 4 * S or a < 6:
            continue
        if lr(x - p, y - p, x + w + p, y + h + p) < 0.55:
            continue
        keep[y:y + h, x:x + w][lab[y:y + h, x:x + w] == i] = 1
    lines = cv2.dilate(keep, cv2.getStructuringElement(cv2.MORPH_RECT, (int(13 * S), int(3 * S))))
    blk = cv2.dilate(lines, cv2.getStructuringElement(cv2.MORPH_RECT, (int(5 * S), int(14 * S))))
    m, _, bst, _ = cv2.connectedComponentsWithStats(blk)
    blocks = []
    for i in range(1, m):
        x, y, w, h, a = bst[i]
        ink = keep[y:y + h, x:x + w]
        if ink.sum() < 150 * S * S or w < 20 * S:
            continue
        nc = cv2.connectedComponents(ink)[0] - 1
        if nc < 3 or lr(x, y, x + w, y + h) < 0.5:
            continue
        blocks.append(dict(box=[int(x), int(y), int(w), int(h)], righe=None))
    return blocks, keep


def line_metrics(keep, box, S):
    """Righe del testo originale nel blocco: altezza di riga e larghezza in px di ogni riga."""
    x, y, w, h = box
    sub = keep[y:y + h, x:x + w] if keep is not None else None
    if sub is None or sub.sum() == 0:
        return None, []
    rows = sub.any(axis=1)
    runs, start = [], None
    for i, v in enumerate(list(rows) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start >= 4 * S:
                runs.append((start, i))
            start = None
    if not runs:
        return None, []
    widths = []
    for a, b in runs:
        cols = np.nonzero(sub[a:b].any(axis=0))[0]
        widths.append(int(cols[-1] - cols[0] + 1) if len(cols) else 0)
    if len(runs) >= 2:
        lh = float(np.median([runs[i + 1][0] - runs[i][0] for i in range(len(runs) - 1)]))
    else:
        lh = (runs[0][1] - runs[0][0]) * 1.25
    return lh, widths


# ---------- vignette e ordine di lettura ----------
def panels(gray, S, rtl=False):
    ink = (gray < 235).astype(np.uint8)
    H, W = ink.shape
    gap = int(8 * S)
    out = []

    def gaps(profile):
        segs, start = [], None
        empty = profile < 0.01
        for i, e in enumerate(list(empty) + [True]):
            if not e and start is None:
                start = i
            elif e and start is not None:
                segs.append((start, i))
                start = None
        merged = []
        for s in segs:
            if merged and s[0] - merged[-1][1] < gap:
                merged[-1] = (merged[-1][0], s[1])
            else:
                merged.append(s)
        return [s for s in merged if s[1] - s[0] > 20 * S]

    def cut(x0, y0, x1, y1, depth):
        sub = ink[y0:y1, x0:x1]
        if depth > 6 or sub.size == 0:
            out.append([x0, y0, x1 - x0, y1 - y0])
            return
        rows = gaps(sub.mean(axis=1))
        if len(rows) > 1:
            for a, b in rows:
                cut(x0, y0 + a, x1, y0 + b, depth + 1)
            return
        cols = gaps(sub.mean(axis=0))
        if len(cols) > 1:
            for a, b in (reversed(cols) if rtl else cols):
                cut(x0 + a, y0, x0 + b, y1, depth + 1)
            return
        out.append([x0, y0, x1 - x0, y1 - y0])

    cut(0, 0, W, H, 0)
    return [p for p in out if p[2] > 60 * S and p[3] > 60 * S] or [[0, 0, W, H]]


def panel_of(box, pans):
    cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
    for i, (x, y, w, h) in enumerate(pans):
        if x <= cx <= x + w and y <= cy <= y + h:
            return i
    return min(range(len(pans)), key=lambda i: box_dist(box, pans[i]))


def reading_sort(items, pans, S, rtl=False):
    for it in items:
        it["vignetta"] = panel_of(it["box"], pans)
    items.sort(key=lambda it: (it["vignetta"], it["box"][1]))
    # stessa altezza (±30 px a 200 dpi) → prima quello a sinistra (a destra per rtl)
    changed = True
    while changed:
        changed = False
        for i in range(len(items) - 1):
            a, b = items[i], items[i + 1]
            if a["vignetta"] == b["vignetta"] and abs(a["box"][1] - b["box"][1]) < 30 * S:
                if (b["box"][0] < a["box"][0]) != rtl and b["box"][0] != a["box"][0]:
                    items[i], items[i + 1] = b, a
                    changed = True
    return items


# ---------- misura del balloon ----------
def measure(im, keep, box, lh, cfg, S):
    H, W = im.shape[:2]
    x, y, w, h = box
    sub = im[y:y + h, x:x + w].reshape(-1, 3)
    txt = keep[y:y + h, x:x + w].reshape(-1) > 0 if keep is not None else np.zeros(len(sub), bool)
    bg = np.median(sub[~txt], axis=0) if (~txt).sum() > 10 else np.array([255, 255, 255])
    same = (np.abs(im.astype(np.int16) - bg.astype(np.int16)).sum(axis=2) < 60).astype(np.uint8)
    same[y:y + h, x:x + w] = 1
    same = cv2.erode(same, np.ones((3, 3), np.uint8))
    same[y:y + h, x:x + w] = 1
    lh = lh or 30 * S
    mx, my = int(max(1.0 * w, 4 * lh)), int(max(1.0 * h, 3 * lh))
    x0, y0, x1, y1 = max(0, x - mx), max(0, y - my), min(W, x + w + mx), min(H, y + h + my)
    win = same[y0:y1, x0:x1]
    _, lab = cv2.connectedComponents(win, connectivity=4)
    region = (lab == lab[y + h // 2 - y0, x + w // 2 - x0]).astype(np.uint8)
    edges = [region[0, :].mean(), region[-1, :].mean(), region[:, 0].mean(), region[:, -1].mean()]
    aperto = sum(edges) / 4 > 0.2 or region.sum() > 12 * w * h
    ys, xs = np.nonzero(region)
    rect = region.sum() / max(1, (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1))
    inside = (cv2.erode(region, np.ones((int(5 * S) | 1,) * 2, np.uint8)), (x0, y0))
    if aperto:
        # testo su fondo aperto: la larghezza delle righe originali + un po' di margine
        return dict(balloon=[x, y, w, h], bande_px=[], aperto=True, rettangolo=False, lh_px=round(lh, 1), _inside=None)
    # didascalie (riquadri): margine minimo; balloon tondi: margine proporzionale alla riga
    pad = max(1, int(2 * S)) if rect > 0.9 else max(1, int(cfg["padding_em"] * lh))
    inner = cv2.erode(region, np.ones((2 * pad + 1, 2 * pad + 1), np.uint8))
    ys, xs = np.nonzero(inner)
    if len(ys) == 0:
        return dict(balloon=[x, y, w, h], bande_px=[], aperto=False, rettangolo=bool(rect > 0.9), lh_px=round(lh, 1),
                    _inside=inside)
    top, bot = ys.min(), ys.max()
    lhi = lh * cfg["leading_it"]
    n = int((bot - top + 1) // lhi)
    if n == 0 and (bot - top + 1) >= 0.8 * lh:
        n, lhi = 1, float(bot - top + 1)
    off = top + ((bot - top + 1) - n * lhi) / 2
    bande = []
    for k in range(n):
        # riga utile = larghezza a metà della riga (come la usa il letterista), non il minimo su tutta la banda
        mid = inner[int(off + (k + 0.5) * lhi)]
        ok = mid > 0
        best = cur = 0
        for v in ok:
            cur = cur + 1 if v else 0
            best = max(best, cur)
        bande.append(int(best))
    return dict(balloon=[int(xs.min() + x0 - pad), int(top + y0 - pad), int(xs.max() - xs.min() + 2 * pad),
                         int(bot - top + 2 * pad)], bande_px=bande, aperto=False, rettangolo=bool(rect > 0.9),
                lh_px=round(lhi, 1), _inside=inside)


def detect_page(pid, cfg, debug=False):
    im = cv2.imread(str(WORK / "pages" / f"{pid}.png"))
    if im is None:
        sys.exit(f"Manca work/pages/{pid}.png: esegui prima scripts/render.py")
    H, W = im.shape[:2]
    S = cfg["render_dpi"] / 200.0
    rtl = cfg.get("reading_order", "ltr") == "rtl"
    hand = cfg.get("labels_mode", "auto") == "hand"
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    if hand:
        blue, red = label_masks(im, cfg)
        gray[(blue | red) > 0] = 255
    tl = load_json(WORK / "textlayer" / f"{pid}.json", {}) or {}
    own, keep = text_blocks(gray, S)
    if tl.get("blocks"):
        items = [dict(box=b["box"], righe=b["righe"], fonte="pdf") for b in tl["blocks"]]
    else:
        items = [dict(box=b["box"], righe=None, fonte="ocr") for b in own]
    pans = panels(gray, S, rtl)

    def metrics(it):
        if it["righe"]:
            hs = [r["box"][3] for r in it["righe"]]
            ys = [r["box"][1] for r in it["righe"]]
            lh = float(np.median(np.diff(ys))) if len(ys) > 1 else float(np.median(hs)) * 1.2
            return lh, [r["box"][2] for r in it["righe"]]
        return line_metrics(keep, it["box"], S)

    for it in items:
        it["lh"], it["src_px"] = metrics(it)
        it["m"] = measure(im, keep, it["box"], it["lh"], cfg, S)
    # blocchi di testo nello stesso balloon (il rilevatore a volte spezza un testo): uniscili
    merged = True
    while merged:
        merged = False
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                if a["m"]["aperto"] or b["m"]["aperto"] or a["fonte"] != b["fonte"]:
                    continue
                ba, bb = a["m"]["balloon"], b["m"]["balloon"]
                ix = max(0, min(ba[0] + ba[2], bb[0] + bb[2]) - max(ba[0], bb[0]))
                iy = max(0, min(ba[1] + ba[3], bb[1] + bb[3]) - max(ba[1], bb[1]))
                if ix * iy > 0.6 * min(ba[2] * ba[3], bb[2] * bb[3]):
                    x0 = min(a["box"][0], b["box"][0]); y0 = min(a["box"][1], b["box"][1])
                    x1 = max(a["box"][0] + a["box"][2], b["box"][0] + b["box"][2])
                    y1 = max(a["box"][1] + a["box"][3], b["box"][1] + b["box"][3])
                    first, second = (a, b) if a["box"][1] <= b["box"][1] else (b, a)
                    a["box"] = [x0, y0, x1 - x0, y1 - y0]
                    a["righe"] = (first["righe"] or []) + (second["righe"] or []) or None
                    a["lh"], a["src_px"] = metrics(a)
                    a["m"] = measure(im, keep, a["box"], a["lh"], cfg, S)
                    items.pop(j)
                    merged = True
                    break
            if merged:
                break
    items = reading_sort(items, pans, S, rtl)
    crops = WORK / "crops"
    crops.mkdir(parents=True, exist_ok=True)
    regions = []
    for n, it in enumerate(items, start=1):
        x, y, w, h = it["box"]
        m = dict(it["m"])
        inside = m.pop("_inside", None)
        crop = f"{pid}_t{x}x{y}x{w}x{h}.png"
        if inside is not None and it["fonte"] == "ocr":
            # ritaglio largo, ripulito con l'interno del balloon: tutto il testo (accenti, lettere ai bordi),
            # niente contorno, coda o disegno
            g = int(max(6 * S, 0.8 * (it["lh"] or 30 * S)))
            box = (max(0, x - g), max(0, y - g), min(W, x + w + g), min(H, y + h + g))
            piece = gray[box[1]:box[3], box[0]:box[2]].copy()
            reg, (ox, oy) = inside
            full = np.zeros(gray.shape, np.uint8)
            full[oy:oy + reg.shape[0], ox:ox + reg.shape[1]] = reg
            piece[full[box[1]:box[3], box[0]:box[2]] == 0] = 255
        else:
            g = int(6 * S)
            piece = gray[max(0, y - g):y + h + g, max(0, x - g):x + w + g].copy()
            if keep is not None and it["fonte"] == "ocr":
                km = cv2.dilate(keep, np.ones((int(13 * S) | 1, int(17 * S) | 1), np.uint8))
                piece[km[max(0, y - g):y + h + g, max(0, x - g):x + w + g] == 0] = 255
        cv2.imwrite(str(crops / crop), piece)
        regions.append(dict(rid=f"{pid}_A{n:02d}", id=str(n), tipo="DID" if m["rettangolo"] else "BAL",
                            vignetta=it["vignetta"] + 1, testo=it["box"], crop=crop, fonte=it["fonte"],
                            righe_testo=[r["testo"] for r in it["righe"]] if it["righe"] else None,
                            righe_px_orig=it["src_px"], **m))
    if hand:
        S2 = int(400 * S * S)
        lb_text = label_boxes(blue, S, S2)
        lb_sfx = [b for b in label_boxes(red, S, S2) if b[1] < H * (1 - cfg["ignore_red_bottom_fraction"])]
        cand = [(1 / (1 + box_dist(lb, r["testo"]) / (60 * S)), li, k)
                for li, lb in enumerate(lb_text) for k, r in enumerate(regions) if box_dist(lb, r["testo"]) <= 200 * S]
        cand.sort(key=lambda c: -c[0])
        used_l, by_region = set(), {}
        for v, li, k in cand:
            if li in used_l:
                continue
            used_l.add(li)
            by_region.setdefault(k, []).append(li)
        hand_regions = []
        for k, lis in by_region.items():
            for li in lis:
                r = dict(regions[k])
                r["rid"] = f"{pid}_L{li:02d}"
                r["label_box"] = lb_text[li]
                r["label_crop"] = f"{pid}_L{li:02d}.png"
                lx, ly, lw, lh2 = lb_text[li]
                cv2.imwrite(str(crops / r["label_crop"]), im[ly:ly + lh2, lx:lx + lw])
                hand_regions.append(r)
        for si, lb in enumerate(lb_sfx):
            lx, ly, lw, lh2 = lb
            name = f"{pid}_S{si:02d}.png"
            cv2.imwrite(str(crops / name), im[ly:ly + lh2, lx:lx + lw])
            ctx = f"{pid}_s{si:02d}.jpg"
            cv2.imwrite(str(crops / ctx), im[max(0, ly - 2 * lh2):ly + 3 * lh2, max(0, lx - 2 * lw):lx + 3 * lw])
            hand_regions.append(dict(rid=f"{pid}_S{si:02d}", tipo="SFX", label_box=lb, label_crop=name, crop=ctx,
                                     testo=None, bande_px=[], aperto=True))
        regions = hand_regions
    # effetti sonori scritti come testo (corpo molto più grande del resto della pagina)
    lhs = [r["lh_px"] for r in regions if r.get("lh_px")]
    if lhs:
        med = float(np.median(lhs))
        for r in regions:
            if r.get("lh_px") and r["lh_px"] > 1.8 * med and r.get("tipo") != "SFX":
                r["tipo"] = "SFX"
    page = dict(pid=pid, size=[W, H], vignette=pans, regions=regions)
    save_json(WORK / "detect" / f"{pid}.json", page)
    if debug:
        ov = im.copy()
        for i, p in enumerate(pans):
            cv2.rectangle(ov, (p[0], p[1]), (p[0] + p[2], p[1] + p[3]), (255, 0, 255), 3)
        for r in regions:
            if r.get("testo"):
                x, y, w, h = r["testo"]
                cv2.rectangle(ov, (x, y), (x + w, y + h), (0, 160, 0), 3)
                bx, by, bw, bh = r["balloon"]
                cv2.rectangle(ov, (bx, by), (bx + bw, by + bh), (200, 120, 0), 2)
                cv2.putText(ov, str(r.get("id", "")), (x - 30, y + 25), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 230), 3)
        (WORK / "debug").mkdir(exist_ok=True)
        cv2.imwrite(str(WORK / "debug" / f"{pid}.jpg"), cv2.resize(ov, None, fx=0.4, fy=0.4))
    return page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chapter", nargs="?")
    ap.add_argument("--pages", nargs="*", type=int)
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()
    cfg = lettering_cfg()
    if a.chapter:
        c = chapter_by_id(a.chapter)
        pids = page_ids(c["first"], c["last"])
    elif a.pages:
        pids = [f"p{n:03d}" for n in a.pages]
    else:
        sys.exit(__doc__)
    tot = dict(testi=0, pdf=0, aperti=0, vignette=0)
    for pid in pids:
        p = detect_page(pid, cfg, a.debug)
        tot["vignette"] += len(p["vignette"])
        for r in p["regions"]:
            if r.get("testo"):
                tot["testi"] += 1
                tot["pdf"] += r.get("fonte") == "pdf"
                tot["aperti"] += bool(r.get("aperto"))
    print(f"{a.chapter or 'pagine'}: {len(pids)} pagine · vignette {tot['vignette']} · testi {tot['testi']} "
          f"(dal PDF {tot['pdf']}, da OCR {tot['testi'] - tot['pdf']}) · fuori balloon/aperti {tot['aperti']}")
    if cfg.get("labels_mode", "auto") == "hand" and a.chapter:
        from sheets import build
        build(a.chapter)


if __name__ == "__main__":
    main()
