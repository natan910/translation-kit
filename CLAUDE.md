# translation-kit

Kit per tradurre e adattare in italiano manga (dal giapponese) e fumetti europei e americani (francese, spagnolo, inglese, tedesco e altre lingue), producendo un copione di lettering. Due modi, stesso kit:

- **manga** → skill `manga-translate` (`.claude/skills/manga-translate/SKILL.md`), agenti `manga-translator`, `manga-editor`, config in `config/manga/`
- **comics** → skill `comics-translate` (`.claude/skills/comics-translate/SKILL.md`), agenti `comics-translator`, `comics-editor`, config in `config/comics/`
- in comune: agenti `label-reader`, `harmonizer`, `feedback-analyst`; script di QA, merge, export, confronto revisione.

Il modo del lavoro in corso è in `work/mode` (`bin/py scripts/mode.py` per vederlo). Segui la skill del modo per ogni nuovo volume, per riprendere un lavoro interrotto e quando torna una revisione del redattore.

Regole:
- **Python: sempre `bin/py`, mai `python3`.** `bin/py` usa la `.venv` del kit anche in una shell nuova (per ogni agente). Se la `.venv` manca: `bash setup.sh`.
- Lingua di lavoro con l'utente: italiano.
- Il lavoro meccanico va negli script di `scripts/`, mai fatto a mano da un modello (niente ricopiature di testo, niente impaginazione a mano dei file).
- Opus solo per traduzione e adattamento; il resto con Haiku/Sonnet (vedi `.claude/agents/`).
- Ogni agente lavora nella sua cartella `work/agents/<nome>-<capitolo>/` e risponde in poche righe.
- Un lavoro alla volta in `work/`; per cominciarne un altro: `bash scripts/archive.sh <nome>` (sposta in `archive/`, non cancella).
- `config/<modo>/` contiene le regole che migliorano nel tempo (glossario, guida di stile, lezioni dalle revisioni): modificarle solo con l'approvazione dell'utente.
- `output/` contiene le consegne; i `.tsv` lì dentro sono la base per il confronto con le revisioni: non cancellarli.
