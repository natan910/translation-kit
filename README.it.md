# translation-kit — copioni di lettering in italiano con Claude Code

*English: see [README.md](README.md).*

Un kit, due modi:

| Modo | Per | Lingue di partenza | Numerazione dei testi |
|---|---|---|---|
| `manga` | manga | giapponese (testo verticale) | numeri blu / lettere rosse scritti a mano dal redattore |
| `comics` | fumetti europei e americani | francese, spagnolo, inglese, tedesco, portoghese, olandese… | automatica in ordine di lettura (o a mano, per tavole in bianco e nero) |

Il lavoro meccanico (rilevamento, misure dei balloon, OCR, controlli, export) lo fanno script Python, a costo zero in token. I modelli lavorano solo dove serve giudizio: Opus traduce e adatta, Haiku legge le etichette scritte a mano, Sonnet controlla la coerenza e impara dalle revisioni. Consegna: copione in Excel e Word (più le tavole numerate in modo comics).

## Installazione (una volta)

Il kit usa un ambiente Python isolato, `.venv`, dentro la sua cartella.

```
cd translation-kit
bash setup.sh                  # crea .venv e installa le dipendenze
bash setup.sh --manga-ocr      # in più: manga-ocr, l'OCR consigliato per i manga (~2,5 GB con PyTorch)
brew install poppler tesseract tesseract-lang     # programmi di sistema (macOS); non stanno nella .venv
bin/py scripts/setup_check.py  # controllo finale
```
Poi apri la cartella con Claude Code: `claude` dalla cartella del kit.

### Perché `.venv` e cos'è `bin/py`
- La `.venv` tiene le librerie del kit (OpenCV, numpy, e soprattutto PyTorch se installi manga-ocr) separate dal resto del Mac e dagli altri progetti. Su macOS con il Python di Homebrew, `pip install` fuori da una `.venv` è comunque bloccato.
- `bin/py` è un piccolo lanciatore: esegue il Python della `.venv` senza bisogno di attivarla. Tutti gli script, la skill e gli agenti lo usano, così anche gli agenti che partono in una shell nuova trovano le librerie. Se la `.venv` non c'è ancora, ripiega su `python3` di sistema e lo segnala.
- Se aggiorni Python (es. Homebrew passa da 3.12 a 3.13) e la `.venv` smette di funzionare: `bash setup.sh --reset`.
- Non spostare né comprimere la `.venv` (contiene percorsi assoluti): se sposti il kit, rifai `bash setup.sh --reset`. È esclusa da `.gitignore`.
- Occupa ~300 MB, ~2,5 GB con manga-ocr. Una sola `.venv` serve entrambi i modi.

## Uso
In Claude Code, per esempio:
- *"Traduci il volume input/vol13.pdf"* (manga) → skill `manga-translate`
- *"Traduci l'albo input/album.pdf dal francese"* → skill `comics-translate`

Claude prepara il volume con gli script (`bash scripts/prep.sh manga|comics input/<file>.pdf`), ti chiede le decisioni prima di tradurre (capitoli/parti, glossario, grafie, scelte di stile), poi lancia gli agenti capitolo per capitolo e consegna in `output/`.

**Un lavoro alla volta.** `work/` contiene il lavoro in corso. Per cominciarne un altro: `bash scripts/archive.sh <nome>` sposta il lavoro in `archive/<nome>/` (niente viene cancellato) e libera `work/`.

## Dov'è cosa
```
translation-kit/
├── setup.sh                  installazione (.venv)
├── bin/py                    Python del kit
├── CLAUDE.md                 regole per Claude Code
├── .claude/
│   ├── agents/               gli agenti (file di istruzioni; cartella nascosta: Cmd+Shift+. nel Finder)
│   │   ├── manga-translator.md, manga-editor.md         Opus
│   │   ├── comics-translator.md, comics-editor.md       Opus
│   │   ├── label-reader.md                              Haiku
│   │   └── harmonizer.md, feedback-analyst.md           Sonnet
│   └── skills/
│       ├── manga-translate/SKILL.md                     il flusso manga
│       └── comics-translate/SKILL.md                    il flusso fumetti
├── scripts/
│   ├── prep.sh, mode.py, archive.sh                     avvio, modo, archivio
│   ├── render, qa, fit, merge, export, review_diff…     in comune
│   ├── manga/                detect, ocr, build_inputs, chapters_guess
│   └── comics/               extract (testo dal PDF), detect, ocr, build_inputs, number_pages, chapters_auto
├── config/
│   ├── manga/                glossario, guida di stile, lettering, capitoli, learned/ (lezioni dalle revisioni)
│   └── comics/               idem per i fumetti
├── tests/make_sample.py      crea un fumetto di prova (modo comics)
├── input/  work/  archive/  output/
```
Gli agenti sono file di testo: in cima c'è nome, modello e strumenti consentiti; sotto, le istruzioni. Claude Code li avvia come sessioni separate quando la skill lo dice. Si modificano in italiano, senza codice.

## Rimandare la versione rivista
Correggi l'xlsx (colonne Adattamento / Personaggio / Stato, commenti in "Nota redattore") o il docx (colonna Italiano, commenti in Nota), senza rinumerare le righe. Poi in Claude Code: *"Ecco la revisione di <volume>"*. Il confronto è automatico (`scripts/review_diff.py`), un agente propone nuove regole per traduttore ed editor, tu approvi quali tenere, e finiscono in `config/<modo>/learned/`: gli agenti le leggono a ogni lavoro successivo. Non è un riaddestramento del modello, sono istruzioni che si accumulano. La misura del miglioramento è la percentuale di righe che correggi da un volume all'altro.

Il confronto accetta anche copioni nel formato precedente, con la colonna "Giapponese" al posto di "Originale".

## Comandi utili senza Claude
```
bin/py scripts/mode.py                                   # modo attivo
bin/py scripts/export.py <copione.tsv> "Titolo"          # TSV → xlsx + docx (+ copia tsv per la revisione)
bin/py scripts/fit.py "Testo da provare" 8,11,13,13,9    # entra in un balloon con queste righe?
bin/py scripts/manga/detect.py --pages 40 --debug        # sovrapposizioni in work/debug/ (modo manga)
bin/py scripts/comics/number_pages.py all "Titolo"       # tavole numerate (modo comics)
bin/py tests/make_sample.py                              # fumetto di prova
```

## Calibrare la capienza dei balloon
- **manga**: la capienza si stima dal corpo dei caratteri giapponesi (`it_font_vs_jp_glyph` in `config/manga/lettering.json`). Dopo il primo capitolo letterato: righe troppo lunghe → abbassa di 0,05; troppo corte → alza.
- **comics**: il lettering originale fa da righello (`it_font_vs_source` = 1.0, stesso corpo). Se il letterista italiano usa un corpo diverso, imposta il rapporto (es. 0.9).
Il feedback-analyst propone la correzione da solo se nella revisione cambi molti stati.

## Limiti noti
- **manga**: rilevamento dei balloon euristico (OpenCV): perde testi scritti a mano o sul disegno; tesseract legge bene solo ~40% dei balloon, manga-ocr molto meglio. Lettura delle etichette a mano con Haiku: ~93% corretta (provata su un capitolo reale di circa 50 pagine).
- **comics**: provato su pagine di prova generate (16/16 testi, ordine corretto, OCR francese ~95%), non ancora su un albo vero. Tavole senza canali bianchi regolari possono dare un ordine sbagliato (il traduttore lo segnala con `ORDINE:`); gli SFX disegnati li aggiunge il traduttore.
- La capienza è una stima: la conferma finale è del letterista.
