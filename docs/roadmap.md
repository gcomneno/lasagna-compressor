# Roadmap – lasagna-compressor
Questo file raccoglie le idee di sviluppo per `lasagna-compressor`, organizzate per “strati di ambizione”:
- ✅ Done / prototipato
- 🟡 TODO (ragionevole)
- 🟣 Maybe (quando/SE c’è voglia)
- 🔥 Crazy (per giornate di follia creativa)

---

## 0. Stato attuale (prototipo Python)

### ✅ Implementato

- Core Huffman generico su byte:
  - costruzione tabella frequenze (`freq[256]`),
  - albero di Huffman,
  - tabella dei codici,
  - encode/decode di bitstream.
- Formati:
  - **v1** – Step1: byte grezzi
  - **v2** – Step2: split V/C/O
  - **v3** – Step3: pseudo-sillabe + blocchi non-lettera
  - **v4** – Step4: parole intere + blocchi non-lettera
- CLI in Python:
  - `c1/d1`, `c2/d2`, `c3/d3`, `c4/d4`
- Documentazione di base:
  - `README.md`
  - `docs/formats.md`
  - `docs/design-notes.md`

---

## 1. Fase 0 – Python stabile 🟡

Obiettivo: rendere il prototipo Python comodo da usare e da capire.

### TODO

- [ ] **Test di roundtrip per tutti i formati**
  - Script/test che:
    - per alcuni file di esempio (`tests/testdata/*`),
    - eseguono:  
      `input → compress (v1..v4) → decompress → input'`
    - verificano che `input == input'`.

- [ ] **Script di benchmark base**
  - Fornire uno script (es. `scripts/bench.py`) che:
    - per una lista di file:
      - calcola dimensione compressa v1–v4,
      - stampa un mini report:
        - size originale, size compressa, rapporto, bit/simbolo.
    - eventualmente confronta con `gzip` come riferimento.

- [ ] **Pulizia / refactoring minimo**
  - Migliorare la leggibilità di `gcc_huffman.py`:
    - separare meglio sezione core vs pre-processing,
    - rendere più chiari i nomi delle funzioni,
    - aggiungere commenti sintetici sui formati (rimando a `docs/formats.md`).

---

## 2. Fase 1 – Ottimizzazione header 🟡

Obiettivo: ridurre il peso morto, soprattutto su file piccoli/medi.

### TODO

- [ ] **Header v1 “compresso”**
  - Passare da:
    - 256×`u32` freq fissa
  - a:
    - `NUM_SYMS` (`u16` o `u8`) = quanti simboli compaiono,
    - per ciascun simbolo:
      - `SYMBOL` (`u8`),
      - `FREQ` (`u32`).
  - Mantenere compatibilità logica con l’attuale decoder (o incrementare la versione in modo esplicito).

- [ ] **Applicare la stessa idea a v2–v4**
  - v2: ridurre header per `mask`, `vowels`, `cons`.
  - v3/v4: ridurre tabella `FREQ[256]` sugli ID dei token.

- [ ] **Benchmark “prima/dopo header”**
  - Confrontare:
    - v1/v2/v3/v4 attuali,
    - v1/v2/v3/v4 con header ottimizzati,
  - su:
    - file piccoli (1–10 KB),
    - medi (10–200 KB),
    - mediograndi (200 KB – qualche MB).

---

## 3. Fase 2 – Lemmi & Step5 🟣

Obiettivo: iniziare a giocare sul **livello lemma/morfologia**.

### TODO

- [ ] **Analisi librerie NLP per italiano**
  - Verificare:
    - spaCy (modello italiano),
    - stanza,
    - altri tool di lemmatizzazione.
  - Criteri:
    - qualità lemmatizzazione,
    - semplicità di integrazione in Python,
    - licenza.

- [ ] **Spec di formato v5 (lemmi + tag)**
  - Definire in `docs/formats.md` una bozza di layout v5:
    - vocabolario lemmi,
    - vocabolario tag,
    - stream di ID lemmi,
    - stream di ID tag,
    - stream blocchi non-lettera,
    - sequenza di “token type” per ricostruire l’ordine (WORD/OTHER).
  - Specificare chiaramente:
    - cosa serve per essere **lossless**,
    - eventuale `fallback` a forme lessicali originali.

