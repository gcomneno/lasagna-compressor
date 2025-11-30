#!/usr/bin/env python3
"""
GCC - Grande Compressione Cucita-a-mano
Step 1: Huffman su byte, formato:

[ MAGIC(3) | VERSION(1) | N(8) | FREQ[256]*4 | LASTBITS(1) | DATA(...) ]

- MAGIC     = b'GCC'
- VERSION   = 0x01
- N         = numero di byte originali (uint64, big endian)
- FREQ[i]   = frequenza del byte i (uint32, big endian), per i=0..255
- LASTBITS  = numero di bit validi nell'ultimo byte del bitstream (1..8, oppure 0 se N=0)
- DATA      = bitstream Huffman
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, List
from pathlib import Path

import heapq
import itertools
import sys

MAGIC = b"GCC"
VERSION = 1

# -------------------
# Strutture di base
# -------------------
@dataclass
class HuffmanNode:
    freq: int
    symbol: Optional[int] = None  # 0-255 per foglie, None per nodi interni
    left: Optional["HuffmanNode"] = None
    right: Optional["HuffmanNode"] = None

# -------------------
# Costruzione tabella frequenze
# -------------------
def build_freq_table(data: bytes) -> List[int]:
    """Restituisce un array freq[256] con i conteggi di ogni byte."""
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    return freq

# -------------------
# Albero di Huffman
# -------------------
def build_huffman_tree(freq: List[int]) -> Optional[HuffmanNode]:
    """
    Costruisce l'albero di Huffman a partire dalle frequenze.
    Ritorna la radice o None se non ci sono simboli.
    """
    heap: List[tuple[int, int, HuffmanNode]] = []
    counter = itertools.count()  # per evitare problemi di confronto tra nodi

    # Crea una foglia per ogni simbolo con freq>0
    for sym, f in enumerate(freq):
        if f > 0:
            node = HuffmanNode(freq=f, symbol=sym)
            heapq.heappush(heap, (f, next(counter), node))

    if not heap:
        return None

    # Caso speciale: un solo simbolo
    if len(heap) == 1:
        f, _, only = heap[0]
        dummy_symbol = (only.symbol + 1) % 256
        dummy = HuffmanNode(freq=0, symbol=dummy_symbol)
        heapq.heappush(heap, (0, next(counter), dummy))

    # Combina sempre i due nodi con frequenza minima
    while len(heap) > 1:
        f1, _, n1 = heapq.heappop(heap)
        f2, _, n2 = heapq.heappop(heap)
        parent = HuffmanNode(freq=f1 + f2, symbol=None, left=n1, right=n2)
        heapq.heappush(heap, (parent.freq, next(counter), parent))

    # Radice
    return heap[0][2]

def build_code_table(root: HuffmanNode) -> Dict[int, List[int]]:
    """
    Visita l'albero e costruisce una tabella:
        code[byte] = lista di bit [0,1,...]
    """
    codes: Dict[int, List[int]] = {}

    def dfs(node: HuffmanNode, path: List[int]):
        # Foglia: ha un simbolo e nessun figlio
        if node.symbol is not None and node.left is None and node.right is None:
            # Se il path è vuoto (un solo simbolo), obblighiamo almeno un bit
            codes[node.symbol] = path.copy() if path else [0]
            return
        if node.left is not None:
            dfs(node.left, path + [0])
        if node.right is not None:
            dfs(node.right, path + [1])

    dfs(root, [])
    return codes

# -------------------
# Codifica in bitstream
# -------------------
def encode_data(data: bytes, codes: Dict[int, List[int]]) -> tuple[bytes, int]:
    """
    Converte i byte originali in un bitstream Huffman.

    Ritorna:
        - bytes del bitstream
        - lastbits = numero di bit validi nell'ultimo byte (1..8)
    """
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
        # padding a destra con zeri
        current_byte = current_byte << (8 - bit_count)
        out_bytes.append(current_byte)
        lastbits = bit_count
    else:
        # tutti i byte sono pieni
        lastbits = 8

    return bytes(out_bytes), lastbits

# -------------------
# API di compressione (bytes in -> bytes out)
# -------------------
def compress_bytes(data: bytes) -> bytes:
    """
    Comprimi una sequenza di byte.
    Ritorna l'intero file compresso (header + bitstream).
    """
    N = len(data)
    freq = build_freq_table(data)
    root = build_huffman_tree(freq)

    # Header
    header = bytearray()
    header += MAGIC                  # 3 byte
    header.append(VERSION)           # 1 byte
    header += N.to_bytes(8, "big")   # 8 byte: numero di byte originali

    # Frequenze: 256 * 4 byte (uint32 big endian)
    for f in freq:
        header += f.to_bytes(4, "big")

    # Caso: file vuoto
    if root is None:
        header.append(0)  # LASTBITS = 0
        return bytes(header)

    # Costruisci tabella codici e bitstream
    codes = build_code_table(root)
    bitstream, lastbits = encode_data(data, codes)

    header.append(lastbits)  # 1 byte LASTBITS
    return bytes(header) + bitstream

def decompress_bytes(comp: bytes) -> bytes:
    """
    Decomprimi un blocco di byte nel formato GCC/Huffman.
    """
    # Dimensione minima header
    min_header = 3 + 1 + 8 + 256 * 4 + 1
    if len(comp) < min_header:
        raise ValueError("Dati troppo corti per essere un file GCC valido")

    idx = 0
    magic = comp[idx:idx+3]
    idx += 3
    if magic != MAGIC:
        raise ValueError("Magic number non valido")
    version = comp[idx]
    idx += 1
    if version != VERSION:
        raise ValueError(f"Versione non supportata: {version}")

    # Numero di simboli originali
    N = int.from_bytes(comp[idx:idx+8], "big")
    idx += 8

    # Tabella frequenze
    freq: List[int] = []
    for _ in range(256):
        f = int.from_bytes(comp[idx:idx+4], "big")
        idx += 4
        freq.append(f)

    lastbits = comp[idx]
    idx += 1
    bitstream = comp[idx:]

    if N == 0:
        return b""

    root = build_huffman_tree(freq)
    if root is None:
        return b""

    # Decodifica bit per bit
    out = bytearray()
    node = root
    total_symbols = 0
    total_bytes = len(bitstream)

    for i, byte in enumerate(bitstream):
        bits_in_this_byte = 8
        if i == total_bytes - 1:
            bits_in_this_byte = lastbits  # solo questi bit sono validi

        for bit_index in range(bits_in_this_byte):
            bit = (byte >> (7 - bit_index)) & 1
            node = node.left if bit == 0 else node.right

            # Foglia?
            if node.symbol is not None and node.left is None and node.right is None:
                out.append(node.symbol)
                total_symbols += 1
                node = root
                if total_symbols == N:
                    return bytes(out)

    # In teoria dovremmo già essere usciti sopra
    return bytes(out)

# -------------------
# Helper su file
# -------------------
def compress_file(input_path: str | Path, output_path: str | Path) -> None:
    """Legge un file, lo comprime, scrive il risultato."""
    input_path = Path(input_path)
    output_path = Path(output_path)

    data = input_path.read_bytes()
    comp = compress_bytes(data)
    output_path.write_bytes(comp)

def decompress_file(input_path: str | Path, output_path: str | Path) -> None:
    """Legge un file GCC, lo decomprime, scrive il risultato."""
    input_path = Path(input_path)
    output_path = Path(output_path)

    comp = input_path.read_bytes()
    data = decompress_bytes(comp)
    output_path.write_bytes(data)

def print_stats(original_path: str | Path, compressed_path: str | Path) -> None:
    """
    Stampa statistiche di compressione:
    - dimensione originale / compressa
    - rapporto di compressione
    - bit per simbolo medio
    """
    original_path = Path(original_path)
    compressed_path = Path(compressed_path)

    size_orig = original_path.stat().st_size
    size_comp = compressed_path.stat().st_size

    if size_orig == 0:
        print("File originale vuoto: niente statistiche sensate 🙂")
        return

    ratio = size_comp / size_orig
    bps = (size_comp * 8) / size_orig  # bit per byte originale (qui 1 byte = 1 simbolo)

    print("=== GCC Huffman stats ===")
    print(f"File originale : {original_path} ({size_orig} byte)")
    print(f"File compresso : {compressed_path} ({size_comp} byte)")
    print(f"Rapporto       : {ratio:.3f} (1.0 = nessuna compressione)")
    print(f"Bit/simbolo    : {bps:.3f} (8.0 = non compresso)")
    print("=========================")

# -------------------
# Uso da riga di comando (facoltativo)
# -------------------
def main(argv: list[str]) -> int:
    if len(argv) < 4 or argv[1] not in ("c", "d"):
        print(f"Uso: {argv[0]} c input.txt output.gcc   (compress)")
        print(f"      {argv[0]} d input.gcc output.txt   (decompress)")
        return 1

    mode = argv[1]
    inp = argv[2]
    out = argv[3]

    if mode == "c":
        compress_file(inp, out)
        # Dopo la compressione, stampa le statistiche
        print_stats(inp, out)
    else:
        decompress_file(inp, out)
        print(f"Decompressione completata: {out}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
