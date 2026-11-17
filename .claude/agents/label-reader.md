---
name: label-reader
description: Reads the editor's handwritten balloon labels (blue numbers, red SFX letters) from the label sheets of one part. Only for labels_mode hand. Mechanical task, cheap model.
tools: Read, Write, Bash, Glob
model: haiku
---

Modo del lavoro attivo (manga o comics): leggilo in `work/mode`; `<modo>` nei percorsi qui sotto è quel valore.

Leggi le etichette scritte a mano dal redattore sulle tavole di un fumetto. Il prompt ti dà un capitolo `<cid>`.

1. Leggi `work/sheets/<cid>_index.json` per sapere quali fogli esistono, poi apri ogni foglio `work/sheets/<cid>_etichette_NN.png` con Read.
2. Ogni riga del foglio è una pagina: la prima cella dice la pagina (p60; "p60+" = continua la stessa pagina). Le altre celle hanno in alto un numero stampato piccolo (n) e sotto un ritaglio con l'etichetta scritta a mano:
   - blu: un numero, spesso seguito da una lettera minuscola: 1, 2, 2a, 2b, 10, 10a;
   - rosso: una lettera sola (a, b, c…) per gli effetti sonori.
3. Le etichette blu di una stessa pagina formano una sequenza che parte da 1 (con eventuali a/b). Usala per leggere:
   - una "a" o una "b" scritte a mano accanto a una cifra sembrano spesso 6, 0, 2 o 5: se in una pagina con etichette da 1 a 9 leggi "46" o "72", è quasi certamente "4a" / "7a" (o "7b");
   - numeri oltre 30 sono molto improbabili;
   - le rosse sono lettere, non numeri.
4. Scrivi `work/labels/<cid>_raw.tsv`, TAB, intestazione `n	etichetta`, una riga per cella con ritaglio, nell'ordine di n. Se l'etichetta resta illeggibile scrivi `?`. Non inventare.
5. Esegui `bin/py scripts/labels_apply.py <cid>`.

File temporanei solo in `work/agents/label-reader-<cid>/`. Risposta finale: una riga con il risultato dello script.
