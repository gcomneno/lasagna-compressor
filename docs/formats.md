# Binary formats – lasagna-compressor

This document describes the **experimental binary formats** used by `lasagna-compressor`.

All formats share:

- **Magic**: 3 bytes, always `0x47 0x43 0x43` (`"GCC"`).
- **Version**: 1 byte, identifies the format variant.
- **Endianness**: all multi-byte integers are stored in **big-endian**.
- **Huffman core**:
  - frequencies are stored as 256 × `uint32`,
  - Huffman codes are implicit (reconstructed from frequencies),
  - bitstreams are stored as raw bytes, most significant bit first.

Types used below:

- `u8`  = unsigned 8-bit integer (1 byte)
- `u16` = unsigned 16-bit integer (2 bytes)
- `u32` = unsigned 32-bit integer (4 bytes)
- `u64` = unsigned 64-bit integer (8 bytes)
- `B[N]` = N raw bytes
- `...`  = rest of file

---

## v1 – Step 1: raw bytes (baseline)

Version byte: `0x01`

### Overview

- Input is treated as a flat sequence of bytes.
- A single **Huffman** code is built over the 256 possible byte values.
- The encoded file contains:
  - a header with original size and frequency table,
  - a Huffman bitstream representing the original bytes.

### Layout

```text
+------------+--------+------------------+------------------------+-----------+-------------------+
| Field      | Type   | Size (bytes)     | Description            | Required  | Notes             |
+============+========+==================+========================+===========+===================+
| MAGIC      | B[3]   | 3                | "GCC"                  | yes       | 0x47 0x43 0x43    |
| VERSION    | u8     | 1                | format version         | yes       | = 1               |
| N          | u64    | 8                | original size in bytes | yes       |                    |
| FREQ[i]    | u32    | 256 × 4 = 1024   | frequency for byte i   | yes       | i = 0..255        |
| LASTBITS   | u8     | 1                | valid bits in last     | yes       | 0 or 1..8         |
| DATA       | B[...] | rest of file     | Huffman bitstream      | yes       |                    |
+------------+--------+------------------+------------------------+-----------+-------------------+
````

### Semantics

* `N` = number of symbols to decode (original byte count).
* `FREQ` is used to reconstruct the Huffman tree.
* `DATA`:

  * bits are read MSB-first within each byte,
  * decoding stops after `N` symbols have been produced.
* `LASTBITS`:

  * if `N == 0`, may be `0`, and `DATA` is empty.
  * otherwise, last byte in `DATA` has `LASTBITS` valid bits (1..8); remaining bits in that byte are padding and must be ignored.

---

## v2 – Step 2: V/C/O split

Version byte: `0x02`

### Overview

Input text is split into three logical streams:

* `mask_stream` : one byte per original input byte, taking values `'V'`, `'C'`, or `'O'`:

  * `'V'` (0x56) = vowel,
  * `'C'` (0x43) = consonant,
  * `'O'` (0x4F) = other (non-letter).
* `vowels_stream` : all vowel bytes, in order.
* `cons_stream` : all other bytes (consonants + non-letters), in order.

Each stream is independently Huffman-compressed using the same core as v1.

### Layout

```text
+--------------+--------+----------------------+----------------------------+
| Field        | Type   | Size (bytes)         | Description                |
+==============+========+======================+============================+
| MAGIC        | B[3]   | 3                    | "GCC"                      |
| VERSION      | u8     | 1                    | format version = 2         |
| N            | u64    | 8                    | original total byte count  |
| LEN_V        | u64    | 8                    | length of vowels_stream    |
| LEN_C        | u64    | 8                    | length of cons_stream      |
| FREQ_MASK[i] | u32    | 256 × 4 = 1024       | freq table for mask        |
| LAST_MASK    | u8     | 1                    | valid bits in last mask    |
| BSIZE_MASK   | u64    | 8                    | size (in bytes) of BS_MASK |
| FREQ_V[i]    | u32    | 256 × 4 = 1024       | freq table for vowels      |
| LAST_V       | u8     | 1                    | valid bits in last vowels  |
| BSIZE_V      | u64    | 8                    | size (in bytes) of BS_V    |
| FREQ_C[i]    | u32    | 256 × 4 = 1024       | freq table for cons        |
| LAST_C       | u8     | 1                    | valid bits in last cons    |
| BSIZE_C      | u64    | 8                    | size (in bytes) of BS_C    |
| BS_MASK      | B[...] | BSIZE_MASK           | bitstream for mask_stream  |
| BS_V         | B[...] | BSIZE_V              | bitstream for vowels       |
| BS_C         | B[...] | BSIZE_C              | bitstream for cons         |
+--------------+--------+----------------------+----------------------------+
```

### Semantics

* `N` is the length of the original byte sequence.
* `mask_stream` length = `N` (one mask byte per original byte).
* `LEN_V` and `LEN_C` are the number of decoded symbols expected from `BS_V` and `BS_C`, respectively.
* Decoding:

  1. Rebuild three Huffman trees from `FREQ_MASK`, `FREQ_V`, `FREQ_C`.
  2. Decode:

     * mask: `N` symbols from `BS_MASK`, using `LAST_MASK`,
     * vowels: `LEN_V` symbols from `BS_V`,
     * cons: `LEN_C` symbols from `BS_C`.
  3. Reconstruct original bytes:

     * iterate over `mask_stream`:

       * if `'V'` → take next symbol from `vowels_stream`,
       * else → take next symbol from `cons_stream`.

---

## v3 – Step 3: pseudo-syllables + non-letter blocks

Version byte: `0x03`

### Overview

The input is tokenized into:

* **letter sequences** (ASCII `A–Z`, `a–z`), further split into “pseudo-syllables”:

  * crude rule: split after each vowel,
* **non-letter sequences** (spaces, punctuation, digits, etc.), kept as separate blocks.

Each distinct token (syllable or non-letter block) is added to a **vocabulary** and assigned an ID in `[0, VOCAB_SIZE-1]`, with `VOCAB_SIZE ≤ 256`.

The compressed file stores:

* the list of tokens in the order of their first appearance (vocabulary),
* a Huffman-encoded sequence of token IDs (one ID per token).

### Layout

```text
+------------+--------+------------------------------+-----------------------------+
| Field      | Type   | Size (bytes)                 | Description                 |
+============+========+==============================+=============================+
| MAGIC      | B[3]   | 3                            | "GCC"                       |
| VERSION    | u8     | 1                            | format version = 3          |
| N_TOKENS   | u64    | 8                            | number of tokens in text    |
| VOCAB_SIZE | u16    | 2                            | number of distinct tokens   |
| VOCAB[i]   | -      | variable, see below          | token definitions           |
| FREQ[j]    | u32    | 256 × 4 = 1024               | freq table for ID stream    |
| LASTBITS   | u8     | 1                            | valid bits in last byte     |
| BS_IDS     | B[...] | rest of file                 | bitstream of token ID seq   |
+------------+--------+------------------------------+-----------------------------+
```

`VOCAB[i]` (for `i = 0 .. VOCAB_SIZE-1`) is stored as:

```text
+--------+--------+------------------+
| Field  | Type   | Size (bytes)     |
+========+========+==================+
| LEN    | u16    | 2                | token length L
| TOKEN  | B[LEN] | L                | raw bytes of token
+--------+--------+------------------+
```

### Semantics

* Tokenization:

  * sequences of ASCII letters → split into pseudo-syllables,
  * sequences of non-letters → a single token each.
* `VOCAB` defines an ordered list of tokens; the index in this list is the token ID.
* The sequence of IDs is encoded using Huffman (one symbol = one ID byte).
* `N_TOKENS` = number of IDs to be decoded.
* Decoding:

  1. Read `VOCAB_SIZE`, then read `VOCAB` tokens into `vocab_list`.
  2. Build Huffman tree from `FREQ`.
  3. Decode `N_TOKENS` ID bytes from `BS_IDS` (using `LASTBITS`).
  4. For each ID `b`, append `vocab_list[b]` to the output.

Note: v3 is currently limited to `VOCAB_SIZE ≤ 256`.

---

## v4 – Step 4: whole words + non-letter blocks

Version byte: `0x04`

### Overview

Similar to v3, but tokenization is simpler:

* **word tokens**: sequences of ASCII letters (`A–Z`, `a–z`),
* **other tokens**: sequences of non-letter bytes.

No syllable splitting: each word is a single token.

Vocabulary and Huffman encoding are done exactly as in v3, but tokens represent **whole words** instead of pseudo-syllables.

### Layout

Identical to v3, except `VERSION = 4` and semantics of tokens:

```text
+------------+--------+------------------------------+-----------------------------+
| Field      | Type   | Size (bytes)                 | Description                 |
+============+========+==============================+=============================+
| MAGIC      | B[3]   | 3                            | "GCC"                       |
| VERSION    | u8     | 1                            | format version = 4          |
| N_TOKENS   | u64    | 8                            | number of tokens in text    |
| VOCAB_SIZE | u16    | 2                            | number of distinct tokens   |
| VOCAB[i]   | -      | variable (LEN + TOKEN bytes) | token definitions           |
| FREQ[j]    | u32    | 256 × 4 = 1024               | freq table for ID stream    |
| LASTBITS   | u8     | 1                            | valid bits in last byte     |
| BS_IDS     | B[...] | rest of file                 | bitstream of token ID seq   |
+------------+--------+------------------------------+-----------------------------+
```

`VOCAB[i]` has the same sub-layout as in v3:

```text
LEN (u16) | TOKEN (B[LEN])
```

### Semantics

* Tokenization:

  * sequences of ASCII letters → one word token,
  * sequences of non-letters → one token per contiguous block.
* The rest (vocab, ID encoding, decoding) behaves exactly like v3.
* Output reconstruction:

  * concatenate `TOKEN` bytes for each decoded ID in order.

Again, v4 is currently limited to `VOCAB_SIZE ≤ 256`.

---

## Notes on future v5 (lemmas + tags)

A possible future format v5 (Step 5) would:

* tokenize words as in v4,
* map each word to `(lemma, tag)` using a lemmatizer,
* store:

  * a lemma vocabulary,
  * a tag vocabulary,
  * one or more Huffman-encoded streams of lemma IDs and tag IDs,
  * plus a way to reconstruct surface forms from `(lemma, tag)`.

This format is **not implemented yet** and is only documented at a conceptual level in `README.md` and design notes.
