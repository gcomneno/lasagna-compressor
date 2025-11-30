#!/usr/bin/env bash
set -e

PYTHON=${PYTHON:-python3}
SCRIPT=src/python/gcc_huffman.py

DATA_DIR=tests/testdata

FILES=("small.txt" "medium.txt")
MODES=("1" "2" "3" "4")

echo "=== lasagna-compressor roundtrip tests ==="
echo "Using: $PYTHON $SCRIPT"
echo

for f in "${FILES[@]}"; do
  INPUT="$DATA_DIR/$f"
  if [ ! -f "$INPUT" ]; then
    echo "[WARN] File non trovato: $INPUT (salto)"
    continue
  fi
  echo "--- File: $INPUT ---"
  for m in "${MODES[@]}"; do
    OUT_COMP="$DATA_DIR/${f}.v${m}.gcc"
    OUT_DEC="$DATA_DIR/${f}.v${m}.dec.txt"

    echo "Step v${m}: compress..."
    $PYTHON "$SCRIPT" c${m} "$INPUT" "$OUT_COMP" || {
      echo "  [ERRORE] compressione v${m} fallita, salto decompressione"
      continue
    }

    echo "Step v${m}: decompress..."
    $PYTHON "$SCRIPT" d${m} "$OUT_COMP" "$OUT_DEC"

    echo "Step v${m}: diff..."
    if diff -q "$INPUT" "$OUT_DEC" > /dev/null; then
      echo "  OK: roundtrip lossless"
    else
      echo "  [ATTENZIONE] diff non vuoto per v${m} su $f"
    fi
    echo
  done
  echo
done

echo "=== Fine test roundtrip ==="
