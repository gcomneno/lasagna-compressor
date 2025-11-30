# Design notes – lasagna-compressor
> Appunti di progettazione per un compressore testuale a strati (“lasagna”) focalizzato sull’italiano e sulla struttura linguistica.
---

## 1. Obiettivi del progetto

### 1.1 Obiettivo principale
`lasagna-compressor` **non** nasce per battere gzip, zstd, ecc.  
L’obiettivo è:
- sperimentare **come diversi livelli di struttura linguistica** influenzano la compressione,
- avere un laboratorio per:
  - prototipare idee,
  - misurare effetti di pre-processing diversi,
  - capire i compromessi tra:
    - semplicità,
    - dimensione degli header,
    - complessità linguistica.

In sintesi: è un progetto **didattico / di ricerca personale**, non un prodotto industriale.

### 1.2 Principi chiave

- **Layered design**: ogni “Step” aggiunge un livello di pre-processing, ma riusa lo stesso core di compressione (Huffman su byte).
- **Lossless**: tutti i formati v1–v4 (e futuri) devono permettere di ricostruire il testo originale esattamente.
- **Sperimentale**: formati, layout e API possono cambiare. Non è garantita la compatibilità lunga nel tempo.
- **Bottom-up + top-down ibrido**:
  - conceptual design pensato dall’alto (lemmi, morfologia, linguistica),
  - implementazione incrementale dal basso (byte → V/C/O → sillabe → parole → lemmi).

---

## 2. Strati della “lasagna linguistica”

L’idea di base: un testo ha molti livelli “strutturali”.  
`lasagna-compressor` li esplora uno alla volta.

### 2.1 Strato 0 – Byte grezzi

- Rappresentazione classica: sequenza di byte.
- Nessuna consapevolezza di lettere, parole, lingua.
- Compressione tradizionale: Huffman, LZ, ecc.

Nel progetto, questo è lo **Step 1 (v1)**:  
**Huffman sui byte** con un header semplice (ma relativamente pesante per file piccoli).

---

### 2.2 Strato 1 – Lettere: vocali vs consonanti

L’italiano (e le lingue alfabetiche in generale) hanno una struttura fonologica:

- le **vocali** sono poche ma frequenti (`a,e,i,o,u`),
- le **consonanti** sono più varie,
- le vocali e le consonanti alternano in pattern abbastanza regolari.

Lo Step 2 (v2) prova a sfruttare questo:

- separa il testo in:
  - una **maschera V/C/O**,
  - uno stream di **vocali**,
  - uno stream di **consonanti + altri simboli**.
- comprime i tre stream separatamente con Huffman.

Obiettivo concettuale:

- se la struttura V/C/O è molto regolare, la maschera può comprimersi bene;
- alfabeti ridotti (vocali) dovrebbero produrre codici più corti.

Nella pratica:

- i vantaggi potenziali sono fortemente penalizzati dal costo degli header multipli,
- è uno **Step esplorativo**, più interessante concettualmente che efficace sui file piccoli.

---

### 2.3 Strato 2 – Sillabe (pseudo-sillabe)

Le sillabe sono un’unità intermedia tra lettere e parole:

- riflettono struttura fonetica/articolatoria,
- in molte lingue (incluso l’italiano) hanno pattern frequenti (`-re`, `-zione`, `con-`, ecc.).

Step 3 (v3) introduce:

- una tokenizzazione in:
  - **sequenze di lettere** (parole),
  - **sequenze di non-lettere** (spazi, punteggiatura, ecc.),
- le parole vengono spezzate in **pseudo-sillabe** con una regola grezza:
  - taglio dopo ogni vocale,
- si costruisce un **vocabolario di token** (sillabe + blocchi non-lettera),
- si comprime la **sequenza di ID dei token** con Huffman.

Obiettivo:

- verificare se usare sillabe come “super-simboli” porta a una distribuzione più adatta alla compressione rispetto ai singoli byte.

Limitazioni attuali:

- sillabazione estremamente semplificata (non foneticamente accurata),
- vocabolario limitato a 256 token distinti (per semplicità di implementazione),
- header pesante (vocabolario + FREQ[256]).

---

### 2.4 Strato 3 – Parole intere

Le **parole intere** sono un livello superiore:

- catturano unità lessicali,
- si ripetono spesso in un testo (frequenze di Zipf, ecc.),
- sono la base per passare poi a lemmi e morfologia.

Step 4 (v4) fa:

- tokenizzazione in:
  - sequenze di lettere ASCII → **parole**,
  - sequenze di non-lettere → **blocchi** separati,
- vocabolario di token (parole + blocchi),
- compressione della sequenza di ID dei token con Huffman.

Differenza rispetto a v3:

- v3 lavora su **sillabe** come unità,
- v4 lavora su **parole** come unità.

Vantaggi concettuali:

- le parole sono tipicamente più ripetitive e informative,
- il vocabolario di parole può comprimere bene testi lunghi con lessico ripetuto.

---

### 2.5 Strato 4 – Lemmi e morfologia (idea Step 5)

Strato più alto: **significato lessicale** + **forma morfologica**.

Obiettivo di Step 5 (non ancora implementato):

- trasformare le parole in:
  - **lemma** (forma base: *andare*, *mare*, *bello*),
  - **tag morfologico** (parte del discorso, tempo, persona, genere, numero, ecc.),
