"""Controlli automatici (zero token) tra un passo e l'altro.

Uso:
  python3 scripts/qa.py <capitolo> --stage traduzione
      controlla traduzione.tsv contro source.tsv e prepara editor_input.tsv: traduzione + misure del balloon +
      prova di impaginazione della traduzione grezza (fit_trad, proposta_trad). È l'unico input dell'editor.
  python3 scripts/qa.py <capitolo> --stage adattamento
      controlla adattamento.tsv: colonne, stati, id mancanti, termini vietati dal glossario, e rifà la prova di
      impaginazione. Scrive qa.tsv con le sole righe da correggere (l'editor le sistema in un secondo giro breve).

Stampa un riepilogo di poche righe. Codice di uscita 1 se ci sono errori di formato.
"""
import argparse
import re
import sys

from common import CONFIG, ED_COLS, STATI, WORK, chapter_by_id, load_json, read_tsv, write_tsv
from fit import judge

EDITOR_INPUT_COLS = ["pag_pdf", "folio", "id", "tipo", "vignetta", "personaggio", "originale", "traduzione",
                     "note_traduttore", "lung_orig", "lung_trad", "capienza", "righe", "aperto", "fit_trad", "proposta_trad"]


def glossary_rules():
    p = CONFIG / "glossary.tsv"
    if not p.exists():
        return []
    rules = []
    for g in read_tsv(p)[1]:
        for bad in [b.strip() for b in g.get("vietate", "").split(",") if b.strip()]:
            rules.append((re.compile(r"(?<!\w)" + re.escape(bad) + r"(?!\w)"), bad, g["italiano"]))
    return rules


def key(r):
    return (str(int(r["pag_pdf"])), r["id"].strip())


def parse_righe(s):
    return [int(x) for x in str(s).split(",") if x.strip().isdigit()]


def stage_traduzione(cid, cdir, offset):
    _, src = read_tsv(cdir / "source.tsv")
    h, tr = read_tsv(cdir / "traduzione.tsv")
    errors = []
    need = ["pag_pdf", "id", "tipo", "originale", "italiano"]
    if any(c not in h for c in need):
        sys.exit(f"traduzione.tsv: colonne mancanti {[c for c in need if c not in h]}")
    srcmap = {key(r): r for r in src if r["tipo"] != "VUOTA"}
    seen = {key(r) for r in tr}
    missing = [k for k in srcmap if k not in seen and not k[1].startswith("?")]
    rules = glossary_rules()
    out, fits = [], {"OK": 0, "STRETTO": 0, "LUNGO": 0, "": 0}
    for r in tr:
        s = srcmap.get(key(r), {})
        righe = parse_righe(s.get("righe", ""))
        j = judge(r.get("italiano", ""), righe) if r.get("tipo") not in ("SFX", "VUOTA") else dict(stato="", proposta="")
        fits[j["stato"]] = fits.get(j["stato"], 0) + 1
        for rx, bad, good in rules:
            if rx.search(r.get("italiano", "")):
                errors.append(f"p{r['pag_pdf']}-{r['id']}: «{bad}» → usare «{good}»")
        folio = r.get("folio") or (str(int(r["pag_pdf"]) + offset) if offset is not None else "")
        out.append(dict(pag_pdf=r["pag_pdf"], folio=folio, id=r["id"], tipo=r.get("tipo", ""),
                        vignetta=s.get("vignetta", ""), personaggio=r.get("personaggio", ""),
                        originale=r.get("originale", ""), traduzione=r.get("italiano", ""),
                        note_traduttore=r.get("note_traduttore", ""),
                        lung_orig=len(r.get("originale", "")), lung_trad=len(r.get("italiano", "").replace(" / ", " ")),
                        capienza=s.get("capienza", ""), righe=s.get("righe", ""), aperto=s.get("aperto", ""),
                        fit_trad=j["stato"], proposta_trad=j.get("proposta", "")))
    write_tsv(cdir / "editor_input.tsv", EDITOR_INPUT_COLS, out)
    print(f"{cid} traduzione: {len(tr)} righe · id della sorgente non tradotti {len(missing)} · termini vietati {len(errors)}")
    print(f"  prova balloon sulla traduzione grezza: OK {fits['OK']} · STRETTO {fits['STRETTO']} · LUNGO {fits['LUNGO']} · senza misura {fits['']}")
    for e in (errors + [f"manca {k[0]}-{k[1]}" for k in missing])[:12]:
        print("  " + e)
    return 0


def stage_adattamento(cid, cdir):
    h, ad = read_tsv(cdir / "adattamento.tsv")
    if h[: len(ED_COLS)] != ED_COLS:
        print(f"adattamento.tsv: intestazione diversa da quella attesa:\n  {ED_COLS}")
        return 1
    _, ei = read_tsv(cdir / "editor_input.tsv")
    eimap = {key(r): r for r in ei}
    rules = glossary_rules()
    flagged, bad_state = [], 0
    stats = {}
    for r in ad:
        probs = []
        if r["stato"] not in STATI:
            bad_state += 1
            probs.append(f"stato non valido «{r['stato']}»")
        for rx, bad, good in rules:
            if rx.search(r["adattamento"]):
                probs.append(f"«{bad}» → «{good}»")
        src = eimap.get(key(r), {})
        righe = parse_righe(src.get("righe", ""))
        if r["tipo"] not in ("SFX", "VUOTA") and righe and r["adattamento"].strip():
            j = judge(r["adattamento"], righe)
            stats[j["stato"]] = stats.get(j["stato"], 0) + 1
            if j["stato"] == "LUNGO" and r["stato"] in ("OK", "STRETTO"):
                probs.append(f"la prova automatica dice LUNGO ({j['nota']}); l'editor ha messo {r['stato']}")
            elif j.get("nota") and j.get("proposta") and r["stato"] == "OK" and src.get("aperto") != "sì":
                probs.append(f"a capo: proposta «{j['proposta']}»")
        if key(r) not in eimap:
            probs.append("id non presente nell'input dell'editor (riga aggiunta?)")
        if probs:
            flagged.append(dict(pag_pdf=r["pag_pdf"], id=r["id"], adattamento=r["adattamento"], stato=r["stato"],
                                righe=src.get("righe", ""), problemi=" · ".join(probs)))
    missing = [k for k in eimap if k not in {key(r) for r in ad}]
    for k in missing:
        flagged.append(dict(pag_pdf=k[0], id=k[1], adattamento="", stato="", righe="", problemi="riga mancante nell'adattamento"))
    write_tsv(cdir / "qa.tsv", ["pag_pdf", "id", "adattamento", "stato", "righe", "problemi"], flagged)
    states = {s: sum(1 for r in ad if r["stato"] == s) for s in ("OK", "STRETTO", "LUNGO", "RIVEDERE")}
    print(f"{cid} adattamento: {len(ad)} righe · {states} · da correggere {len(flagged)} (qa.tsv) · righe mancanti {len(missing)}")
    print(f"  prova automatica: {stats}")
    return 1 if bad_state else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chapter")
    ap.add_argument("--stage", required=True, choices=["traduzione", "adattamento"])
    a = ap.parse_args()
    chapter_by_id(a.chapter)
    offset = (load_json(CONFIG / "chapters.json", {}) or {}).get("folio_offset")
    cdir = WORK / "chapters" / a.chapter
    rc = stage_traduzione(a.chapter, cdir, offset) if a.stage == "traduzione" else stage_adattamento(a.chapter, cdir)
    sys.exit(rc)


if __name__ == "__main__":
    main()
