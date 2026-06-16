#!/usr/bin/env bash
# Download Norway Chess PGNs and optional FIDE rating lists.
# Files are stored in data/raw/ and then parsed by tools/build_dataset.py.
set -e
mkdir -p data/raw data/fide

# ============================================================
# Lichess Broadcast API.
# The round ID is the last URL segment before #boards in a broadcast URL.
# In this event, classical and Armageddon games can be separate broadcasts,
# so each year can have a classical list and an Armageddon list.
# When Armageddon broadcasts are unavailable, the corresponding list is empty.
# ============================================================

# --- 2025: 10 rounds, Armageddon available for each round. ---
NC2025_ROUNDS=( elkTUv1R 8Ma8Q5pQ BviKOlVd ewv1CJRv KALfYrDN 4MpGqf5j MC47id34 Sbvh39d7 Qv9cnRyb tSRIKmS9 )
NC2025_ARM=(    FXKadMQF ZSJJZojO ewjbU7qP 4MNffXul b3lUTDzE VFYPyPlD 4DTMxNLY BclakG50 ZpRw34eP MIocpJBR )

# --- 2024: 10 rounds, no separate Armageddon broadcasts in this list. ---
NC2024_ROUNDS=( I9TLGEOt sbOHYOVj xmZcMs9U 4JSenCaJ VFMWFVLX Whq5YPU7 4FLBpAW3 2xhPECG3 Qvlkp2yF C5Zzd9mM )
NC2024_ARM=( )

# --- 2023: 9 rounds, no separate Armageddon broadcasts in this list. ---
NC2023_ROUNDS=( ohfaKwUZ Sv6pt144 AKZf0IXy fJhUEF3V rB8kJizd B8eQ1V5b 2UtkIHUg 0tEcjAqk mx43YVG0 )
NC2023_ARM=( )

# --- 2022: 9 rounds; Armageddon is available only for rounds 5, 6, 8, and 9. ---
NC2022_ROUNDS=( 33mPLPA0 XwCedSsH UjuL0cgY baff4olI ANrYbfUr wPckvgJ0 StMuODXT llVvDPW1 1rLDl0nJ )
NC2022_ARM_AT=( 5:WVhrEHXY 6:8joTLEUU 8:bysjifcE 9:zS1Z5ADR )

dl_classical () {
  local year=$1; shift; local i=1
  for rid in "$@"; do
    [ -n "$rid" ] && echo "NC$year R$i (classical $rid)" && \
      curl -sf "https://lichess.org/api/broadcast/round/${rid}.pgn" -o "data/raw/nc${year}_r${i}.pgn"
    i=$((i+1)); sleep 1
  done
}
dl_arm_aligned () {   # Armageddon rounds share the same indexes as classical rounds.
  local year=$1; shift; local i=1
  for rid in "$@"; do
    [ -n "$rid" ] && echo "NC$year R$i (armageddon $rid)" && \
      curl -sf "https://lichess.org/api/broadcast/round/${rid}.pgn" -o "data/raw/nc${year}_r${i}_arm.pgn"
    i=$((i+1)); sleep 1
  done
}
dl_arm_at () {        # Armageddon only for selected rounds: "index:id" pairs.
  local year=$1; shift
  for pair in "$@"; do
    local idx="${pair%%:*}" rid="${pair##*:}"
    echo "NC$year R$idx (armageddon $rid)"
    curl -sf "https://lichess.org/api/broadcast/round/${rid}.pgn" -o "data/raw/nc${year}_r${idx}_arm.pgn"
    sleep 1
  done
}

dl_classical 2025 "${NC2025_ROUNDS[@]}"; dl_arm_aligned 2025 "${NC2025_ARM[@]}"
dl_classical 2024 "${NC2024_ROUNDS[@]}"; dl_arm_aligned 2024 "${NC2024_ARM[@]}"
dl_classical 2023 "${NC2023_ROUNDS[@]}"; dl_arm_aligned 2023 "${NC2023_ARM[@]}"
dl_classical 2022 "${NC2022_ROUNDS[@]}"; dl_arm_at 2022 "${NC2022_ARM_AT[@]}"

# ============================================================
# Optional FIDE rating lists.
# Archive: https://ratings.fide.com/download_lists.phtml
# Example names: standard_may22frl, blitz_may25frl.
# ============================================================
FIDE_LISTS=( )   # Example: ( standard_may22frl blitz_may22frl standard_may25frl blitz_may25frl )
for f in "${FIDE_LISTS[@]}"; do
  echo "FIDE $f"
  curl -sf "https://ratings.fide.com/download/${f}.zip" -o "data/fide/${f}.zip"
  unzip -o -q "data/fide/${f}.zip" -d data/fide/ ; sleep 1
done

echo "Done. Next: python3 tools/build_dataset.py"
