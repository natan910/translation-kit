"""Prova di impaginazione: fa stare un testo italiano nelle righe misurate di un balloon.

Le righe misurate (campo `righe`, caratteri per riga dall'alto in basso) seguono la forma del balloon:
in un ovale le righe in alto e in basso sono corte. Il testo va centrato verticalmente, quindi si prova
ogni finestra di k righe consecutive, partendo da k piccolo.

Uso da riga di comando:  python3 scripts/fit.py "Testo da provare" 8,11,13,13,12,9
"""
import sys

from common import lettering_cfg


def _wrap(words, widths):
    lines, i = [], 0
    for w in widths:
        line = ""
        while i < len(words):
            cand = words[i] if not line else line + " " + words[i]
            if len(cand) <= w:
                line = cand
                i += 1
            else:
                break
        lines.append(line)
    return lines if i == len(words) and all(lines) else None


def best_wrap(text, righe):
    """Restituisce (righe_usate, testo_a_capo) con il minor numero di righe, centrate; None se non entra."""
    words = text.replace(" // ", " ").replace(" / ", " ").split()
    if not words:
        return 0, ""
    n = len(righe)
    for k in range(1, n + 1):
        starts = sorted(range(0, n - k + 1), key=lambda s: abs((s + k / 2) - n / 2))
        for s in starts:
            res = _wrap(words, righe[s:s + k])
            if res:
                return k, " / ".join(res)
    return None


def editor_breaks_fit(text, righe):
    """Le andate a capo scelte dall'editor (" / ") entrano in qualche finestra centrata di righe?"""
    lines = [ln.strip() for ln in text.replace(" // ", " / ").split(" / ") if ln.strip()]
    n, k = len(righe), len(lines)
    if k == 0 or k > n:
        return False
    for s in sorted(range(0, n - k + 1), key=lambda s: abs((s + k / 2) - n / 2)):
        if all(len(l) <= w for l, w in zip(lines, righe[s:s + k])):
            return True
    return False


def judge(text, righe, cfg=None):
    """Stato automatico: OK / STRETTO / LUNGO, con proposta di a capo. Stato vuoto se non c'è misura."""
    cfg = cfg or lettering_cfg()
    if not righe or not text.strip():
        return dict(stato="", proposta="", nota="nessuna misura del balloon")
    if len(righe) < cfg.get("min_lines_for_verdict", 1) or max(righe) < 4:
        return dict(stato="", proposta="", nota="balloon piccolo: misura poco affidabile")
    r = best_wrap(text, righe)
    if r is None:
        sc = cfg.get("min_font_scale", 1.0)
        if sc < 1.0:
            wider = [int(x / sc) for x in righe]
            more = wider + wider[-1:] * max(0, int(len(righe) / sc) - len(righe))
            r2 = best_wrap(text, more)
            if r2 is not None:
                return dict(stato="STRETTO", proposta=r2[1], righe_usate=r2[0],
                            nota=f"entra solo con il corpo ridotto al {int(sc * 100)}%")
        return dict(stato="LUNGO", proposta="",
                    nota=f"non entra nelle {len(righe)} righe misurate (max {max(righe)} car./riga)")
    k, wrapped = r
    # STRETTO = il testo riempie davvero il balloon: caratteri / capienza totale oltre tight_ratio
    fill = len(text.replace(" // ", " ").replace(" / ", " ")) / max(sum(righe), 1)
    if fill > cfg["tight_ratio"]:
        stato = "STRETTO"
    else:
        stato = "OK"
    if editor_breaks_fit(text, righe):
        nota = ""
    elif " / " in text:
        nota = "gli a capo dell'editor non seguono la forma: vedi proposta"
    else:
        nota = "servono degli a capo: vedi proposta"
    return dict(stato=stato, proposta=wrapped, nota=nota, righe_usate=k)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    print(judge(sys.argv[1], [int(x) for x in sys.argv[2].split(",")]))
