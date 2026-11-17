"""Passo 4b — converte la lettura dei fogli etichette in work/labels/<capitolo>.json.

L'agente label-reader scrive work/labels/<capitolo>_raw.tsv con due colonne:  n<TAB>etichetta
(n = numero stampato sopra il ritaglio nel foglio; etichetta = ciò che è scritto a mano: 1, 2a, 10, b, …; "?" se illeggibile).
Questo script lo traduce in {rid: etichetta} usando work/sheets/<capitolo>_index.json.

Uso:  python3 scripts/labels_apply.py <capitolo>
"""
import sys

from common import WORK, load_json, read_tsv, save_json


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cid = sys.argv[1]
    index = load_json(WORK / "sheets" / f"{cid}_index.json")
    if index is None:
        sys.exit("Manca l'indice dei fogli: esegui prima scripts/detect.py " + cid)
    n2rid = {it["n"]: it["rid"] for sh in index for it in sh["items"]}
    _, rows = read_tsv(WORK / "labels" / f"{cid}_raw.tsv")
    out, bad = {}, []
    for r in rows:
        try:
            n = int(r["n"])
        except (ValueError, KeyError):
            continue
        lab = r.get("etichetta", "").strip()
        if n in n2rid and lab and lab != "?":
            out[n2rid[n]] = lab
        elif n in n2rid:
            bad.append(n)
    missing = sorted(set(n2rid) - {int(r["n"]) for r in rows if r.get("n", "").isdigit()})
    save_json(WORK / "labels" / f"{cid}.json", out)
    print(f"{cid}: {len(out)}/{len(n2rid)} etichette lette · illeggibili {len(bad)} · mancanti {len(missing)}")
    if bad or missing:
        print("  da controllare (n):", ", ".join(map(str, (bad + missing)[:40])))


if __name__ == "__main__":
    main()
