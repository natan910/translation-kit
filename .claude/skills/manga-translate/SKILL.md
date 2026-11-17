---
name: manga-translate
description: Translate and adapt a Japanese manga volume into an Italian lettering script (xlsx + docx) with the manga-kit pipeline, and learn from the redattore's reviewed version. Use for a new volume, to resume one, or when a reviewed script comes back.
---

# Pipeline di traduzione manga (giapponese → italiano)

Tutto avviene nella cartella del kit (questa repo). Scripts in `scripts/`, agenti in `.claude/agents/`, regole in `config/manga/`. Il lavoro meccanico lo fanno gli script (zero token); i modelli solo dove serve giudizio:

| Passo | Chi | Modello |
|---|---|---|
| Render, rilevamento balloon e misure, OCR, fogli etichette, QA, merge, export, confronto revisione | script Python | — |
| Lettura etichette scritte a mano | agente `label-reader` | Haiku |
| Traduzione | agente `manga-translator`, uno per capitolo | Opus |
| Adattamento ai balloon (testo + misure, niente immagini) | agente `manga-editor`, uno per capitolo | Opus |
| Coerenza tra capitoli | agente `harmonizer` | Sonnet |
| Apprendimento dalla revisione | agente `feedback-analyst` | Sonnet |

Regole per tutti gli agenti che lanci: ognuno ha la sua cartella `work/agents/<agente>-<capitolo>/`; risposta finale breve (lo dice la loro definizione: non chiedere riassunti). Non riportare all'utente i loro resoconti per intero: solo numeri e decisioni da prendere.

## Ripresa
Ogni passo scrive file in `work/`. Prima di ogni passo controlla se il suo output esiste già e saltalo (o riprendi dall'ultima pagina scritta). Se un agente si ferma per i limiti d'uso, alla ripresa rimandagli un messaggio: riparte dal file.

## 0. Controllo macchina
Tutti gli script si lanciano con `bin/py` (usa la `.venv` del kit anche in una shell nuova). Se `.venv` non esiste: `bash setup.sh` (manga: `bash setup.sh --manga-ocr`). Un lavoro alla volta in `work/`: per cominciarne uno nuovo, archivia il precedente con `bash scripts/archive.sh <nome>`.
`bin/py scripts/setup_check.py`. Se manca qualcosa, installalo (o di' all'utente il comando). manga-ocr è consigliato ma non obbligatorio.

## 1. Preparazione (zero token)
PDF in `input/`. Poi `bash scripts/prep.sh manga input/<volume>.pdf`: render, rilevamento, OCR di tutto il volume, proposta capitoli.

## 2. Decisioni prima di tradurre (chiedi all'utente, una volta)
- Capitoli: mostra la proposta di `bin/py scripts/manga/chapters_guess.py`; scrivila con `--write`, separa a mano gli extra finali (rubrica, galleria, colophon) e imposta `folio_offset` in `config/manga/chapters.json`. Conferma con l'utente.
- Glossario: se è una serie nuova o un volume nuovo, chiedi il glossario ufficiale dei volumi precedenti e aggiornalo in `config/manga/glossary.tsv` (colonne originale, italiano, vietate, note). Guarda le anteprime delle pagine con le schede personaggi e, se c'è, la galleria finale (grafie latine dell'autore). Chiedi le scelte aperte (grafie dei nomi, termini chiave, trattamento SFX) PRIMA di tradurre: correggere dopo costa un giro intero.
- Formato di consegna: di default xlsx + docx.

## 3. Etichette, per capitolo (Haiku)
Per ogni capitolo: `bin/py scripts/sheets.py <cid>`, poi agente `label-reader` con prompt "capitolo <cid>". Poi `bin/py scripts/manga/build_inputs.py <cid>`. Se restano molte etichette non lette, guarda tu i fogli indicati prima di passare oltre. Si possono lanciare tutti i capitoli in parallelo.

## 4. Traduzione (Opus)
Agente `manga-translator` con prompt "capitolo <cid>". Al massimo 3 capitoli in parallelo (evita di esaurire i limiti d'uso tutti insieme). Ogni agente esegue da solo `scripts/qa.py <cid> --stage traduzione`; controlla il riepilogo.

## 5. Adattamento (Opus)
Appena un capitolo è tradotto: `bin/py scripts/qa.py <cid> --stage traduzione` (se l'agente non l'ha già fatto), poi agente `manga-editor` con prompt "capitolo <cid>". L'editor lavora su testo + misure e fa da solo il secondo giro su `qa.tsv`.

## 6. Coerenza del volume (Sonnet)
Quando tutti i capitoli sono adattati: agente `harmonizer`. Mostra all'utente `work/final/armonizzazione_proposte.md`, chiedi le decisioni, aggiorna `work/final/armonizzazione.tsv` di conseguenza, poi `bin/py scripts/apply_replacements.py work/final/armonizzazione.tsv --dry-run` e, se va bene, senza `--dry-run`. Aggiungi le decisioni a `config/manga/glossary.tsv`.

## 7. Consegna (zero token)
`bin/py scripts/merge.py` → `bin/py scripts/export.py work/final/copione.tsv "<Titolo> vol. <N>"` → `output/*_copione.xlsx` e `*_copione.docx`. Consegna i due file. Riepilogo all'utente: righe per stato, decisioni aperte (righe RIVEDERE), cosa controllare per primo. Ricorda che può rimandare la versione rivista.

## 8. Revisione del redattore → agenti migliori
Quando l'utente rimanda il copione rivisto (xlsx o docx esportati, modificati; commenti nella colonna "Nota redattore" o "Nota"):
1. Copialo in `input/` e lancia `bin/py scripts/review_diff.py input/<file> --label <serie>-vol<N>`.
2. Agente `feedback-analyst` con prompt "revisione <label>".
3. Mostra all'utente `work/feedback/<label>/proposte.md` in forma breve e chiedi quali approvare (AskUserQuestion, scelta multipla per sezione).
4. Applica solo le approvate: aggiungi le regole a `config/manga/learned/translator.md` / `config/manga/learned/editor.md` (formato: istruzione · esempio · fonte), i termini a `config/manga/glossary.tsv`, la calibrazione a `config/manga/lettering.json`. Una riga in `config/manga/learned/CHANGELOG.md`.
5. Riferisci la percentuale di righe cambiate dal redattore: è la misura del miglioramento da un volume all'altro.

Nota: "migliorare gli agenti" qui significa aggiornare le istruzioni e le regole che leggono a ogni lavoro, non riaddestrare il modello.

## Calibrare la capienza
Il calcolo dei caratteri per balloon dipende dal corpo del lettering. Dopo il primo capitolo letterato, se il letterista trova sistematicamente righe troppo lunghe (o troppo corte), abbassa (o alza) `it_font_vs_jp_glyph` in `config/manga/lettering.json` di 0,05 e rilancia `bin/py scripts/manga/detect.py` e `bin/py scripts/manga/build_inputs.py` per i capitoli non ancora adattati.
