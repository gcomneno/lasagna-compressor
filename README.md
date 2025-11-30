# lasagna-compressor
> A layered experimental text compressor for Italian, inspired by linguistic structure… and baked like a lasagna. 🍝
---

## Overview (EN)

**lasagna-compressor** is an experimental text compressor that tries to exploit different *linguistic layers* of Italian, instead of treating text as a flat stream of bytes.

It is **not** meant to beat industrial compressors like gzip.  
It is a playground for:
- understanding how compression and language structure interact,
- experimenting with different preprocessing layers (bytes, vowels/consonants, syllables, words, lemmas),
- building prototypes first in Python, and later (maybe) porting parts to C.

The current implementation is a single Python script using **Huffman coding** on top of several preprocessing strategies (“steps”).

---

## Panoramica (IT)

**lasagna-compressor** è un compressore di testo **sperimentale** che prova a usare i vari *strati* della lingua italiana (byte, lettere, sillabe, parole, lemmi) invece di schiacciare tutto alla cieca.

Obiettivo:

- capire come sfruttare la struttura linguistica per la compressione,
- avere un laboratorio per giocare con:
  - Huffman,
  - diversi livelli di pre-processing,
  - futuri esperimenti con lemmi e morfologia.

Non è pensato per “battere gzip”, ma per **studiare e divertirsi**.

---

## Layers / Steps

Attualmente sono implementati 4 step (formati v1–v4) + un’idea per v5:

### v1 – Step 1: raw bytes (baseline)

- Nessun pre-processing.
- Il file viene visto come semplice sequenza di byte.
- Viene applicata la classica compressione **Huffman** sui byte.
- Formato con:
  - header (magic `"GCC"`, versione, numero di byte, tabella frequenze),
  - bitstream Huffman.

Comandi CLI: `c1` / `d1`.

---

### v2 – Step 2: V/C/O (vowels / consonants / other)

- Pre-processing:
  - si separa il testo in 3 stream:
    - **mask**: sequenza di `'V'`, `'C'`, `'O'` per ogni carattere,
    - **vowels**: solo le vocali,
    - **cons**: consonanti + tutto il resto.
- Ogni stream viene compresso **separatamente** con Huffman.
- L’idea è sfruttare la struttura **vocale/consonante** dell’italiano.

Comandi CLI: `c2` / `d2`.

---

### v3 – Step 3: pseudo-syllables + non-letter blocks

- Pre-processing:
  - il testo è diviso in token:
    - sequenze di lettere ASCII → spezzate in **pseudo-sillabe** (taglio grezzo dopo ogni vocale),
    - sequenze di non-lettere → tenute come blocchi separati (spazi, punteggiatura, ecc.).
- Si costruisce un **vocabolario di token** (sillabe + blocchi).
- Ogni token viene mappato a un ID (0–255) e si comprime la sequenza di ID con Huffman.
- Il formato v3 contiene:
  - numero di token,
  - vocabolario (ID → token),
  - tabella frequenze sugli ID,
  - bitstream Huffman.

Comandi CLI: `c3` / `d3`.

> ⚠️ Limite attuale: al massimo **256 token distinti** per v3.

---

### v4 – Step 4: whole words + non-letter blocks

- Pre-processing:
  - il testo è diviso in token:
    - sequenze di lettere ASCII → **parole intere**,
    - sequenze di non-lettere → blocchi separati.
- Come in v3:
  - si crea un vocabolario di token (parole + blocchi),
  - ogni token è sostituito da un ID (0–255),
  - si applica Huffman sulla sequenza di ID.
- Il formato v4 è simile a v3, ma i token sono **parole**, non sillabe.

Comandi CLI: `c4` / `d4`.

> ⚠️ Anche qui: massimo **256 token distinti** per v4.

---

### v5 – Step 5 (idea, non implementato): lemmas + morphological tags

**Concept only, not implemented yet.**

- Obiettivo: lavorare non solo su forme scritte, ma su:
  - **lemmi** (forma base delle parole, es. *andare*),
  - **tag morfologici** (tempo, persona, numero, genere, ecc.).
