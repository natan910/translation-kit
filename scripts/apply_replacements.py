"""Applica sostituzioni di armonizzazione decise dal redattore a tutti gli adattamenti (zero token).

Uso:  python3 scripts/apply_replacements.py work/final/armonizzazione.tsv [--dry-run]
TSV con colonne: cerca, sostituisci, colonne (es. "adattamento,personaggio"), parola_intera (sì/no)
Scrive il registro in work/final/sostituzioni.log.
"""
import argparse
import re

from common import WORK, chapters, read_tsv, write_tsv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tsv")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    _, rules = read_tsv(a.tsv)
    log, total = [], 0
    for c in chapters():
        p = WORK / "chapters" / c["id"] / "adattamento.tsv"
        if not p.exists():
            continue
        header, rows = read_tsv(p)
        for r in rows:
            for rule in rules:
                pat = re.escape(rule["cerca"])
                if rule.get("parola_intera", "sì").lower().startswith("s"):
                    pat = r"(?<!\w)" + pat + r"(?!\w)"
                for col in [x.strip() for x in rule.get("colonne", "adattamento").split(",")]:
                    new, n = re.subn(pat, rule["sostituisci"], r.get(col, ""))
                    if n:
                        log.append(f"p{r['pag_pdf']}-{r['id']} [{col}] {r[col]} → {new}")
                        r[col] = new
                        total += n
        if not a.dry_run:
            write_tsv(p, header, rows)
    (WORK / "final").mkdir(parents=True, exist_ok=True)
    (WORK / "final" / "sostituzioni.log").write_text("\n".join(log), encoding="utf-8")
    print(f"{'(prova) ' if a.dry_run else ''}{total} sostituzioni in {len(set(l.split(' ')[0] for l in log))} righe → work/final/sostituzioni.log")


if __name__ == "__main__":
    main()
