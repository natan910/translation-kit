---
name: comics-translate
description: Translate and adapt a European or American comic (French, Spanish, English, German or other) into an Italian lettering script (xlsx + docx) with the comics-kit pipeline, and learn from the redattore's reviewed version. Use for a new album or issue, to resume one, or when a reviewed script comes back.
---

# Pipeline di traduzione fumetti (lingue europee → italiano)

Tutto avviene nella cartella del kit. Scripts in `scripts/`, agenti in `.claude/agents/`, regole in `config/comics/`. Il lavoro meccanico lo fanno gli script (zero token); i modelli solo dove serve giudizio:

| Passo | Chi | Modello |
|---|---|---|
| Render, livello di testo del PDF, rilevamento testi, vignette e ordine di lettura, misure dei balloon, OCR, QA, merge, export, tavole numerate, confronto revisione | script Python | — |
| Lettura etichette scritte a mano (solo `labels_mode` hand) | `label-reader` | Haiku |
| Traduzione | `comics-translator`, uno per parte | Opus |
| Adattamento ai balloon (testo + misure, niente immagini) | `comics-editor`, uno per parte | Opus |
| Coerenza tra parti | `harmonizer` | Sonnet |
| Apprendimento dalla revisione | `feedback-analyst` | Sonnet |

Ogni agente lavora nella sua cartella `work/agents/<agente>-<parte>/` e risponde in poche righe. All'utente riporta solo numeri e decisioni. Se la sessione non vede gli agenti di `.claude/agents/`, lancia un agente generico con il modello indicato e il prompt "Segui le istruzioni di .claude/agents/<nome>.md per <parte>".

## Ripresa
Ogni passo scrive file in `work/`: prima di ogni passo controlla se l'output esiste e saltalo o riprendi dall'ultima pagina scritta. Un agente fermato dai limiti d'uso si riprende con un messaggio: riparte dal file.

## 0. Controllo macchina e impostazioni
Tutti gli script si lanciano con `bin/py` (usa la `.venv` del kit anche in una shell nuova). Se `.venv` non esiste: `bash setup.sh` (manga: `bash setup.sh --manga-ocr`). Un lavoro alla volta in `work/`: per cominciarne uno nuovo, archivia il precedente con `bash scripts/archive.sh <nome>`.
- `bin/py scripts/setup_check.py` (controlla anche il pacchetto tesseract della lingua di partenza).
- `config/comics/lettering.json`: chiedi all'utente (una volta, AskUserQuestion) la lingua di partenza (`lingua_originale`: fra, spa, eng, deu, por, nld…; più lingue: "fra+eng") e se le tavole hanno numeri scritti a mano (`labels_mode`: auto di default; hand solo per pagine in bianco e nero). Ordine di lettura `ltr` salvo fumetti con ordine giapponese.

## 1. Preparazione (zero token)
PDF in `input/`, poi `bash scripts/prep.sh comics input/<albo>.pdf [pagine_per_parte]`: render, livello di testo (se il PDF ce l'ha: testo esatto, niente OCR), divisione in parti, rilevamento, OCR delle pagine senza testo.
Poi, per ogni parte: `bin/py scripts/comics/build_inputs.py <parte>`.
In numerazione automatica: `bin/py scripts/comics/number_pages.py all "<Titolo>"` → tavole numerate in `output/`; proponi all'utente di scorrerle per controllare l'ordine di lettura sulle pagine complesse.

## 2. Decisioni prima di tradurre (una volta)
- Parti: conferma `config/comics/chapters.json` (albo intero fino a 64 pagine, altrimenti parti da ~24; si possono scrivere a mano, es. un numero di comic book per parte).
- Glossario: per una serie già pubblicata chiedi il glossario ufficiale (nomi, termini, registri tu/lei tra personaggi) e scrivilo in `config/comics/glossary.tsv` (originale, italiano, vietate, note).
- Le voci **[da decidere]** di `config/comics/style_guide.md` (maiuscolo, virgolette, nomi propri, SFX, turpiloquio): chiedile alla prima serie e scrivi la decisione al posto del segnaposto.

## 3. Etichette a mano (solo `labels_mode` hand)
`bin/py scripts/sheets.py <parte>` → agente `label-reader` → `bin/py scripts/labels_apply.py <parte>` → `bin/py scripts/comics/build_inputs.py <parte>`.

## 4. Traduzione (Opus)
Agente `comics-translator` con prompt "parte <parte>", al massimo 3 in parallelo. L'agente esegue `scripts/qa.py <parte> --stage traduzione`; controlla il riepilogo (id mancanti, termini vietati, quanti LUNGO già sulla traduzione grezza).

## 5. Adattamento (Opus)
Appena una parte è tradotta: agente `comics-editor` con prompt "parte <parte>". Lavora su `editor_input.tsv` (testo + misure + lunghezza dell'originale) e fa da solo il secondo giro su `qa.tsv`.

## 6. Coerenza (Sonnet)
Con tutte le parti adattate: agente `harmonizer`; mostra `work/final/armonizzazione_proposte.md`, applica le decisioni con `bin/py scripts/apply_replacements.py work/final/armonizzazione.tsv` (prima `--dry-run`), aggiornale nel glossario.

## 7. Consegna (zero token)
`bin/py scripts/merge.py` → `bin/py scripts/export.py work/final/copione.tsv "<Titolo>"` → `output/*_copione.xlsx`, `.docx` (+ `.tsv` per il confronto con la revisione) e, in numerazione automatica, le tavole numerate. Riepilogo: righe per stato, righe RIVEDERE e note `ORDINE:` da guardare per prime. Ricorda che l'utente può rimandare la versione rivista.

## 8. Revisione del redattore → agenti migliori
1. `bin/py scripts/review_diff.py <rivisto.xlsx|.docx> --delivered output/<titolo>_copione.tsv --label <serie>-<albo>`.
2. Agente `feedback-analyst` con "revisione <label>".
3. Mostra in breve `work/feedback/<label>/proposte.md` e chiedi quali approvare (scelta multipla per sezione).
4. Applica solo le approvate: `config/comics/learned/translator.md`, `config/comics/learned/editor.md` (istruzione · esempio · fonte), `config/comics/glossary.tsv`, `config/comics/lettering.json`; una riga in `config/comics/learned/CHANGELOG.md`.
5. Riferisci la percentuale di righe cambiate dal redattore: è la misura del miglioramento da un albo all'altro.
"Migliorare gli agenti" = aggiornare le regole che leggono, non riaddestrare il modello.

## Calibrare la capienza
La capienza usa il lettering originale come righello (stesso corpo: `it_font_vs_source` = 1.0). Se il letterista italiano usa un corpo diverso dall'originale, imposta il rapporto (es. 0.9) e rilancia `bin/py scripts/comics/build_inputs.py` per le parti non ancora adattate: non serve rifare rilevamento né OCR.