- Pipeline ideale:
  - tokenizzazione in parole + non-parole (come v4),
  - lemmatizzazione delle parole → (lemma, tag),
  - costruzione di stream separati:
    - `lemma_ids`,
    - `tag_ids`,
    - `other_ids` (blocchi non-lettera),
  - compressione di ogni stream con Huffman.
- Richiede un vero lemmatizzatore italiano e/o modello morfologico.

---

## Usage

### Prerequisites

- Python 3.x
- Il file `gcc_huffman.py` (ad esempio in `src/python/gcc_huffman.py`).

Dal root del progetto:

```bash
cd lasagna-compressor
python3 src/python/gcc_huffman.py  # oppure ./gcc_huffman.py se è nella root
````

### Command line interface

Formato generale:

```bash
python3 src/python/gcc_huffman.py <mode> <input> <output>
```

Dove `<mode>` può essere:

* `c1` – compress Step1 (raw bytes, v1)
* `d1` – decompress Step1
* `c2` – compress Step2 (V/C/O, v2)
* `d2` – decompress Step2
* `c3` – compress Step3 (pseudo-syllables, v3)
* `d3` – decompress Step3
* `c4` – compress Step4 (whole words, v4)
* `d4` – decompress Step4

Esempi (se `gcc_huffman.py` è nella root):

```bash
# Step 1 – byte-level Huffman
python3 gcc_huffman.py c1 input.txt output_step1.gcc
python3 gcc_huffman.py d1 output_step1.gcc recon_step1.txt
diff input.txt recon_step1.txt  # should be empty (lossless)

# Step 2 – V/C/O
python3 gcc_huffman.py c2 input.txt output_step2.gcc
python3 gcc_huffman.py d2 output_step2.gcc recon_step2.txt

# Step 3 – pseudo-syllables
python3 gcc_huffman.py c3 input.txt output_step3.gcc
python3 gcc_huffman.py d3 output_step3.gcc recon_step3.txt

# Step 4 – whole words
python3 gcc_huffman.py c4 input.txt output_step4.gcc
python3 gcc_huffman.py d4 output_step4.gcc recon_step4.txt
```

Ogni modalità di compressione stampa anche statistiche di base:

* dimensione originale / compressa,
* rapporto di compressione,
* bit per simbolo (8.0 = non compresso).

---

## Limitations / Note

* I formati v1–v4 sono **sperimentali** e non stabili:

  * possono cambiare in futuro,
  * non sono compatibili con altri software.
* I test attuali sono pensati per **testo in ASCII/UTF-8 “semplice”**:

  * lettere A–Z / a–z,
  * niente garanzie per caratteri Unicode esotici.
* Su file piccoli, l’overhead degli header è molto grande, quindi:

  * la “compressione” spesso **aumenta** la dimensione del file,
  * questo è voluto: il focus è sul modello, non sulle performance reali.

---

## Roadmap (short version)

Planned / possible future work:

1. **Header optimizations**

   * salvare solo simboli con freq > 0,
   * ridurre la dimensione delle tabelle nell’header.

2. **Real lemmatizer integration (Step5)**

   * usare una libreria di lemmatizzazione per l’italiano,
   * definire un formato v5 (lemmi + tag morfologici).

3. **C port**

   * portare il core Huffman (v1) in C,
   * valutare un porting anche per il livello “parole” (v4).

---

## Disclaimer
This project is a **learning playground**, not production software.
If it breaks, explodes your file sizes, or makes you hungry… well, at least the last one is intended. 😄🍝

---

## Project status
This project is **experimental** and not stable.

- Binary formats (v1–v4) may change at any time.
- The Python implementation is a prototype / playground, not production code.
- The goal is to explore ideas (compression + linguistic structure), not to outperform existing compressors.

### Stato del progetto (IT)

Il progetto è **sperimentale** e non stabile.

- I formati binari (v1–v4) possono cambiare in futuro.
- L’implementazione in Python è un prototipo da laboratorio, non software di produzione.
- L’obiettivo è esplorare idee (compressione + struttura linguistica), non battere gzip.
