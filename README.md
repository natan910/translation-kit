# translation-kit

**A Claude Code toolkit that turns a comic or manga PDF into an Italian lettering script** (Excel + Word): translated, adapted to the size of each balloon, and checked, with a feedback loop that learns from the editor's corrections.

Two modes in one kit:

| Mode | For | Source languages | How text is numbered |
|---|---|---|---|
| `manga` | manga | Japanese (vertical text) | blue numbers / red letters handwritten by the editor on the pages |
| `comics` | European and American comics | French, Spanish, English, German, Portuguese, Dutch, and any language Tesseract supports | automatic, in reading order (or handwritten, for black-and-white pages) |

*The agents' instructions, the style guides and the output scripts are in Italian (target language: Italian). An Italian guide is in [README.it.md](README.it.md).*

---

## Why it exists

Translating a comic for publication is two jobs: **translation** (getting meaning, tone and voice right) and **adaptation** (making the text fit the balloons without betraying it). Language models are good at the first and blind to the second unless they can measure the page. Letting a model do the mechanical work (reading every page image, retyping text, formatting files) is slow and burns tokens.

This kit splits the work:

- **Deterministic Python scripts do everything mechanical, at zero token cost:** rendering pages, finding balloons and measuring them, OCR (or extracting the PDF's text layer), computing reading order, quality checks, merging, exporting, and comparing a reviewed script with the delivered one.
- **Models work only where judgement is needed**, each on the cheapest model that can do the job:

| Step | Who | Model |
|---|---|---|
| Rendering, text-layer extraction, balloon detection and measurement, reading order, OCR, QA, merge, export, review diff | Python scripts | — |
| Reading handwritten labels | `label-reader` agent | Haiku |
| Translation | `manga-translator` / `comics-translator`, one per chapter | Opus |
| Adaptation to the balloons (text + measurements, no page images) | `manga-editor` / `comics-editor`, one per chapter | Opus |
| Cross-chapter consistency | `harmonizer` | Sonnet |
| Learning from the editor's review | `feedback-analyst` | Sonnet |

## How it works

1. **Prepare** (`bash scripts/prep.sh manga|comics input/<file>.pdf`). The scripts render the pages and find the text blocks. They read the text: from the PDF's text layer if there is one, otherwise with OCR (manga-ocr or Tesseract). They measure each balloon's shape as **Italian characters per line**:
   - in manga, from the size of the Japanese glyphs;
   - in comics, using the original lettering as a ruler.
2. **Decide before translating.** Claude asks the human editor for the chapter split, the series glossary, name spellings and open style choices (uppercase lettering, sound effects…), so they don't have to be fixed across a whole volume later.
3. **Translate** chapter by chapter (Opus), from the source script plus lightweight page previews.
4. **Adapt** (Opus) from text plus measurements only, with no page images unless needed. A fit test wraps every line into the measured balloon, proposes line breaks, and flags lines as `OK`, `STRETTO` (tight), `LUNGO` (too long) or `RIVEDERE` (open question for the editor).
5. **Harmonize** names and terms across chapters (Sonnet); the editor approves, a script applies.
6. **Export** to `.xlsx` and `.docx` (plus numbered reference pages in comics mode).
7. **Learn.** The editor sends back the reviewed file. `review_diff.py` measures every change. The `feedback-analyst` proposes new rules for the translator and editor agents, the editor approves which to keep, and they go into `config/<mode>/learned/`, which the agents read on every following job. This is accumulated instructions, not model fine-tuning. The improvement metric is the share of lines the editor still changes, volume after volume.

Every step writes its output to `work/`, so a job interrupted by usage limits resumes from where it stopped.

## Requirements

- [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
- Python 3.10+
- Poppler (`pdftoppm`, `pdftotext`) and Tesseract with the language packs you need:
  ```
  brew install poppler tesseract tesseract-lang          # macOS
  apt install poppler-utils tesseract-ocr tesseract-ocr-jpn-vert tesseract-ocr-fra …   # Debian/Ubuntu
  ```

## Install

```
git clone <this repo> translation-kit
cd translation-kit
bash setup.sh                  # creates .venv and installs Python dependencies
bash setup.sh --manga-ocr      # optional: manga-ocr, strongly recommended for manga (~2.5 GB with PyTorch)
bin/py scripts/setup_check.py  # checks everything, including Tesseract language packs
```

`bin/py` runs the kit's `.venv` Python without activating it. Every script, skill and agent uses it, so agents started in a fresh shell still find the libraries.

Try it on a generated sample comic (two colour pages in French):
```
bin/py tests/make_sample.py
bash scripts/prep.sh comics tests/sample_scansione.pdf
```

## Use

Open the folder with Claude Code and ask, for example:

- *"Traduci il volume input/vol01.pdf"* → `manga-translate` skill
- *"Traduci l'albo input/album.pdf dal francese"* → `comics-translate` skill

One job at a time lives in `work/`. To start another, archive the current one with `bash scripts/archive.sh <name>`; it moves to `archive/` and nothing is deleted.

### Sending back a reviewed script
Edit the exported `.xlsx` (Adattamento / Personaggio / Stato columns, comments in "Nota redattore") or the `.docx` (Italiano column) without renumbering rows, then hand it back to Claude: *"Ecco la revisione di <volume>"*.

## Repository layout

```
translation-kit/
├── setup.sh, bin/py, requirements.txt
├── CLAUDE.md                     project rules for Claude Code
├── .claude/
│   ├── agents/                   agent definitions (model, tools, instructions)
│   └── skills/                   manga-translate, comics-translate: the step-by-step pipelines
├── scripts/
│   ├── prep.sh, mode.py, archive.sh
│   ├── render, qa, fit, merge, export, review_diff, …   shared
│   ├── manga/                    vertical-text detection, OCR, chapter detection
│   └── comics/                   PDF text layer, horizontal-text detection, panels and reading order, numbered pages
├── config/
│   ├── manga/  comics/           glossary, style guide, lettering calibration, chapters, learned rules
├── tests/make_sample.py          generates a test comic
└── input/  work/  output/        (ignored by git)
```

## Calibration

Balloon capacity is an estimate. After the letterer's first chapter, adjust one value:
- `it_font_vs_jp_glyph` in `config/manga/lettering.json`;
- `it_font_vs_source` in `config/comics/lettering.json`.

Lower it if lines keep coming out too long, raise it if too short. The `feedback-analyst` proposes this correction itself when reviews keep changing the status flags.

## Measured so far, and known limits

| | Result | Tested on |
|---|---|---|
| Handwritten label reading (Haiku) | ~93% correct, ~92% of the script's IDs found automatically | one real manga chapter (~50 pages) |
| Japanese OCR, Tesseract | usable on ~40% of balloons (clean text only) | same chapter |
| Comics: text found, reading order | 16/16 texts, correct order | generated pages only |
| Comics: French OCR, Tesseract | ~95% of characters | generated pages only |

**Japanese OCR.** Install manga-ocr: it's much better on stylised text. With Tesseract alone, the translator reads more from the page images, which costs more tokens.

**Balloon detection** is heuristic (OpenCV). It can miss handwritten text, text drawn on the artwork, and some white-on-black text. Missed labels stay in the script with a note, and the translator reads them from the preview.

**Comics mode** hasn't been tested on a real album yet. Pages without regular white gutters (splash pages, overlapping panels, balloons crossing two panels) can get the wrong reading order. The translator flags these with `ORDINE:` instead of renumbering. Sound effects drawn as artwork aren't detected; the translator adds them.

**Capacity** is an estimate; the letterer has the final word.

## Copyright and source material

The kit contains no comic material. Use it only on works you have the rights to translate. Keep source PDFs, scripts and translations out of the repository: `input/`, `work/`, `archive/` and `output/` are git-ignored for this reason.

## License

MIT, see [LICENSE](LICENSE).