- [ ] **Step5 “fake” (demo con lowercase + casing)**
  - Implementare una v5 semplificata, con:
    - lemma = parola in minuscolo,
    - tag = pattern maiuscole (lower/upper/capitalize),
  - pipeline:
    - tokenizzazione parole (come v4),
    - mapping parola → (lemma, tag),
    - vocabolario lemmi + vocabolario tag,
    - compressione di:
      - `lemma_ids`,
      - `tag_ids`.
  - Verificare roundtrip e misurare differenze rispetto a v4.

---

## 4. Fase 3 – Porting C 🔥 (ragionevole ma “heavy”)

Obiettivo: portare parte della logica in C per:

- imparare,
- avere una base più vicina a compressori reali,
- eventualmente integrare con altri sistemi.

### TODO

- [ ] **Core Huffman in C**
  - Implementare:
    - costruzione freq,
    - costruzione albero,
    - generazione codici,
    - encode/decode bitstream,
  - con una piccola API tipo:
    - `int huff_compress(const uint8_t* in, size_t n, uint8_t* out, size_t* out_n)`
    - `int huff_decompress(const uint8_t* in, size_t n, uint8_t* out, size_t* out_n, ...)`.

- [ ] **Formato v1 in C**
  - Portare:
    - scrittura header v1,
    - lettura header v1,
    - compress/decompress.
  - Test:
    - file compressi con Python devono essere decompressi correttamente da C, e viceversa (se possibile).

- [ ] **Tokenizzazione parole (v4) in C**
  - Implementare una versione C del pre-processing di v4:
    - split parole / non-lettere,
    - costruzione vocabolario,
    - stream di ID,
    - compress/decompress con core Huffman.

---

## 5. Maybe – estensioni future 🟣

Idee non prioritarie, ma potenzialmente interessanti:

- [ ] **Supporto UTF-8 completo**
  - Oggi la logica è pensata per ASCII semplice.
  - Estendere tokenizzazione (parole/sillabe) a UTF-8 generale (accenti, caratteri non latini, ecc.).

- [ ] **Huffman canonico**
  - Salvare solo lunghezze dei codici, non intere frequenze.
  - Ridurre ulteriormente la dimensione degli header.

- [ ] **Altri modelli di compressione**
  - Sostituire o affiancare Huffman con:
    - arithmetic coding,
    - codici a lunghezza variabile più avanzati.

- [ ] **Plug-in di pre-processing**
  - Rendere il “pre-processing layer” pluggable:
    - modulo Python per definire nuovi Step,
    - interfaccia comune:
      - `encode(text) -> (metadata, id_streams)`
      - `decode(metadata, id_streams) -> text`.

---

## 6. Crazy ideas 🔥

Per le giornate di ispirazione cosmica:

- [ ] **Modelli statistici basati su n-gram / LM per i lemmi**
  - Costruire modelli di probabilità:
    - per sequenze di lemmi,
    - per sequenze di tag morfologici.
  - Usarli per guidare la compressione (es. arithmetic coding condizionato sul contesto).

- [ ] **“Paired corpus” originale + lemma/tag**
  - Salvare, per uno stesso testo:
    - file compresso con v4,
    - file compresso con v5,
  - studiare:
    - correlazioni tra struttura morfologica e compressibilità,
    - effetti di registri linguistici diversi (informale vs tecnico).

- [ ] **Front-end visuale**
  - Piccola UI (web o curses) che:
    - mostra tokenizzazione,
    - sillabazione,
    - mapping parola → lemma/tag,
    - struttura degli header,
    - grafici su frequenze, bit/gamma, ecc.

---

## 7. Filosofia della roadmap

La roadmap è pensata per:

1. Tenere chiara la distinzione tra:
   - **core tecnico** (Huffman, formati, porting in C),
   - **giochi linguistici** (sillabe, parole, lemmi),
2. Permettere a chi apre il progetto (anche “io tra 6 mesi”) di capire:
   - cosa è già sperimentato,
   - cosa è pianificato,
   - cosa è puramente un sogno alcolico da lasagna night.

Questa roadmap **non è un contratto**: serve solo a non perdere di vista le idee buone (e quelle pazze) man mano che il progetto evolve.