- separare:
  - il contenuto “di base” (sequenza di lemmi),
  - le informazioni “di superficie” (tag).

Schema ideale:

- tokenizzazione come v4 (parole / non-parole),
- lemmatizzazione delle parole → `(lemma, tag)` per ogni parola,
- vocabolari separati:
  - `lemma_vocab`,
  - `tag_vocab`,
  - `other_vocab` (blocchi non-lettera),
- compressione separata di:
  - `lemma_ids`,
  - `tag_ids`,
  - `other_ids`.

Note:

- per rimanere totally **lossless**, serve:
  - un generatore morfologico affidabile:
    - `generate(lemma, tag) -> surface_form`,
  - o un dizionario delle forme originali per “correggere” eventuali ambiguità.
- Step 5 è per ora un livello **concettuale**, documentato ma non codificato.

---

## 3. Filosofia di implementazione

### 3.1 Core Hugffman riusabile

Il progetto si basa su un **core Huffman** unico:

- funzioni generiche:
  - costruzione tabella frequenze (`freq[256]`),
  - costruzione albero di Huffman,
  - generazione tabella dei codici,
  - encode/decode di bitstream,
- usato da tutti gli Step (v1–v4, futuro v5).

I vari Step differiscono solo per il **pre-processing** e per il formato dell’**header**.

### 3.2 Formati monolitici, poi ottimizzati

Impostazione attuale:

- gli header sono volutamente **ridondanti e verbosi**:
  - 256 frequenze per ogni stream,
  - vocabolari espliciti salvati in chiaro,
  - lunghezze salvate in `u64` anche dove basterebbe meno.
- questo aumenta l’overhead sui file piccoli, ma:
  - rende i formati più semplici da capire e debug,
  - fa da base per successivi esperimenti di **ottimizzazione header**.

L’idea è:
1. partire da formati “naïf ma chiari”,
2. misurare,
3. ottimizzare header/payload solo quando serve, tenendo sempre la vecchia versione come documentazione.

---

### 3.3 Trade-off: header vs guadagno
Il progetto mette in luce un concetto spesso invisibile nei compressori reali:
> un modello più intelligente non è gratis:  
> costa header, vocabolari, metadati.

Alcuni Step (es. v2, v3, v4):

- hanno pre-processing concettualmente sensato,
- ma nella pratica possono **peggiorare** la dimensione totale per file piccoli/medi, perché:
  - ogni livello porta vocabolari o tabelle aggiuntive,
  - i benefici nel bitstream non compensano il costo dell’header.

Parte del “gioco” della lasagna è proprio **osservare questo compromesso**:

- quanto guadagni nel bitstream,
- quanto perdi in metadati,
- come cambia il bilancio al crescere della dimensione del testo.

---

## 4. Roadmap concettuale

Riassunto della roadmap (da leggere insieme a `docs/roadmap.md` / README):

### 4.1 Fase 0 – Stabilizzare il prototipo Python

- Garantire che v1–v4:
  - siano stabili nella logica di compressione/decompressione,
  - abbiano test di base (roundtrip: input → compress → decompress → input).
- Migliorare la documentazione:
  - `README.md`,
  - `docs/formats.md` (questo file),
  - esempi di utilizzo.

### 4.2 Fase 1 – Ottimizzare gli header

- Ridurre l’overhead di frequenze e vocabolari:
  - non salvare simboli con `freq == 0`,
  - usare tipi più compatti quando possibile,
  - considerare Huffman “canonico” per ridurre la quantità di metadati.
- Valutare i miglioramenti su:
  - file piccoli,
  - medi,
  - grandi.

### 4.3 Fase 2 – Lemmatizzatore & Step 5

- Integrare un lemmatizzatore italiano (quando/SE sarà opportuno).
- Definire un formato v5 che separi:
  - lemmi,
  - tag morfologici,
  - altri token.
- Valutare il comportamento su:
  - testi con morfologia ricca,
  - differente registro linguistico.

### 4.4 Fase 3 – Porting in C

- Portare il **core Huffman** in C (v1).
- Valutare un porting anche per:
  - tokenizzazione parole (v4),
  - eventuale API C che esponga compress/decompress su buffer.

---

## 5. Note finali

`lasagna-compressor` è una **sandbox linguistico-algoritmica**:

- serve più a fare domande che a dare risposte definitive,
- mira a rendere espliciti i layer che spesso i compressori “seri” nascondono dentro modelli complessi.

Domande che il progetto vuole rendere esplorabili:

- Quanto conviene davvero usare:
  - lettere,
  - sillabe,
  - parole,
  - lemmi,
  come unità di compressione?
- Quanto costa portarsi dietro il “sapere linguistico” (vocabolari, tag, modelli)?
- Dove si trova il “punto dolce” tra:
  - **intelligenza del modello**,
  - **peso degli header**,
  - **semplicità di implementazione**?

Il progetto non pretende di rispondere in modo definitivo,  
ma vuole fornire un terreno di gioco dove è facile:

- cambiare una cosa alla volta,
- misurare,
- ragionare.

E, possibilmente, **divertirsi un po’ con la linguistica e la compressione**, che male non fa. 🍝🧠
