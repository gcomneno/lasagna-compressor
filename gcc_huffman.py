#!/usr/bin/env python3
"""
GCC - Grande Compressione Cucita-a-mano

Core: Huffman su byte, riusato da:
- Step 1: un solo stream (v1)
- Step 2: 3 stream (mask / vocali / consonanti+altro) (v2)
- Step 3: token "sillabe" + blocchi non-lettera, Huffman sugli ID dei token (v3)
- Step 4: token "parole intere" + blocchi non-lettera, Huffman sugli ID dei token (v4)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
from pathlib import Path

import heapq
import itertools
import sys

MAGIC = b"GCC"

VERSION_STEP1 = 1  # byte/bit stream
VERSION_STEP2 = 2  # maschera + vocali + resto
VERSION_STEP3 = 3  # sillabe
VERSION_STEP4 = 4  # parole intere
VERSION_STEP5 = 5  # (concettuale) – lemmi + tag morfologici (“vocabolario mentale”)

# -------------------
# Strutture di base Huffman
# -------------------
@dataclass
class HuffmanNode:
    freq: int
    symbol: Optional[int] = None  # 0-255 per foglie, None per interni
    left: Optional["HuffmanNode"] = None
    right: Optional["HuffmanNode"] = None

def build_freq_table(data: bytes) -> List[int]:
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    return freq

def build_huffman_tree(freq: List[int]) -> Optional[HuffmanNode]:
    heap: List[tuple[int, int, HuffmanNode]] = []
    counter = itertools.count()

    for sym, f in enumerate(freq):
        if f > 0:
            node = HuffmanNode(freq=f, symbol=sym)
            heapq.heappush(heap, (f, next(counter), node))

    if not heap:
        return None

    # Caso speciale: un solo simbolo => aggiungo dummy
    if len(heap) == 1:
        f, _, only = heap[0]
        dummy_symbol = (only.symbol + 1) % 256
        dummy = HuffmanNode(freq=0, symbol=dummy_symbol)
        heapq.heappush(heap, (0, next(counter), dummy))

    while len(heap) > 1:
        f1, _, n1 = heapq.heappop(heap)
        f2, _, n2 = heapq.heappop(heap)
        parent = HuffmanNode(freq=f1 + f2, symbol=None, left=n1, right=n2)
        heapq.heappush(heap, (parent.freq, next(counter), parent))

    return heap[0][2]

def build_code_table(root: HuffmanNode) -> Dict[int, List[int]]:
    codes: Dict[int, List[int]] = {}

    def dfs(node: HuffmanNode, path: List[int]):
        # Foglia
        if node.symbol is not None and node.left is None and node.right is None:
            codes[node.symbol] = path.copy() if path else [0]
            return
        if node.left is not None:
            dfs(node.left, path + [0])
        if node.right is not None:
            dfs(node.right, path + [1])

    dfs(root, [])
    return codes

def encode_data(data: bytes, codes: Dict[int, List[int]]) -> Tuple[bytes, int]:
    """
    data -> (bitstream, lastbits)
    lastbits = numero di bit validi nell'ultimo byte (1..8) oppure 0 se data vuoto.
    """
    if not data:
        return b"", 0

    out_bytes = bytearray()
    current_byte = 0
    bit_count = 0

    for b in data:
        for bit in codes[b]:
            current_byte = (current_byte << 1) | bit
            bit_count += 1
            if bit_count == 8:
                out_bytes.append(current_byte)
                current_byte = 0
                bit_count = 0

    if bit_count > 0:
        current_byte = current_byte << (8 - bit_count)
        out_bytes.append(current_byte)
        lastbits = bit_count
    else:
        lastbits = 8  # tutti i byte pieni

    return bytes(out_bytes), lastbits

def decode_bitstream(root: HuffmanNode, bitstream: bytes, N: int, lastbits: int) -> bytes:
    """
    Decodifica N simboli a partire dall'albero, dal bitstream e da lastbits.
    """
    if N == 0:
        return b""
    if root is None:
        return b""

    out = bytearray()
    node = root
    total_symbols = 0
    total_bytes = len(bitstream)

    for i, byte in enumerate(bitstream):
        bits_in_this_byte = 8
        if i == total_bytes - 1 and lastbits != 0:
            bits_in_this_byte = lastbits

        for bit_index in range(bits_in_this_byte):
            bit = (byte >> (7 - bit_index)) & 1
            node = node.left if bit == 0 else node.right
            if node.symbol is not None and node.left is None and node.right is None:
                out.append(node.symbol)
                total_symbols += 1
                node = root
                if total_symbols == N:
                    return bytes(out)

    return bytes(out)

def huffman_compress_core(data: bytes) -> Tuple[List[int], int, bytes]:
    """
    Core riusabile (Step1/Step2/Step3/Step4): data -> (freq, lastbits, bitstream)
    """
    freq = build_freq_table(data)
    root = build_huffman_tree(freq)
    if root is None:
        return freq, 0, b""
    codes = build_code_table(root)
    bitstream, lastbits = encode_data(data, codes)
    return freq, lastbits, bitstream

def huffman_decompress_core(freq: List[int], bitstream: bytes, N: int, lastbits: int) -> bytes:
    """
    Core riusabile: (freq, bitstream, N, lastbits) -> data
    """
    root = build_huffman_tree(freq)
    if root is None or N == 0:
        return b""
    return decode_bitstream(root, bitstream, N, lastbits)

# -------------------
# Step 1: formato v1 (un solo stream)
# -------------------
def compress_bytes_v1(data: bytes) -> bytes:
    """
    Formato v1:
    [ MAGIC(3) | VERSION(1) | N(8) | FREQ[256]*4 | LASTBITS(1) | DATA(...) ]
    """
    N = len(data)
    freq, lastbits, bitstream = huffman_compress_core(data)

    header = bytearray()
    header += MAGIC
    header.append(VERSION_STEP1)
    header += N.to_bytes(8, "big")

    for f in freq:
        header += f.to_bytes(4, "big")

    header.append(lastbits)
    return bytes(header) + bitstream

def decompress_bytes_v1(comp: bytes) -> bytes:
    min_header = 3 + 1 + 8 + 256 * 4 + 1
    if len(comp) < min_header:
        raise ValueError("Dati troppo corti per GCC v1")

    idx = 0
    magic = comp[idx:idx+3]
    idx += 3
    if magic != MAGIC:
        raise ValueError("Magic number non valido")
    version = comp[idx]
    idx += 1
    if version != VERSION_STEP1:
        raise ValueError(f"Versione v1 richiesta, trovato {version}")

    N = int.from_bytes(comp[idx:idx+8], "big")
    idx += 8

    freq = []
    for _ in range(256):
        f = int.from_bytes(comp[idx:idx+4], "big")
        idx += 4
        freq.append(f)

    lastbits = comp[idx]
    idx += 1
    bitstream = comp[idx:]

    return huffman_decompress_core(freq, bitstream, N, lastbits)

# -------------------
# Step 2: formato v2 (maschera + vocali + resto)
# -------------------
VOWELS = set("aeiouAEIOU")

def split_streams_v2(data: bytes) -> Tuple[bytes, bytes, bytes]:
    """
    Data una sequenza di byte (testo), produce:
    - mask_stream: 'V','C','O' (come byte)
    - vowels_stream: solo le vocali
    - cons_stream: consonanti + tutto il resto
    """
    mask = bytearray()
    vowels = bytearray()
    cons = bytearray()

    for b in data:
        ch = chr(b)
        if ch in VOWELS:
            mask.append(ord('V'))
            vowels.append(b)
        elif ch.isalpha():
            mask.append(ord('C'))
            cons.append(b)
        else:
            mask.append(ord('O'))
            cons.append(b)

    return bytes(mask), bytes(vowels), bytes(cons)

def merge_streams_v2(mask: bytes, vowels: bytes, cons: bytes) -> bytes:
    """
    Ricostruisce il testo originale usando:
    - mask: 'V','C','O'
    - vowels: sequenza di vocali
    - cons: consonanti + non-lettere
    """
    out = bytearray()
    iv = 0
    ic = 0
    for m in mask:
        if m == ord('V'):
            out.append(vowels[iv])
            iv += 1
        else:
            out.append(cons[ic])
            ic += 1
    return bytes(out)

def compress_bytes_v2(data: bytes) -> bytes:
    """
    Formato v2 (Step 2):

    [ MAGIC(3) | VERSION(1)=2 | N(8) | LEN_V(8) | LEN_C(8)
      | FREQ_MASK[256]*4 | LASTBITS_MASK(1) | BSIZE_MASK(8)
      | FREQ_V[256]*4    | LASTBITS_V(1)    | BSIZE_V(8)
      | FREQ_C[256]*4    | LASTBITS_C(1)    | BSIZE_C(8)
      | DATA_MASK | DATA_V | DATA_C ]
    """
    N = len(data)
    mask, vowels, cons = split_streams_v2(data)

    freq_m, last_m, bs_m = huffman_compress_core(mask)
    freq_v, last_v, bs_v = huffman_compress_core(vowels)
    freq_c, last_c, bs_c = huffman_compress_core(cons)

    header = bytearray()
    header += MAGIC
    header.append(VERSION_STEP2)
    header += N.to_bytes(8, "big")

    # lunghezze dei flussi originali
    header += len(vowels).to_bytes(8, "big")  # LEN_V
    header += len(cons).to_bytes(8, "big")    # LEN_C
    # mask length = N, lo sappiamo già

    # FREQ + lastbits + dimensioni bitstream per ciascun flusso
    # MASK
    for f in freq_m:
        header += f.to_bytes(4, "big")
    header.append(last_m)
    header += len(bs_m).to_bytes(8, "big")

    # VOWELS
    for f in freq_v:
        header += f.to_bytes(4, "big")
    header.append(last_v)
    header += len(bs_v).to_bytes(8, "big")

    # CONS
    for f in freq_c:
        header += f.to_bytes(4, "big")
    header.append(last_c)
    header += len(bs_c).to_bytes(8, "big")

    return bytes(header) + bs_m + bs_v + bs_c

def decompress_bytes_v2(comp: bytes) -> bytes:
    """
    Decodifica formato v2 (Step 2).
    """
    # Controllo minimo: almeno header base
    min_header_base = 3 + 1 + 8 + 8 + 8   # MAGIC+VER+N+LEN_V+LEN_C
    if len(comp) < min_header_base:
        raise ValueError("Dati troppo corti per GCC v2 (base header)")

    idx = 0
    magic = comp[idx:idx+3]
    idx += 3
    if magic != MAGIC:
        raise ValueError("Magic non valido")
    version = comp[idx]
    idx += 1
    if version != VERSION_STEP2:
        raise ValueError(f"Versione v2 richiesta, trovato {version}")

    N = int.from_bytes(comp[idx:idx+8], "big")
    idx += 8
    len_v = int.from_bytes(comp[idx:idx+8], "big")
    idx += 8
    len_c = int.from_bytes(comp[idx:idx+8], "big")
    idx += 8
    # mask length = N

    # MASK: freq + lastbits + bsize
    freq_m = []
    for _ in range(256):
        f = int.from_bytes(comp[idx:idx+4], "big")
        idx += 4
        freq_m.append(f)
    last_m = comp[idx]
    idx += 1
    bsize_m = int.from_bytes(comp[idx:idx+8], "big")
    idx += 8

    # VOWELS
    freq_v = []
    for _ in range(256):
        f = int.from_bytes(comp[idx:idx+4], "big")
        idx += 4
        freq_v.append(f)
    last_v = comp[idx]
    idx += 1
    bsize_v = int.from_bytes(comp[idx:idx+8], "big")
    idx += 8

    # CONS
    freq_c = []
    for _ in range(256):
        f = int.from_bytes(comp[idx:idx+4], "big")
        idx += 4
        freq_c.append(f)
    last_c = comp[idx]
    idx += 1
    bsize_c = int.from_bytes(comp[idx:idx+8], "big")
    idx += 8

    # Bitstream per i tre flussi
    end_m = idx + bsize_m
    bs_m = comp[idx:end_m]
    idx = end_m

    end_v = idx + bsize_v
    bs_v = comp[idx:end_v]
    idx = end_v

    end_c = idx + bsize_c
    bs_c = comp[idx:end_c]

    # Decodifica i tre flussi
    mask = huffman_decompress_core(freq_m, bs_m, N, last_m)
    vowels = huffman_decompress_core(freq_v, bs_v, len_v, last_v)
    cons = huffman_decompress_core(freq_c, bs_c, len_c, last_c)

    # Ricostruisci il testo
    return merge_streams_v2(mask, vowels, cons)

# -------------------
# Step 3: formato v3 (sillabe + blocchi non-lettera)
# -------------------
def _is_ascii_letter(b: int) -> bool:
    return (65 <= b <= 90) or (97 <= b <= 122)  # A-Z a-z

_VOWEL_BYTES = {ord(c) for c in "aeiouAEIOU"}

def _is_vowel_byte(b: int) -> bool:
    return b in _VOWEL_BYTES

def split_word_into_syllables(word: bytes) -> List[bytes]:
    """
    Spezzettamento grezzo di una "parola" (solo lettere) in pseudo-sillabe:
    - accumula caratteri
    - spezza dopo ogni vocale
    Non è foneticamente perfetto, ma basta per sperimentare.
    """
    syllables: List[bytes] = []
    current = bytearray()
    for b in word:
        current.append(b)
        if _is_vowel_byte(b):
            syllables.append(bytes(current))
            current.clear()
    if current:
        syllables.append(bytes(current))
    return syllables

def tokenize_syllables_and_other(data: bytes) -> List[bytes]:
    """
    Trasforma il testo in una lista di token:
    - sequenze di lettere -> spezzate in pseudo-sillabe
    - sequenze di non-lettere -> tenute come blocchi separati
    """
    tokens: List[bytes] = []
    i = 0
    n = len(data)

    while i < n:
        b = data[i]
        if _is_ascii_letter(b):
            # raccogli sequenza di lettere
            start = i
            i += 1
            while i < n and _is_ascii_letter(data[i]):
                i += 1
            word = data[start:i]
            sylls = split_word_into_syllables(word)
            tokens.extend(sylls)
        else:
            # raccogli sequenza di non-lettere
            start = i
            i += 1
            while i < n and not _is_ascii_letter(data[i]):
                i += 1
            tokens.append(data[start:i])
    return tokens

def compress_bytes_v3(data: bytes) -> bytes:
    """
    Formato v3 (Step 3: sillabe):

    [ MAGIC(3) | VERSION(1)=3
      | N_TOKENS(8)
      | VOCAB_SIZE(2)
      | VOCAB:
          per i=0..VOCAB_SIZE-1:
             LEN(2) | TOKEN_BYTES
      | FREQ[256]*4 | LASTBITS(1) | BITSTREAM_IDs(...) ]
    """
    tokens = tokenize_syllables_and_other(data)
    N_tokens = len(tokens)

    # Costruisci vocabolario: token_bytes -> id
    vocab: Dict[bytes, int] = {}
    vocab_list: List[bytes] = []
    for tok in tokens:
        if tok not in vocab:
            vocab[tok] = len(vocab_list)
            vocab_list.append(tok)

    vocab_size = len(vocab_list)
    if vocab_size > 256:
        raise ValueError(
            f"VOCAB troppo grande per v3 ( {vocab_size} > 256 ). "
            "Per ora Step3 richiede al massimo 256 token distinti."
        )

    # Sequenza di ID come bytes
    id_stream = bytearray()
    for tok in tokens:
        id_stream.append(vocab[tok])

    freq, lastbits, bitstream = huffman_compress_core(bytes(id_stream))

    header = bytearray()
    header += MAGIC
    header.append(VERSION_STEP3)
    header += N_tokens.to_bytes(8, "big")

    # VOCAB_SIZE (2 byte)
    header += vocab_size.to_bytes(2, "big")

    # VOCAB
    for tok_bytes in vocab_list:
        L = len(tok_bytes)
        if L > 0xFFFF:
            raise ValueError("Token troppo lungo per LEN(2 byte)")
        header += L.to_bytes(2, "big")
        header += tok_bytes

    # FREQ[256]*4
    for f in freq:
        header += f.to_bytes(4, "big")

    # LASTBITS
    header.append(lastbits)

    # Bitstream fino alla fine
    return bytes(header) + bitstream

def decompress_bytes_v3(comp: bytes) -> bytes:
    """
    Decodifica formato v3 (Step 3: sillabe).
    """
    idx = 0
    min_header_base = 3 + 1 + 8 + 2
    if len(comp) < min_header_base:
        raise ValueError("Dati troppo corti per GCC v3 (base header)")

    magic = comp[idx:idx+3]
    idx += 3
    if magic != MAGIC:
        raise ValueError("Magic non valido")

    version = comp[idx]
    idx += 1
    if version != VERSION_STEP3:
        raise ValueError(f"Versione v3 richiesta, trovato {version}")

    N_tokens = int.from_bytes(comp[idx:idx+8], "big")
    idx += 8

    vocab_size = int.from_bytes(comp[idx:idx+2], "big")
    idx += 2

    # VOCAB
    vocab_list: List[bytes] = []
    for _ in range(vocab_size):
        if idx + 2 > len(comp):
            raise ValueError("File troncato (LEN token)")
        L = int.from_bytes(comp[idx:idx+2], "big")
        idx += 2
        if idx + L > len(comp):
            raise ValueError("File troncato (TOKEN bytes)")
        tok_bytes = comp[idx:idx+L]
        idx += L
        vocab_list.append(tok_bytes)

    # FREQ[256]*4
    if idx + 256*4 + 1 > len(comp):
        raise ValueError("File troncato (freq + lastbits)")

    freq: List[int] = []
    for _ in range(256):
        f = int.from_bytes(comp[idx:idx+4], "big")
        idx += 4
        freq.append(f)

    lastbits = comp[idx]
    idx += 1

    bitstream = comp[idx:]

    # Decodifica stream di ID
    id_bytes = huffman_decompress_core(freq, bitstream, N_tokens, lastbits)

    # Ricostruisci il testo concatenando i token
    out = bytearray()
    for b in id_bytes:
        tok = vocab_list[b]
        out += tok

    return bytes(out)

# -------------------
# Step 4: formato v4 (parole intere + blocchi non-lettera)
# -------------------
def tokenize_words_and_other(data: bytes) -> List[bytes]:
    """
    Trasforma il testo in token:
    - sequenze di lettere ASCII A-Z/a-z -> parole
    - sequenze di non-lettere -> blocchi separati
    """
    tokens: List[bytes] = []
    i = 0
    n = len(data)

    while i < n:
        b = data[i]
        if _is_ascii_letter(b):
            # raccogli sequenza di lettere
            start = i
            i += 1
            while i < n and _is_ascii_letter(data[i]):
                i += 1
            tokens.append(data[start:i])
        else:
            # raccogli sequenza di non-lettere
            start = i
            i += 1
            while i < n and not _is_ascii_letter(data[i]):
                i += 1
            tokens.append(data[start:i])

    return tokens

def compress_bytes_v4(data: bytes) -> bytes:
    """
    Formato v4 (Step 4: parole intere):

    [ MAGIC(3) | VERSION(1)=4
      | N_TOKENS(8)
      | VOCAB_SIZE(2)
      | VOCAB:
          per i=0..VOCAB_SIZE-1:
             LEN(2) | TOKEN_BYTES
      | FREQ[256]*4 | LASTBITS(1) | BITSTREAM_IDs(...) ]
    """
    tokens = tokenize_words_and_other(data)
    N_tokens = len(tokens)

    # Costruisci vocabolario: token_bytes -> id
    vocab: Dict[bytes, int] = {}
    vocab_list: List[bytes] = []
    for tok in tokens:
        if tok not in vocab:
            vocab[tok] = len(vocab_list)
            vocab_list.append(tok)

    vocab_size = len(vocab_list)
    if vocab_size > 256:
        raise ValueError(
            f"VOCAB troppo grande per v4 ( {vocab_size} > 256 ). "
            "Per ora Step4 richiede al massimo 256 token distinti."
        )

    # Sequenza di ID come bytes
    id_stream = bytearray()
    for tok in tokens:
        id_stream.append(vocab[tok])

    freq, lastbits, bitstream = huffman_compress_core(bytes(id_stream))

    header = bytearray()
    header += MAGIC
    header.append(VERSION_STEP4)
    header += N_tokens.to_bytes(8, "big")

    # VOCAB_SIZE (2 byte)
    header += vocab_size.to_bytes(2, "big")

    # VOCAB
    for tok_bytes in vocab_list:
        L = len(tok_bytes)
        if L > 0xFFFF:
            raise ValueError("Token troppo lungo per LEN(2 byte)")
        header += L.to_bytes(2, "big")
        header += tok_bytes

    # FREQ[256]*4
    for f in freq:
        header += f.to_bytes(4, "big")

    # LASTBITS
    header.append(lastbits)

    # Bitstream fino alla fine
    return bytes(header) + bitstream

def decompress_bytes_v4(comp: bytes) -> bytes:
    """
    Decodifica formato v4 (Step 4: parole intere).
    """
    idx = 0
    min_header_base = 3 + 1 + 8 + 2
    if len(comp) < min_header_base:
        raise ValueError("Dati troppo cortti per GCC v4 (base header)")

    magic = comp[idx:idx+3]
    idx += 3
    if magic != MAGIC:
        raise ValueError("Magic non valido")

    version = comp[idx]
    idx += 1
    if version != VERSION_STEP4:
        raise ValueError(f"Versione v4 richiesta, trovato {version}")

    N_tokens = int.from_bytes(comp[idx:idx+8], "big")
    idx += 8

    vocab_size = int.from_bytes(comp[idx:idx+2], "big")
    idx += 2

    # VOCAB
    vocab_list: List[bytes] = []
    for _ in range(vocab_size):
        if idx + 2 > len(comp):
            raise ValueError("File troncato (LEN token)")
        L = int.from_bytes(comp[idx:idx+2], "big")
        idx += 2
        if idx + L > len(comp):
            raise ValueError("File troncato (TOKEN bytes)")
        tok_bytes = comp[idx:idx+L]
        idx += L
        vocab_list.append(tok_bytes)

    # FREQ[256]*4
    if idx + 256*4 + 1 > len(comp):
        raise ValueError("File troncato (freq + lastbits)")

    freq: List[int] = []
    for _ in range(256):
        f = int.from_bytes(comp[idx:idx+4], "big")
        idx += 4
        freq.append(f)

    lastbits = comp[idx]
    idx += 1

    bitstream = comp[idx:]

    # Decodifica stream di ID
    id_bytes = huffman_decompress_core(freq, bitstream, N_tokens, lastbits)

    # Ricostruisci il testo concatenando i token
    out = bytearray()
    for b in id_bytes:
        tok = vocab_list[b]
        out += tok

    return bytes(out)

# -------------------
# Helper su file
# -------------------
def compress_file_v1(input_path: str | Path, output_path: str | Path) -> None:
    data = Path(input_path).read_bytes()
    comp = compress_bytes_v1(data)
    Path(output_path).write_bytes(comp)

def decompress_file_v1(input_path: str | Path, output_path: str | Path) -> None:
    comp = Path(input_path).read_bytes()
    data = decompress_bytes_v1(comp)
    Path(output_path).write_bytes(data)

def compress_file_v2(input_path: str | Path, output_path: str | Path) -> None:
    data = Path(input_path).read_bytes()
    comp = compress_bytes_v2(data)
    Path(output_path).write_bytes(comp)

def decompress_file_v2(input_path: str | Path, output_path: str | Path) -> None:
    comp = Path(input_path).read_bytes()
    data = decompress_bytes_v2(comp)
    Path(output_path).write_bytes(data)

def compress_file_v3(input_path: str | Path, output_path: str | Path) -> None:
    data = Path(input_path).read_bytes()
    comp = compress_bytes_v3(data)
    Path(output_path).write_bytes(comp)

def decompress_file_v3(input_path: str | Path, output_path: str | Path) -> None:
    comp = Path(input_path).read_bytes()
    data = decompress_bytes_v3(comp)
    Path(output_path).write_bytes(data)

def compress_file_v4(input_path: str | Path, output_path: str | Path) -> None:
    data = Path(input_path).read_bytes()
    comp = compress_bytes_v4(data)
    Path(output_path).write_bytes(comp)

def decompress_file_v4(input_path: str | Path, output_path: str | Path) -> None:
    comp = Path(input_path).read_bytes()
    data = decompress_bytes_v4(comp)
    Path(output_path).write_bytes(data)

# -------------------
# Statistiche
# -------------------
def print_stats(original_path: str | Path, compressed_path: str | Path, label: str) -> None:
    original_path = Path(original_path)
    compressed_path = Path(compressed_path)

    size_orig = original_path.stat().st_size
    size_comp = compressed_path.stat().st_size

    print(f"=== GCC Huffman stats ({label}) ===")
    print(f"File originale : {original_path} ({size_orig} byte)")
    print(f"File compresso : {compressed_path} ({size_comp} byte)")

    if size_orig == 0:
        print("File originale vuoto: niente statistiche sensate 🙂")
        print("===============================")
        return

    ratio = size_comp / size_orig
    bps = (size_comp * 8) / size_orig

    print(f"Rapporto       : {ratio:.3f} (1.0 = nessuna compressione)")
    print(f"Bit/simbolo    : {bps:.3f} (8.0 = non compresso)")
    print("===============================")

# -------------------
# CLI
# -------------------
def main(argv: List[str]) -> int:
    if len(argv) < 4 or argv[1] not in ("c1", "d1", "c2", "d2", "c3", "d3", "c4", "d4"):
        print(f"Uso:")
        print(f"  {argv[0]} c1 input.txt output.gcc1   (compress Step1)")
        print(f"  {argv[0]} d1 input.gcc1 output.txt   (decompress Step1)")
        print(f"  {argv[0]} c2 input.txt output.gcc2   (compress Step2 V/C/O)")
        print(f"  {argv[0]} d2 input.gcc2 output.txt   (decompress Step2)")
        print(f"  {argv[0]} c3 input.txt output.gcc3   (compress Step3 sillabe)")
        print(f"  {argv[0]} d3 input.gcc3 output.txt   (decompress Step3)")
        print(f"  {argv[0]} c4 input.txt output.gcc4   (compress Step4 parole)")
        print(f"  {argv[0]} d4 input.gcc4 output.txt   (decompress Step4)")
        return 1

    mode = argv[1]
    inp = argv[2]
    out = argv[3]

    if mode == "c1":
        compress_file_v1(inp, out)
        print_stats(inp, out, "Step1")
    elif mode == "d1":
        decompress_file_v1(inp, out)
        print(f"Decompressione Step1 completata: {out}")
    elif mode == "c2":
        compress_file_v2(inp, out)
        print_stats(inp, out, "Step2")
    elif mode == "d2":
        decompress_file_v2(inp, out)
        print(f"Decompressione Step2 completata: {out}")
    elif mode == "c3":
        compress_file_v3(inp, out)
        print_stats(inp, out, "Step3 (sillabe)")
    elif mode == "d3":
        decompress_file_v3(inp, out)
        print(f"Decompressione Step3 completata: {out}")
    elif mode == "c4":
        compress_file_v4(inp, out)
        print_stats(inp, out, "Step4 (parole)")
    else:  # d4
        decompress_file_v4(inp, out)
        print(f"Decompressione Step4 completata: {out}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
